"""systemd user timers and reminders."""
from __future__ import annotations

import os
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok

_MEERA_DATA = Path(os.path.expanduser("~/.local/share/meera_reminders"))
_SYSTEMD_USER = Path(os.path.expanduser("~/.config/systemd/user"))


def _timer_list(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        [
            "systemctl",
            "--user",
            "list-timers",
            "--all",
            "--no-pager",
            "--no-legend",
        ],
        timeout=20.0,
        max_stdout_chars=131072,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            r.stderr or r.stdout or "systemctl list-timers failed",
            "COMMAND_FAILED",
        )
    lines = [ln.rstrip() for ln in r.stdout.splitlines() if ln.strip()]
    return tool_result_ok(
        f"{len(lines)} user timer row(s)",
        data={"lines": lines[:300]},
    )


def _next_unit_id() -> str:
    _MEERA_DATA.mkdir(parents=True, exist_ok=True)
    counter_path = _MEERA_DATA / "counter"
    try:
        counter = int(counter_path.read_text().strip())
    except (FileNotFoundError, ValueError):
        counter = 0
    counter += 1
    counter_path.write_text(str(counter))
    return f"meera-reminder-{counter}"


def _daemon_reload() -> ToolResult | None:
    r = run_argv(
        ["systemctl", "--user", "daemon-reload"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            r.stderr or r.stdout or "systemctl daemon-reload failed",
            "COMMAND_FAILED",
        )
    return None


def _tool_reminder_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    message: str = params["message"]
    delay_minutes: int = params["delay_minutes"]
    unit_id: str = params.get("unit_id") or _next_unit_id()

    if delay_minutes < 1 or delay_minutes > 10080:
        return tool_result_err(
            "delay_minutes must be between 1 and 10080",
            "INVALID_VALUE",
        )

    for ch in unit_id:
        if ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._":
            return tool_result_err(
                "unit_id contains invalid characters",
                "INVALID_VALUE",
            )

    timer_path = _SYSTEMD_USER / f"{unit_id}.timer"
    if timer_path.exists():
        return tool_result_err(
            f"Timer {unit_id} already exists",
            "ALREADY_EXISTS",
        )

    target_time = datetime.now() + timedelta(minutes=delay_minutes)
    calendar_str = target_time.strftime("%Y-%m-%d %H:%M:00")

    description = message.replace("\n", " ")[:100]

    timer_content = (
        f"[Unit]\n"
        f"Description=Meera reminder: {description}\n"
        f"\n"
        f"[Timer]\n"
        f"OnCalendar={calendar_str}\n"
        f"Persistent=false\n"
        f"AccuracySec=10\n"
        f"\n"
        f"[Install]\n"
        f"WantedBy=timers.target\n"
    )

    msg_file = _MEERA_DATA / f"{unit_id}.txt"
    _MEERA_DATA.mkdir(parents=True, exist_ok=True)
    msg_file.write_text(message)

    cleanup_cmd = (
        f'notify-send "Meera Reminder" '
        f'"$(cat {_MEERA_DATA}/{unit_id}.txt)" '
        f'&& rm -f {_MEERA_DATA}/{unit_id}.txt '
        f'&& systemctl --user disable --now {unit_id}.timer '
        f'&& systemctl --user stop {unit_id}.timer '
        f'&& rm -f {_SYSTEMD_USER}/{unit_id}.timer {_SYSTEMD_USER}/{unit_id}.service '
        f'&& systemctl --user daemon-reload'
    )

    service_content = (
        f"[Unit]\n"
        f"Description=Meera notification\n"
        f"\n"
        f"[Service]\n"
        f"Type=oneshot\n"
        f"ExecStart=/bin/bash -c '{cleanup_cmd}'\n"
    )

    timer_path.write_text(timer_content)
    (_SYSTEMD_USER / f"{unit_id}.service").write_text(service_content)

    reload_err = _daemon_reload()
    if reload_err is not None:
        return reload_err

    r = run_argv(
        ["systemctl", "--user", "enable", "--now", f"{unit_id}.timer"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        for p in [timer_path, _SYSTEMD_USER / f"{unit_id}.service", msg_file]:
            if p.exists():
                p.unlink(missing_ok=True)
        return tool_result_err(
            r.stderr or r.stdout or "Failed to enable timer",
            "COMMAND_FAILED",
        )

    return tool_result_ok(
        f"Reminder set: {unit_id}",
        data={
            "unit_id": unit_id,
            "target_time": calendar_str,
            "delay_minutes": delay_minutes,
        },
    )


def _tool_reminder_delete(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    unit_id: str = params["unit_id"]

    r = run_argv(
        ["systemctl", "--user", "disable", "--now", f"{unit_id}.timer"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r

    r2 = run_argv(
        ["systemctl", "--user", "stop", f"{unit_id}.timer"],
        timeout=10.0,
    )
    if isinstance(r2, ToolResult):
        return r2

    timer_path = _SYSTEMD_USER / f"{unit_id}.timer"
    service_path = _SYSTEMD_USER / f"{unit_id}.service"
    msg_file = _MEERA_DATA / f"{unit_id}.txt"

    for p in [timer_path, service_path, msg_file]:
        if p.exists():
            p.unlink(missing_ok=True)

    reload_err = _daemon_reload()
    if reload_err is not None:
        return reload_err

    if r.returncode != 0 and r2.returncode != 0:
        return tool_result_err(
            r.stderr or r2.stderr or "Timer not found",
            "NOT_FOUND",
        )

    return tool_result_ok(
        f"Reminder deleted: {unit_id}",
        data={"unit_id": unit_id},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="timer_list",
        description="List systemd --user timers.",
        parameters=[],
        handler=_timer_list,
        read_only=True,
        exemplars=[
            "list my reminders",
            "show active timers",
            "what reminders do I have",
            "show my pending reminders",
            "list user timers",
            "what timers are scheduled",
        ],
    ),
    ToolSpec(
        name="reminder_set",
        description="Set a one-shot reminder that fires a desktop notification after the given delay. The timer auto-cleans after firing.",
        parameters=[
            ToolParam(
                name="message",
                param_type="string",
                required=True,
                description="The reminder text to show in the notification.",
            ),
            ToolParam(
                name="delay_minutes",
                param_type="integer",
                required=True,
                description="Minutes from now until the reminder fires (1-10080).",
            ),
            ToolParam(
                name="unit_id",
                param_type="string",
                required=False,
                description="Optional unique identifier. Auto-generated if not provided.",
                default=None,
            ),
        ],
        handler=_tool_reminder_set,
        read_only=False,
        exemplars=[
            "remind me in 30 minutes to call mom",
            "set a reminder for 5 minutes",
            "remind me in an hour to take a break",
            "create a reminder to drink water in 20 mins",
            "set a 10 minute timer to check the oven",
            "ping me in 2 hours",
            "wake me up in 45 minutes",
        ],
    ),
    ToolSpec(
        name="reminder_delete",
        description="Delete a previously set reminder by its unit ID.",
        parameters=[
            ToolParam(
                name="unit_id",
                param_type="string",
                required=True,
                description="The timer name to remove (without .timer suffix).",
            ),
        ],
        handler=_tool_reminder_delete,
        read_only=False,
        exemplars=[
            "delete reminder meera-reminder-3",
            "remove the reminder",
            "cancel reminder X",
            "delete my timer",
            "remove the reminder named meera-reminder-1",
            "scrap that reminder",
        ],
    ),
]
