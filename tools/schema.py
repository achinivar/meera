"""Tool metadata and execution results (Phase 2)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    name: str
    param_type: str  # "string" | "integer" | "boolean"
    required: bool
    description: str
    default: Any = None


@dataclass
class ToolResult:
    ok: bool
    message: str
    data: Any = None
    error_code: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: list[ToolParam]
    handler: Callable[[Mapping[str, Any]], ToolResult]
    requires_elevation: bool = False
    read_only: bool = True
    # Natural-language utterances that should map to this tool. Used by the
    # retrieval index (Phase 4) to narrow tool candidates before the LLM call.
    # Add 5-10 paraphrased examples per tool; tests/test_tools.py enforces a minimum.
    exemplars: list[str] = field(default_factory=list)


def tool_result_ok(message: str, data: Any = None) -> ToolResult:
    return ToolResult(ok=True, message=message, data=data, error_code=None)


def tool_result_err(message: str, error_code: str, data: Any = None) -> ToolResult:
    return ToolResult(ok=False, message=message, data=data, error_code=error_code)
