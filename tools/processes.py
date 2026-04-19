"""Process listing (read-only)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _process_list(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    limit = int(params.get("limit") or 25)
    limit = max(1, min(limit, 100))

    r = run_argv(
        [
            "ps",
            "-eo",
            "pid,comm,%cpu,%mem",
            "--sort=-%cpu",
            "--no-headers",
        ],
        timeout=15.0,
    )
    if isinstance(r, ToolResult):
        return r
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()][:limit]
    return tool_result_ok(
        f"Top {len(lines)} processes by CPU",
        data={"processes": lines},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="process_list",
        description="List top processes by CPU use (ps).",
        parameters=[
            ToolParam(
                name="limit",
                param_type="integer",
                required=False,
                description="Max rows (1–100)",
                default=25,
            ),
        ],
        handler=_process_list,
        read_only=True,
    ),
]
