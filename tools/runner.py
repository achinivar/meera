"""Validate parameters and dispatch tool handlers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools.platform import DistroUnknownError, detect_distro
from tools.registry import get_tool
from tools.schema import ToolResult, ToolSpec, tool_result_err


_MAX_STRING_PARAM_LEN = 8192


def _coerce_param(spec: ToolSpec, pname: str, raw: Any) -> Any | ToolResult:
    param = next((p for p in spec.parameters if p.name == pname), None)
    if param is None:
        return tool_result_err(f"Unknown parameter: {pname}", "VALIDATION_ERROR")

    if param.param_type == "string":
        s = raw if isinstance(raw, str) else str(raw)
        if len(s) > _MAX_STRING_PARAM_LEN:
            return tool_result_err(
                f"Parameter {pname!r} exceeds max length",
                "VALIDATION_ERROR",
            )
        return s
    if param.param_type == "integer":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return tool_result_err(
                f"Parameter {pname!r} must be an integer",
                "VALIDATION_ERROR",
            )
    if param.param_type == "boolean":
        if isinstance(raw, bool):
            return raw
        if raw in (0, 1, "0", "1", "true", "false", "True", "False"):
            if raw in ("false", "False", 0, "0"):
                return False
            if raw in ("true", "True", 1, "1"):
                return True
        return tool_result_err(
            f"Parameter {pname!r} must be a boolean",
            "VALIDATION_ERROR",
        )
    return tool_result_err(
        f"Unsupported parameter type: {param.param_type!r}",
        "VALIDATION_ERROR",
    )


def _build_validated_params(spec: ToolSpec, params: Mapping[str, Any]) -> dict[str, Any] | ToolResult:
    out: dict[str, Any] = {}
    allowed = {p.name for p in spec.parameters}
    for key in params:
        if key not in allowed:
            return tool_result_err(f"Unexpected parameter: {key!r}", "VALIDATION_ERROR")

    for p in spec.parameters:
        if p.name in params:
            coerced = _coerce_param(spec, p.name, params[p.name])
            if isinstance(coerced, ToolResult):
                return coerced
            out[p.name] = coerced
        elif p.required:
            return tool_result_err(
                f"Missing required parameter: {p.name!r}",
                "VALIDATION_ERROR",
            )
        elif p.default is not None:
            out[p.name] = p.default
        else:
            out[p.name] = None
    return out


def run_tool(
    name: str,
    params: dict[str, Any] | None = None,
    *,
    allow_elevation: bool = False,
) -> ToolResult:
    spec = get_tool(name)
    if spec is None:
        return tool_result_err(f"Unknown tool: {name!r}", "UNKNOWN_TOOL")

    raw = dict(params or {})

    try:
        host_distro = detect_distro()
    except DistroUnknownError as e:
        return tool_result_err(str(e), "DISTRO_UNKNOWN")

    if "distro" in raw:
        d = raw["distro"]
        if not isinstance(d, str):
            d = str(d)
        if d != host_distro:
            return tool_result_err(
                f"distro mismatch: params={d!r} host={host_distro!r}",
                "DISTRO_MISMATCH",
            )
        raw["distro"] = d
    else:
        raw["distro"] = host_distro

    if spec.requires_elevation and not allow_elevation:
        return tool_result_err(
            "Tool requires elevation; execution denied",
            "ELEVATION_DENIED",
        )

    validated = _build_validated_params(spec, raw)
    if isinstance(validated, ToolResult):
        return validated

    try:
        return spec.handler(validated)
    except Exception as e:  # noqa: BLE001 — boundary: never leak tracebacks to callers
        return tool_result_err(str(e), "INTERNAL_ERROR")
