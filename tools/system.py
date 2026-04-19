"""System tools: Wi-Fi, brightness, volume (read-mostly)."""
from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


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
    # `nmcli device wifi` alone is invalid — it requires e.g. `list`. Use device table for Wi‑Fi rows.
    r = run_argv(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
        timeout=15.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"nmcli failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
            data={"stderr": r.stderr, "stdout": r.stdout},
        )
    lines = [
        ln.strip()
        for ln in r.stdout.splitlines()
        if ln.strip() and _line_looks_like_wifi_device(ln)
    ]
    if not lines:
        # NetworkManager may use different TYPE strings; fall back to full table.
        fallback = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        body = "\n".join(fallback[:50])
        return tool_result_ok(
            "Wi-Fi lines not detected in nmcli output; full device table",
            data={"raw": body, "note": "no wifi/wlan/802.11 row matched"},
        )
    return tool_result_ok(
        "Wi-Fi device status (NetworkManager)",
        data={"lines": lines[:50], "raw": "\n".join(lines)},
    )


def _line_looks_like_wifi_device(line: str) -> bool:
    # -t lines are DEVICE:TYPE:STATE:CONNECTION (SSID may contain ':').
    parts = line.split(":", 3)
    if len(parts) < 2:
        return False
    t = parts[1].lower().strip()
    return (
        "wifi" in t
        or "802.11" in t
        or t == "wlan"
        or ("wireless" in t and "ethernet" not in t)
    )


def _brightness_sysfs() -> ToolResult | None:
    """Read backlight from /sys/class/backlight (no brightnessctl needed on many laptops)."""
    root = Path("/sys/class/backlight")
    if not root.is_dir():
        return None
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        bright = entry / "brightness"
        mxp = entry / "max_brightness"
        if not (bright.is_file() and mxp.is_file()):
            continue
        try:
            cur_s = bright.read_text(encoding="utf-8", errors="replace").strip()
            mx_s = mxp.read_text(encoding="utf-8", errors="replace").strip()
            cur = int(cur_s)
            mx = int(mx_s)
            pct = round(100.0 * cur / mx) if mx > 0 else None
        except PermissionError:
            return tool_result_err(
                f"Permission denied reading backlight sysfs files under {entry}",
                "PERMISSION_DENIED",
                data={"path": str(entry)},
            )
        except (ValueError, OSError):
            continue
        return tool_result_ok(
            f"Backlight ~{pct}% ({entry.name}, sysfs)",
            data={
                "backend": "sysfs",
                "device": entry.name,
                "brightness": cur,
                "max_brightness": mx,
                "percent_approx": pct,
            },
        )
    return None


def _brightness_get(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    bc_err: ToolResult | None = None
    if shutil.which("brightnessctl"):
        r = run_argv(["brightnessctl", "get"], timeout=10.0)
        if isinstance(r, ToolResult):
            return r
        if r.returncode == 0:
            return tool_result_ok(
                f"Brightness: {r.stdout.strip()}",
                data={"backend": "brightnessctl", "raw": r.stdout.strip()},
            )
        bc_err = tool_result_err(
            r.stderr or r.stdout or "brightnessctl failed",
            "COMMAND_FAILED",
        )

    sysfs = _brightness_sysfs()
    if sysfs is not None:
        return sysfs

    if bc_err is not None:
        return bc_err

    return tool_result_err(
        "Cannot read backlight: no working /sys/class/backlight device on this machine and "
        "`brightnessctl` is not installed. Install package `brightnessctl` if you want that "
        "helper; many desktops and HDMI-only setups expose no Linux backlight API.",
        "COMMAND_NOT_FOUND",
        data={"checked_sysfs": "/sys/class/backlight"},
    )


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
        parameters=[],
        handler=_wifi_list_networks,
        read_only=True,
    ),
    ToolSpec(
        name="wifi_status",
        description="Show Wi-Fi device connection state (nmcli).",
        parameters=[],
        handler=_wifi_status,
        read_only=True,
    ),
    ToolSpec(
        name="brightness_get",
        description=(
            "Read internal panel backlight: tries brightnessctl if installed, else sysfs "
            "/sys/class/backlight. May fail on desktops or external-only displays (no API)."
        ),
        parameters=[],
        handler=_brightness_get,
        read_only=True,
    ),
    ToolSpec(
        name="volume_get",
        description="Read default audio sink volume (wpctl or pactl).",
        parameters=[],
        handler=_volume_get,
        read_only=True,
    ),
]
