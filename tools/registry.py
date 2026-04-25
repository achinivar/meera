"""Aggregate tool catalog and JSON serialization for prompts."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import tools.files as files_mod
import tools.packages as packages_mod
import tools.processes as processes_mod
import tools.screenshot as screenshot_mod
import tools.scheduler as scheduler_mod
import tools.system as system_mod
import tools.weather as weather_mod
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_ok


def _ping(params: Mapping[str, Any]) -> ToolResult:
    return tool_result_ok("pong", data={"distro": params["distro"]})


PING_TOOL = ToolSpec(
    name="ping",
    description="No-op connectivity check; returns pong and resolved distro.",
    parameters=[],
    handler=_ping,
    read_only=True,
)


def _collect_tools() -> list[ToolSpec]:
    merged: list[ToolSpec] = [
        PING_TOOL,
        *system_mod.TOOLS,
        *files_mod.TOOLS,
        *processes_mod.TOOLS,
        *packages_mod.TOOLS,
        *scheduler_mod.TOOLS,
        *screenshot_mod.TOOLS,
        *weather_mod.TOOLS,
    ]
    names = [t.name for t in merged]
    seen: set[str] = set()
    for n in names:
        if n in seen:
            raise RuntimeError(f"Duplicate tool name in registry: {n!r}")
        seen.add(n)
    return merged


TOOLS: list[ToolSpec] = _collect_tools()


def get_tool(name: str) -> ToolSpec | None:
    for spec in TOOLS:
        if spec.name == name:
            return spec
    return None


def _prompt_param_manifest(p: ToolParam) -> dict[str, Any]:
    # Do not emit "default" here — tiny models often mirror it as a bogus params key (e.g.
    # {"default":"~"}) which fails validation. Describe defaults only in `description`.
    d: dict[str, Any] = {"name": p.name, "type": p.param_type, "required": p.required}
    if p.description:
        d["description"] = p.description
    return d


def _prompt_spec_dict(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters": [_prompt_param_manifest(p) for p in spec.parameters],
    }


def tools_prompt_catalog_json() -> str:
    payload = {"tools": [_prompt_spec_dict(t) for t in TOOLS]}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
