"""systemd user timers, reminders, and GNOME Calendar import."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok

_MEERA_DATA = Path(os.path.expanduser("~/.local/share/meera_reminders"))
_SYSTEMD_USER = Path(os.path.expanduser("~/.config/systemd/user"))


def _reminder_list(params: Mapping[str, Any]) -> ToolResult:
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
        f"{len(lines)} systemd user timer row(s) (includes Meera reminders: meera-reminder-*)",
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

    _SYSTEMD_USER.mkdir(parents=True, exist_ok=True)
    service_path = _SYSTEMD_USER / f"{unit_id}.service"
    timer_path.write_text(timer_content)
    service_path.write_text(service_content)

    reload_err = _daemon_reload()
    if reload_err is not None:
        for p in [timer_path, service_path, msg_file]:
            if p.exists():
                p.unlink(missing_ok=True)
        return reload_err

    r = run_argv(
        ["systemctl", "--user", "enable", "--now", f"{unit_id}.timer"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        for p in [timer_path, service_path, msg_file]:
            if p.exists():
                p.unlink(missing_ok=True)
        return r
    if r.returncode != 0:
        for p in [timer_path, service_path, msg_file]:
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


# ---- GNOME Calendar: import via .ics + gio open (no dedicated CLI) ----

_MAX_SUMMARY_LEN = 1024
_MIN_DURATION_MIN = 1
_MAX_DURATION_MIN = 10080  # 7 days


def _ics_text_escape(s: str) -> str:
    """RFC 5545 TEXT escaping for SUMMARY / DESCRIPTION (subset)."""
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s.replace("\n", "\\n")


def _duration_to_ics(duration_minutes: int) -> str:
    if duration_minutes % 60 == 0 and duration_minutes >= 60:
        return f"PT{duration_minutes // 60}H"
    return f"PT{duration_minutes}M"


# Calendar start: copy date/time digits from the model string into ICS (no conversion).
_START_ARG_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:Z|[+-]\d{2}:\d{2})?$"
)


def _local_iana_tzid() -> str:
    """Best-effort IANA zone name for the system local timezone (e.g. America/Los_Angeles)."""
    tz = datetime.now().astimezone().tzinfo
    key = getattr(tz, "key", None) if tz is not None else None
    if key:
        return str(key)
    tz_env = (os.environ.get("TZ") or "").strip()
    if tz_env:
        return tz_env
    try:
        lp = Path("/etc/localtime").resolve()
        for i, part in enumerate(lp.parts):
            if part == "zoneinfo" and i + 1 < len(lp.parts):
                return "/".join(lp.parts[i + 1 :])
    except (OSError, ValueError):
        pass
    return "UTC"


def _ics_dtstart_compact_from_start_arg(start: str) -> str | ToolResult:
    s = start.strip()
    if not s:
        return tool_result_err(
            "start must be a non-empty datetime like 2024-05-01T09:00:00Z.",
            "VALIDATION_ERROR",
        )
    m = _START_ARG_RE.match(s)
    if not m:
        return tool_result_err(
            "start must look like 2024-05-01T09:00:00 or 2024-05-01T14:00:00Z.",
            "VALIDATION_ERROR",
        )
    y, mo, d, h, mi, se = m.groups()
    return f"{y}{mo}{d}T{h}{mi}{se}"


def _build_vevent_ics_document(
    summary: str,
    dtstart_compact: str,
    dtstart_tzid: str,
    duration_minutes: int,
) -> str:
    """Return a minimal VEVENT ICS (CRLF). Local wall time + TZID (not UTC Z) for GNOME import."""
    uid = f"{uuid.uuid4()}@meera"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dur = _duration_to_ics(duration_minutes)
    summ = _ics_text_escape(summary.strip())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Meera//GNOME Calendar//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"SUMMARY:{summ}",
        f"DTSTART;TZID={dtstart_tzid}:{dtstart_compact}",
        f"DURATION:{dur}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def _gnome_calendar_event_add(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    summary: str = params["summary"]
    start_raw: str = params["start"]
    duration_minutes: int = params["duration_minutes"]

    text = summary.strip()
    if not text:
        return tool_result_err("summary must not be empty", "VALIDATION_ERROR")
    if len(text) > _MAX_SUMMARY_LEN:
        return tool_result_err(
            f"summary exceeds {_MAX_SUMMARY_LEN} characters",
            "VALIDATION_ERROR",
        )

    if duration_minutes < _MIN_DURATION_MIN or duration_minutes > _MAX_DURATION_MIN:
        return tool_result_err(
            f"duration_minutes must be between {_MIN_DURATION_MIN} and {_MAX_DURATION_MIN}",
            "VALIDATION_ERROR",
        )

    dtstart_compact = _ics_dtstart_compact_from_start_arg(start_raw)
    if isinstance(dtstart_compact, ToolResult):
        return dtstart_compact

    ics_body = _build_vevent_ics_document(
        text, dtstart_compact, _local_iana_tzid(), duration_minutes
    )
    if os.environ.get("MEERA_DEBUG_RETRIEVAL", "").strip().lower() in ("1", "true", "yes", "on"):
        print(f"[retrieval] calendar ics (exact file content passed to gio open):\n{ics_body}", file=sys.stderr, flush=True)
    ics_bytes = ics_body.encode("utf-8")

    fd: int | None = None
    path: str | None = None
    try:
        fd, path = tempfile.mkstemp(prefix="meera-cal-", suffix=".ics")
        with os.fdopen(fd, "wb") as f:
            f.write(ics_bytes)
        fd = None
    except OSError as e:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
        return tool_result_err(str(e), "OS_ERROR")

    assert path is not None
    r = run_argv(["gio", "open", path], timeout=30.0)
    try:
        os.unlink(path)
    except OSError:
        pass

    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            r.stderr or r.stdout or "gio open failed",
            "COMMAND_FAILED",
        )

    return tool_result_ok(
        "Calendar invite written and opened; confirm import in GNOME Calendar if prompted.",
        data={
            "summary": text,
            "start": start_raw.strip(),
            "duration_minutes": duration_minutes,
        },
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="reminder_list",
        description=(
            "List pending scheduled items from systemd user timers. Use this when the user "
            "asks for their reminders: Meera reminder units are named meera-reminder-* and "
            "appear in the output together with any other --user timers."
        ),
        parameters=[],
        handler=_reminder_list,
        read_only=True,
        exemplars=[
            "list my reminders",
            "list all reminders",
            "what reminders do I have",
            "show my pending reminders",
            "show active reminders",
            "what reminders are scheduled",
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
    ToolSpec(
        name="gnome_calendar_event_add",
        description=(
            "Add or schedule a calendar event (meeting, appointment, lunch, etc.) for GNOME "
            "Calendar by writing a temporary .ics file and opening it with gio so the user can "
            "import the event into the Evolution/GNOME Calendar pipeline. The start string's "
            "date and time digits are written to DTSTART with the system local IANA timezone "
            "(no UTC Z suffix) so the event appears at that wall-clock time in the calendar."
        ),
        parameters=[
            ToolParam(
                name="summary",
                param_type="string",
                required=True,
                description="Event title (SUMMARY), e.g. 'Lunch with Alex'.",
            ),
            ToolParam(
                name="start",
                param_type="string",
                required=True,
                description=(
                    "Event start: YYYY-MM-DDTHH:MM:SS with optional Z or ±HH:MM offset; "
                    "those clock digits are copied into DTSTART (no timezone conversion)."
                ),
            ),
            ToolParam(
                name="duration_minutes",
                param_type="integer",
                required=True,
                description="Length of the event in minutes (1-10080).",
            ),
        ],
        handler=_gnome_calendar_event_add,
        read_only=False,
        exemplars=[
            "add lunch to my calendar tomorrow at 1pm",
            "put lunch on the calendar tomorrow at noon",
            "schedule a meeting tomorrow at 3pm for an hour",
            "add a calendar event team standup tomorrow at 9",
            "create a meeting in my calendar Friday 3pm for one hour",
            "schedule a dentist appointment on June 10 at 10:30",
            "block off 2 hours on my calendar tomorrow morning for deep work",
            "new calendar entry coffee with Sam Thursday 4pm",
            "book 30 minutes on my calendar for standup",
            "add an event titled budget review starting 2026-05-01T15:00:00 local lasting 90 minutes",
            "GNOME calendar add event sync interview Monday 11am",
            "remind me on the calendar that I have a flight at 7am",
        ],
    ),
]
