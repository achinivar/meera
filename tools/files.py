"""Safe filesystem tools."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _resolve_under_home(path_str: str) -> Path | ToolResult:
    raw = (path_str or "").strip() or "~"
    expanded = Path(os.path.expanduser(raw)).resolve()
    home = Path.home().resolve()
    try:
        expanded.relative_to(home)
    except ValueError:
        return tool_result_err(
            f"Path must stay under home directory: {home}",
            "VALIDATION_ERROR",
        )
    if ".." in Path(path_str).parts:
        return tool_result_err("Path must not contain '..'", "VALIDATION_ERROR")
    return expanded


def _file_list_dir(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    path_str = str(params.get("path") or "~")
    max_entries = int(params.get("max_entries") or 200)
    max_entries = max(1, min(max_entries, 500))

    resolved = _resolve_under_home(path_str)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return tool_result_err(f"Not a directory: {resolved}", "VALIDATION_ERROR")

    names: list[str] = []
    try:
        for i, entry in enumerate(sorted(resolved.iterdir(), key=lambda p: p.name.lower())):
            if i >= max_entries:
                names.append(f"…({max_entries} cap)")
                break
            suffix = "/" if entry.is_dir() else ""
            names.append(entry.name + suffix)
    except OSError as e:
        return tool_result_err(str(e), "OS_ERROR")

    return tool_result_ok(
        f"{len(names)} entries in {resolved}",
        data={"path": str(resolved), "entries": names},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="file_list_dir",
        description="List files in a directory under the user's home (non-recursive).",
        parameters=[
            ToolParam(
                name="path",
                param_type="string",
                required=False,
                description="Optional directory under home to list; omit for home (~).",
                default="~",
            ),
            ToolParam(
                name="max_entries",
                param_type="integer",
                required=False,
                description="Max entries (1–500)",
                default=200,
            ),
        ],
        handler=_file_list_dir,
        read_only=True,
    ),
]
