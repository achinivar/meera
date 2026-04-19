"""systemd user timers (read-only)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


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


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="timer_list",
        description="List systemd --user timers.",
        parameters=[
            ToolParam(
                name="distro",
                param_type="string",
                required=True,
                description='Must be "ubuntu" or "fedora".',
            ),
        ],
        handler=_timer_list,
        read_only=True,
    ),
]
