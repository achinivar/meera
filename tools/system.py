"""System tools: Wi-Fi, brightness, volume (read-mostly)."""
from __future__ import annotations

import shutil
from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _distro_params(extra: list[ToolParam]) -> list[ToolParam]:
    base = [
        ToolParam(
            name="distro",
            param_type="string",
            required=True,
            description='Must be "ubuntu" or "fedora" (runner injects from /etc/os-release if omitted).',
        ),
    ]
    return base + extra


def _wifi_list_networks(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(["nmcli", "-t", "-f", "SSID,SECURITY,SIGNAL", "dev", "wifi", "list"], timeout=20.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"nmcli failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
            data={"stderr": r.stderr},
        )
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    return tool_result_ok(f"{len(lines)} Wi-Fi network(s) visible", data={"lines": lines[:200]})


def _wifi_status(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        ["nmcli", "-t", "-f", "STATE,CONNECTION", "dev", "wifi"],
        timeout=15.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"nmcli failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok("Wi-Fi device status", data={"raw": r.stdout.strip()})


def _brightness_get(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    if not shutil.which("brightnessctl"):
        return tool_result_err(
            "brightnessctl not installed",
            "COMMAND_NOT_FOUND",
        )
    r = run_argv(["brightnessctl", "get"], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            r.stderr or r.stdout or "brightnessctl failed",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Brightness: {r.stdout.strip()}", data={"raw": r.stdout.strip()})


def _volume_get(params: Mapping[str, Any]) -> ToolResult:
    distro = params["distro"]
    # Probe order: wpctl first, then pactl (distro hints only tweak messaging)
    if shutil.which("wpctl"):
        r = run_argv(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], timeout=10.0)
        if not isinstance(r, ToolResult) and r.returncode == 0:
            return tool_result_ok(
                f"Volume (wpctl): {r.stdout.strip()}",
                data={"backend": "wpctl", "raw": r.stdout.strip(), "distro": distro},
            )
    if shutil.which("pactl"):
        r = run_argv(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], timeout=10.0)
        if isinstance(r, ToolResult):
            return r
        if r.returncode == 0:
            return tool_result_ok(
                f"Volume (pactl): {r.stdout.strip()}",
                data={"backend": "pactl", "raw": r.stdout.strip(), "distro": distro},
            )
        return tool_result_err(
            r.stderr or r.stdout or "pactl failed",
            "COMMAND_FAILED",
        )
    return tool_result_err(
        "Neither wpctl nor pactl found",
        "COMMAND_NOT_FOUND",
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="wifi_list_networks",
        description="List visible Wi-Fi SSIDs (nmcli).",
        parameters=_distro_params([]),
        handler=_wifi_list_networks,
        read_only=True,
    ),
    ToolSpec(
        name="wifi_status",
        description="Show Wi-Fi device connection state (nmcli).",
        parameters=_distro_params([]),
        handler=_wifi_status,
        read_only=True,
    ),
    ToolSpec(
        name="brightness_get",
        description="Read display backlight level via brightnessctl.",
        parameters=_distro_params([]),
        handler=_brightness_get,
        read_only=True,
    ),
    ToolSpec(
        name="volume_get",
        description="Read default audio sink volume (wpctl or pactl).",
        parameters=_distro_params([]),
        handler=_volume_get,
        read_only=True,
    ),
]
