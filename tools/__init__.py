"""Meera Phase 2 tool layer: catalog, manifest, and safe execution."""
from __future__ import annotations

from tools.platform import DistroUnknownError, detect_distro
from tools.registry import TOOLS, get_tool, tools_prompt_catalog_json
from tools.runner import run_tool
from tools.schema import (
    ToolParam,
    ToolResult,
    ToolSpec,
    tool_result_err,
    tool_result_ok,
)

__all__ = [
    "TOOLS",
    "DistroUnknownError",
    "ToolParam",
    "ToolResult",
    "ToolSpec",
    "detect_distro",
    "get_tool",
    "run_tool",
    "tool_result_err",
    "tool_result_ok",
    "tools_prompt_catalog_json",
]
