"""Meera Phase 2 tool layer: catalog, manifest, and safe execution."""
from __future__ import annotations

from tools.platform import DistroUnknownError, detect_distro
from tools.registry import TOOLS, get_tool, tools_manifest_json
from tools.runner import run_tool
from tools.schema import (
    TOOLS_SCHEMA_VERSION,
    ToolParam,
    ToolResult,
    ToolSpec,
    tool_result_err,
    tool_result_ok,
)

__all__ = [
    "TOOLS",
    "TOOLS_SCHEMA_VERSION",
    "DistroUnknownError",
    "ToolParam",
    "ToolResult",
    "ToolSpec",
    "detect_distro",
    "get_tool",
    "run_tool",
    "tool_result_err",
    "tool_result_ok",
    "tools_manifest_json",
]
