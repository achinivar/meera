"""Aggregate tool catalog and JSON manifest for Phase 3 prompts."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import tools.files as files_mod
import tools.packages as packages_mod
import tools.processes as processes_mod
import tools.scheduler as scheduler_mod
import tools.system as system_mod
from tools.schema import (
    TOOLS_SCHEMA_VERSION,
    ToolParam,
    ToolResult,
    ToolSpec,
    tool_result_ok,
)


def _ping(params: Mapping[str, Any]) -> ToolResult:
    return tool_result_ok("pong", data={"distro": params["distro"]})


PING_TOOL = ToolSpec(
    name="ping",
    description="No-op connectivity check; returns pong and resolved distro.",
    parameters=[
        ToolParam(
            name="distro",
            param_type="string",
            required=True,
            description='Must be "ubuntu" or "fedora" (runner injects from /etc/os-release if omitted).',
        ),
    ],
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


def _param_manifest(p: ToolParam) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": p.name,
        "type": p.param_type,
        "required": p.required,
        "description": p.description,
    }
    if p.default is not None:
        d["default"] = p.default
    return d


def _spec_manifest_dict(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters": [_param_manifest(p) for p in spec.parameters],
        "requires_elevation": spec.requires_elevation,
        "read_only": spec.read_only,
    }


def tools_manifest_json() -> str:
    payload = {
        "schema_version": TOOLS_SCHEMA_VERSION,
        "tools": [_spec_manifest_dict(t) for t in TOOLS],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
