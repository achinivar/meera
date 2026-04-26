"""System tools: Wi-Fi, brightness, volume (read-mostly)."""
from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from datetime import datetime as _dt
from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok
from zoneinfo import ZoneInfo


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


def _volume_set_percent(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    percent = params["percent"]
    if not (0 <= percent <= 100):
        return tool_result_err(
            "percent must be between 0 and 100",
            "VALIDATION_ERROR",
        )
    frac = f"{percent / 100:.2f}"
    if shutil.which("wpctl"):
        r = run_argv(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", frac], timeout=10.0)
    elif shutil.which("pactl"):
        r = run_argv(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"], timeout=10.0)
    else:
        return tool_result_err(
            "Neither wpctl nor pactl found",
            "COMMAND_NOT_FOUND",
        )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"Command failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Volume set to {percent}%", data={"percent": percent})


def _volume_mute_toggle(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    state = params["state"]
    if state not in ("mute", "unmute", "toggle"):
        return tool_result_err(
            "state must be 'mute', 'unmute', or 'toggle'",
            "VALIDATION_ERROR",
        )
    if shutil.which("wpctl"):
        # wpctl: 1 / 0 / toggle
        wpctl_arg = {"mute": "1", "unmute": "0", "toggle": "toggle"}[state]
        r = run_argv(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", wpctl_arg], timeout=10.0)
    elif shutil.which("pactl"):
        # pactl: yes / no / toggle
        pactl_arg = {"mute": "yes", "unmute": "no", "toggle": "toggle"}[state]
        r = run_argv(["pactl", "set-sink-mute", "@DEFAULT_SINK@", pactl_arg], timeout=10.0)
    else:
        return tool_result_err(
            "Neither wpctl nor pactl found",
            "COMMAND_NOT_FOUND",
        )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"Command failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Volume mute state set to {state}", data={"state": state})


def _volume_adjust(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    direction = params["direction"]
    percent = params["percent"]
    if direction not in ("up", "down"):
        return tool_result_err(
            "direction must be 'up' or 'down'",
            "VALIDATION_ERROR",
        )
    if not (1 <= percent <= 100):
        return tool_result_err(
            "percent must be between 1 and 100",
            "VALIDATION_ERROR",
        )
    sign = "+" if direction == "up" else "-"
    frac = f"{percent / 100:.2f}"
    if shutil.which("wpctl"):
        r = run_argv(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{frac}{sign}"], timeout=10.0)
    elif shutil.which("pactl"):
        r = run_argv(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%{sign}"], timeout=10.0)
    else:
        return tool_result_err(
            "Neither wpctl nor pactl found",
            "COMMAND_NOT_FOUND",
        )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"Command failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(
        f"Volume {'increased' if direction == 'up' else 'decreased'} by {percent}%",
        data={"direction": direction, "percent": percent},
    )


def _brightness_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    action = params["action"]
    value = params["value"]
    if action not in ("set", "up", "down"):
        return tool_result_err(
            "action must be 'set', 'up', or 'down'",
            "VALIDATION_ERROR",
        )
    if not (0 <= value <= 100):
        return tool_result_err(
            "value must be between 0 and 100",
            "VALIDATION_ERROR",
        )

    if action == "set":
        if shutil.which("brightnessctl"):
            r = run_argv(["brightnessctl", "set", f"{value}%"], timeout=10.0)
            if isinstance(r, ToolResult):
                return r
        else:
            sysfs = _brightness_sysfs()
            if isinstance(sysfs, ToolResult) and not sysfs.ok:
                return sysfs
            if sysfs is None:
                return tool_result_err(
                    "Cannot set brightness: no brightnessctl found and no readable "
                    "sysfs backlight device. Install 'brightnessctl' for polkit-based control.",
                    "COMMAND_NOT_FOUND",
                )
            data = sysfs.data
            mx = data["max_brightness"]
            target = round(mx * value / 100)
            dev = data["device"]
            bright_path = Path(f"/sys/class/backlight/{dev}/brightness")
            try:
                bright_path.write_text(str(target), encoding="utf-8")
            except PermissionError:
                return tool_result_err(
                    "Cannot write brightness without root. Run Meera with appropriate "
                    "permissions or install 'brightnessctl' for polkit-based control.",
                    "PERMISSION_DENIED",
                    data={"device": dev, "target": target},
                )
            return tool_result_ok(
                f"Brightness set to ~{value}% via sysfs ({dev})",
                data={"backend": "sysfs", "percent": value, "device": dev},
            )

        if r.returncode != 0:
            return tool_result_err(
                f"brightnessctl failed: {r.stderr or r.stdout}",
                "COMMAND_FAILED",
            )
        return tool_result_ok(
            f"Brightness set to {value}%",
            data={"backend": "brightnessctl", "percent": value},
        )

    direction = "+" if action == "up" else "-"
    r = run_argv(["brightnessctl", "s", f"{value}%{direction}"], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"brightnessctl failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(
        f"Brightness {'increased' if action == 'up' else 'decreased'} by {value}%",
        data={"backend": "brightnessctl", "action": action, "value": value},
    )


def _wifi_toggle(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    state = params["state"]
    if state not in ("on", "off"):
        return tool_result_err(
            "state must be 'on' or 'off'",
            "VALIDATION_ERROR",
        )
    r = run_argv(["nmcli", "radio", "wifi", state], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"nmcli failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Wi-Fi turned {state}", data={"state": state})


def _system_info(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    data: dict[str, Any] = {}

    r = run_argv(["uptime", "-p"], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode == 0:
        data["uptime"] = r.stdout.strip()

    data["cpu_temp_c"] = None
    temp_found = False
    thermal_roots = sorted(Path("/sys/class/thermal").iterdir()) if Path("/sys/class/thermal").is_dir() else []
    for entry in thermal_roots:
        if not entry.is_dir():
            continue
        temp_file = entry / "temp"
        if not temp_file.is_file():
            continue
        try:
            raw = int(temp_file.read_text(encoding="utf-8", errors="replace").strip())
            data["cpu_temp_c"] = round(raw / 1000, 1)
            temp_found = True
            break
        except (ValueError, OSError, PermissionError):
            continue

    r = run_argv(["cat", "/proc/loadavg"], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode == 0:
        parts = r.stdout.strip().split()
        data["load_average"] = {
            "1m": float(parts[0]) if len(parts) > 0 else None,
            "5m": float(parts[1]) if len(parts) > 1 else None,
            "15m": float(parts[2]) if len(parts) > 2 else None,
        }

    note = "CPU temp unavailable (no accessible thermal zone)" if not temp_found else None
    data["notes"] = note
    return tool_result_ok("System info retrieved", data=data)


def _disk_space(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(["df", "-h", "--total", "-T"], timeout=15.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"df failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    lines = r.stdout.strip().splitlines()
    return tool_result_ok(
        f"Disk usage: {len(lines) - 1} filesystem(s) listed",
        data={"raw": r.stdout.strip(), "lines": lines},
    )


def _network_info(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    data: dict[str, Any] = {}

    route_r = run_argv(["ip", "-o", "route", "get", "8.8.8.8"], timeout=10.0)
    default_iface = None
    if not isinstance(route_r, ToolResult) and route_r.returncode == 0:
        parts = route_r.stdout.strip().split()
        for i, part in enumerate(parts):
            if part == "dev" and i + 1 < len(parts):
                default_iface = parts[i + 1]
                break

    addr_r = run_argv(["ip", "-br", "addr"], timeout=10.0)
    if isinstance(addr_r, ToolResult):
        return addr_r
    if addr_r.returncode != 0:
        return tool_result_err(
            f"ip addr failed: {addr_r.stderr or addr_r.stdout}",
            "COMMAND_FAILED",
        )
    data["interfaces"] = addr_r.stdout.strip().splitlines()

    if default_iface:
        data["default_interface"] = default_iface
        speed_path = Path(f"/sys/class/net/{default_iface}/speed")
        try:
            data["link_speed_mbps"] = int(speed_path.read_text(encoding="utf-8", errors="replace").strip())
        except (ValueError, OSError, PermissionError):
            data["link_speed_mbps"] = None
            data["link_speed_note"] = (
                f"Could not read speed for {default_iface} (common for wireless interfaces)"
            )

    return tool_result_ok("Network info retrieved", data=data)


def _datetime_query(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    timezone = params.get("timezone")
    fmt = params.get("format", "long")
    if fmt not in ("short", "long"):
        fmt = "long"

    try:
        tz = ZoneInfo(timezone) if timezone else None
        now = _dt.now(tz)
        tz_name = str(now.tzinfo) if now.tzinfo else "system local time"
    except Exception as e:
        return tool_result_err(
            f"Invalid timezone '{timezone}': {e}",
            "VALIDATION_ERROR",
        )

    if fmt == "short":
        display = now.strftime("%H:%M")
    else:
        display = now.strftime("%A, %B %d, %Y at %H:%M:%S %Z")

    return tool_result_ok(
        f"Current time: {display}",
        data={"formatted": display, "timezone": tz_name},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="wifi_list_networks",
        description="List visible Wi-Fi SSIDs (nmcli).",
        parameters=[],
        handler=_wifi_list_networks,
        read_only=True,
        exemplars=[
            "list available wifi networks",
            "what wifi networks can I see",
            "show me nearby wifi",
            "scan for wireless networks",
            "what wireless networks are around",
            "find wifi networks in range",
            "show visible SSIDs",
        ],
    ),
    ToolSpec(
        name="wifi_status",
        description="Show Wi-Fi device connection state (nmcli).",
        parameters=[],
        handler=_wifi_status,
        read_only=True,
        exemplars=[
            "am I connected to wifi",
            "what's my wifi status",
            "show wifi connection",
            "what wifi network am I on",
            "wifi connection details",
            "is wifi connected right now",
            "show me my wireless connection",
        ],
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
        exemplars=[
            "what's my screen brightness",
            "how bright is my screen",
            "show current brightness",
            "what is the brightness level",
            "check screen brightness",
            "tell me the brightness percentage",
        ],
    ),
    ToolSpec(
        name="volume_get",
        description="Read default audio sink volume (wpctl or pactl).",
        parameters=[],
        handler=_volume_get,
        read_only=True,
        exemplars=[
            "what's the volume",
            "how loud is it",
            "show current volume",
            "tell me the volume level",
            "check the volume",
            "what volume am I at",
            "is the audio muted",
        ],
    ),
    ToolSpec(
        name="volume_set_percent",
        description="Set volume to a percentage (0-100). Uses wpctl if available, else pactl.",
        parameters=[
            ToolParam(name="percent", param_type="integer", required=True, description="Volume percentage (0-100)"),
        ],
        handler=_volume_set_percent,
        read_only=False,
        exemplars=[
            "set volume to 50",
            "make the volume 30 percent",
            "change volume to 75",
            "volume to 100",
            "set audio to 25%",
            "put the volume at 60",
            "volume 40 please",
        ],
    ),
    ToolSpec(
        name="volume_mute_toggle",
        description="Toggle mute state. State can be 'mute', 'unmute', or 'toggle'.",
        parameters=[
            ToolParam(name="state", param_type="string", required=True, description="One of: mute, unmute, toggle"),
        ],
        handler=_volume_mute_toggle,
        read_only=False,
        exemplars=[
            "mute the volume",
            "unmute",
            "silence the audio",
            "stop muting",
            "toggle mute",
            "turn off the sound",
            "mute audio",
        ],
    ),
    ToolSpec(
        name="volume_adjust",
        description="Adjust volume relatively (increase or decrease by a percentage).",
        parameters=[
            ToolParam(name="direction", param_type="string", required=True, description="One of: up, down"),
            ToolParam(name="percent", param_type="integer", required=True, description="Percentage to adjust by (1-100)"),
        ],
        handler=_volume_adjust,
        read_only=False,
        exemplars=[
            "make it louder",
            "turn down the volume",
            "increase volume by 20",
            "decrease volume by 10",
            "make it quieter",
            "turn it up",
            "lower the volume a bit",
            "louder please",
        ],
    ),
    ToolSpec(
        name="brightness_set",
        description=(
            "Set or adjust brightness. Action 'set' sets absolute percent; 'up'/'down' adjust by value percent."
        ),
        parameters=[
            ToolParam(name="action", param_type="string", required=True, description="One of: set, up, down"),
            ToolParam(name="value", param_type="integer", required=True, description="Percent value (0-100)"),
        ],
        handler=_brightness_set,
        read_only=False,
        exemplars=[
            "make my screen brighter",
            "dim the screen",
            "set brightness to 50",
            "increase brightness",
            "lower brightness",
            "brightness to 80%",
            "make the display dimmer",
            "screen too bright, turn it down",
        ],
    ),
    ToolSpec(
        name="wifi_toggle",
        description="Turn Wi-Fi on or off using nmcli.",
        parameters=[
            ToolParam(name="state", param_type="string", required=True, description="One of: on, off"),
        ],
        handler=_wifi_toggle,
        read_only=False,
        exemplars=[
            "turn wifi on",
            "turn off wifi",
            "disable wireless",
            "enable wifi",
            "switch wifi off",
            "shut down wifi",
            "wifi on please",
        ],
    ),
    ToolSpec(
        name="system_info",
        description="Get system info: uptime, CPU temperature, and load average.",
        parameters=[],
        handler=_system_info,
        read_only=True,
        exemplars=[
            "show system info",
            "what's the system status",
            "tell me about my system",
            "uptime and load",
            "how is my system doing",
            "show me CPU temperature",
            "what's the load average",
            "system health check",
        ],
    ),
    ToolSpec(
        name="disk_space",
        description="Show disk usage summary using df.",
        parameters=[],
        handler=_disk_space,
        read_only=True,
        exemplars=[
            "how much disk space do I have",
            "show disk usage",
            "check free space on disk",
            "is my disk full",
            "disk space usage",
            "how full are my drives",
            "df please",
        ],
    ),
    ToolSpec(
        name="network_info",
        description="Show network info: IP addresses, default interface, and link speed.",
        parameters=[],
        handler=_network_info,
        read_only=True,
        exemplars=[
            "what's my IP address",
            "show network info",
            "network details",
            "what network am I on",
            "show my IP and interface",
            "what's my link speed",
            "ifconfig",
        ],
    ),
    ToolSpec(
        name="datetime_query",
        description="Get current date/time, optionally in a specific timezone.",
        parameters=[
            ToolParam(name="timezone", param_type="string", required=False, description="IANA timezone (e.g. Asia/Tokyo)"),
            ToolParam(name="format", param_type="string", required=False, description="One of: short, long", default="long"),
        ],
        handler=_datetime_query,
        read_only=True,
        exemplars=[
            "what time is it",
            "what's the date today",
            "current date and time",
            "what day is it",
            "show me the time",
            "tell me the time in Tokyo",
            "what time is it in London",
            "today's date",
        ],
    ),
]
