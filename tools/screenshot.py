"""Screenshot tool — capture desktop via gnome-screenshot or scrot."""
from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _screenshot_save(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    directory = params.get("directory") or os.path.expanduser("~/Pictures")
    directory = os.path.expanduser(directory)
    filename = params.get("filename")

    if filename:
        if "/" in filename or ".." in filename:
            return tool_result_err(
                "filename must not contain path separators or '..'",
                "VALIDATION_ERROR",
            )
        dest = os.path.join(directory, str(filename))
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(directory, f"screenshot-{ts}.png")

    dest = os.path.abspath(dest)
    dirpath = os.path.dirname(dest)
    os.makedirs(dirpath, exist_ok=True)

    tool = shutil.which("gnome-screenshot") or shutil.which("scrot")
    if not tool:
        return tool_result_err(
            "No screenshot tool found. Install gnome-screenshot or scrot.",
            "COMMAND_NOT_FOUND",
        )

    r = run_argv([tool, "-f", dest], timeout=15.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"Screenshot command failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )

    return tool_result_ok(
        f"Screenshot saved successfully",
        data={"path": dest},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="screenshot_save",
        description=(
            "Take a screenshot and save it to disk. Uses gnome-screenshot if available,"
            " falls back to scrot. Auto-generates a timestamped filename if none provided."
        ),
        parameters=[
            ToolParam(
                name="directory",
                param_type="string",
                required=False,
                description="Directory to save the screenshot; defaults to ~/Pictures.",
                default="~/Pictures",
            ),
            ToolParam(
                name="filename",
                param_type="string",
                required=False,
                description=(
                    "Optional filename (no path separators). If omitted, a timestamped "
                    "name like screenshot-20250115-143000.png is generated."
                ),
            ),
        ],
        handler=_screenshot_save,
        read_only=False,
    ),
]
