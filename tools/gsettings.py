"""GNOME gsettings tools: Night Light, color scheme, Do Not Disturb, window UI."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


# ---- Night Light ----

def _night_light_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    state = params["state"]
    if state not in ("on", "off"):
        return tool_result_err("state must be 'on' or 'off'", "VALIDATION_ERROR")

    value = "true" if state == "on" else "false"
    r = run_argv(
        ["gsettings", "set", "org.gnome.settings-daemon.plugins.color",
         "night-light-enabled", value],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Night Light turned {state}", data={"state": state})


def _night_light_status(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        ["gsettings", "get", "org.gnome.settings-daemon.plugins.color",
         "night-light-enabled"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    enabled = r.stdout.strip() == "true"
    return tool_result_ok(
        f"Night Light is {'on' if enabled else 'off'}",
        data={"enabled": enabled},
    )


# ---- Color Scheme (Dark / Light mode) ----

def _color_scheme_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    mode = params["mode"]
    if mode not in ("dark", "light"):
        return tool_result_err("mode must be 'dark' or 'light'", "VALIDATION_ERROR")

    value = "prefer-dark" if mode == "dark" else "default"
    r = run_argv(
        ["gsettings", "set", "org.gnome.desktop.interface",
         "color-scheme", value],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Switched to {mode} mode", data={"mode": mode})


def _color_scheme_status(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    raw = r.stdout.strip().strip("'")
    is_dark = "dark" in raw
    return tool_result_ok(
        f"Current color scheme: {'dark' if is_dark else 'light'} mode",
        data={"raw": raw, "is_dark": is_dark},
    )


# ---- Do Not Disturb ----

def _dnd_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    state = params["state"]
    if state not in ("on", "off"):
        return tool_result_err("state must be 'on' or 'off'", "VALIDATION_ERROR")

    # show-banners=false means DND is enabled (no banners shown).
    value = "false" if state == "on" else "true"
    r = run_argv(
        ["gsettings", "set", "org.gnome.desktop.notifications",
         "show-banners", value],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(f"Do Not Disturb turned {state}", data={"state": state})


def _dnd_status(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        ["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    show_banners = r.stdout.strip() == "true"
    dnd_enabled = not show_banners
    return tool_result_ok(
        f"Do Not Disturb is {'on' if dnd_enabled else 'off'}",
        data={"enabled": dnd_enabled},
    )


# ---- Titlebar buttons (appmenu / minimize / maximize / close) ----

_TITLEBAR_BUTTONS = frozenset({"appmenu", "minimize", "maximize", "close"})
# When both sides are omitted, match the common "show min/max again" preset.
_TITLEBAR_LAYOUT_DEFAULT = "appmenu:minimize,maximize,close"


def _parse_titlebar_token_list(spec: str) -> list[str] | ToolResult:
    """Parse a comma-separated list of button names; empty segments skipped."""
    out: list[str] = []
    for part in spec.split(","):
        t = part.strip().lower()
        if not t:
            continue
        if t not in _TITLEBAR_BUTTONS:
            return tool_result_err(
                f"Unknown titlebar button {t!r}; allowed: "
                "appmenu, minimize, maximize, close",
                "VALIDATION_ERROR",
            )
        out.append(t)
    return out


def _build_titlebar_layout(left_raw: str | None, right_raw: str | None) -> str | ToolResult:
    """Build org.gnome.desktop.wm.preferences button-layout value.

    Each side is an ordered comma-separated subset; omit a name to hide that
    control. Left and right groups are separated by ':' (GNOME format).
    If both ``left`` and ``right`` are omitted (None), uses the classic preset
    ``appmenu:minimize,maximize,close``.
    """
    if left_raw is None and right_raw is None:
        return _TITLEBAR_LAYOUT_DEFAULT

    left_t = _parse_titlebar_token_list(left_raw or "")
    if isinstance(left_t, ToolResult):
        return left_t
    right_t = _parse_titlebar_token_list(right_raw or "")
    if isinstance(right_t, ToolResult):
        return right_t

    if not left_t and not right_t:
        return tool_result_err(
            "At least one titlebar button is required when left/right are given",
            "VALIDATION_ERROR",
        )
    combined = left_t + right_t
    if len(combined) != len(set(combined)):
        return tool_result_err(
            "Each titlebar button may appear at most once in the layout",
            "VALIDATION_ERROR",
        )

    return f"{','.join(left_t)}:{','.join(right_t)}"


def _titlebar_button_layout_set(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    layout = _build_titlebar_layout(
        params.get("left"),
        params.get("right"),
    )
    if isinstance(layout, ToolResult):
        return layout

    r = run_argv(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.wm.preferences",
            "button-layout",
            layout,
        ],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(
        f"Titlebar button-layout set to {layout!r}",
        data={"button_layout": layout},
    )


# ---- Alt+Tab: switch individual windows vs default (grouped-by-app) behavior ----


def _alt_tab_switch_windows_mode(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    mode = params["mode"]
    if mode == "traditional":
        value = "['<Alt>Tab']"
        label = "Alt+Tab cycles each window (switch-windows)"
    elif mode == "default":
        value = "[]"
        label = "switch-windows keybinding cleared (restore GNOME default grouping)"
    else:
        return tool_result_err(
            "mode must be 'traditional' or 'default'",
            "VALIDATION_ERROR",
        )

    r = run_argv(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.wm.keybindings",
            "switch-windows",
            value,
        ],
        timeout=10.0,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"gsettings failed: {r.stderr or r.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(label, data={"mode": mode, "switch_windows": value})


# ---- Tool registry ----

TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="night_light_set",
        description="Turn GNOME Night Light on or off.",
        parameters=[
            ToolParam(name="state", param_type="string", required=True,
                      description="One of: on, off"),
        ],
        handler=_night_light_set,
        read_only=False,
        exemplars=[
            "turn on night light",
            "turn off night light",
            "enable night light",
            "disable night light",
            "night light on",
            "night light off",
            "activate red night mode",
            "stop the red screen filter",
        ],
    ),
    ToolSpec(
        name="night_light_status",
        description="Check whether GNOME Night Light is currently enabled.",
        parameters=[],
        handler=_night_light_status,
        read_only=True,
        exemplars=[
            "is night light on",
            "is night light enabled",
            "check night light status",
            "is the red filter on",
            "what's my night light setting",
            "has night light been turned on",
        ],
    ),
    ToolSpec(
        name="color_scheme_set",
        description="Switch GNOME between dark and light color schemes.",
        parameters=[
            ToolParam(name="mode", param_type="string", required=True,
                      description="One of: dark, light"),
        ],
        handler=_color_scheme_set,
        read_only=False,
        exemplars=[
            "switch to dark mode",
            "switch to light mode",
            "turn on dark mode",
            "turn on light mode",
            "enable dark theme",
            "enable light theme",
            "dark mode please",
            "light mode please",
        ],
    ),
    ToolSpec(
        name="color_scheme_status",
        description="Check the current GNOME color scheme (dark or light mode).",
        parameters=[],
        handler=_color_scheme_status,
        read_only=True,
        exemplars=[
            "am I in dark mode",
            "am I in light mode",
            "is dark mode on",
            "what theme am I using",
            "do I have dark mode enabled",
        ],
    ),
    ToolSpec(
        name="dnd_set",
        description="Enable or disable GNOME Do Not Disturb mode.",
        parameters=[
            ToolParam(name="state", param_type="string", required=True,
                      description="One of: on, off"),
        ],
        handler=_dnd_set,
        read_only=False,
        exemplars=[
            "turn on do not disturb",
            "turn off do not disturb",
            "enable do not disturb",
            "disable do not disturb",
            "do not disturb on",
            "do not disturb off",
            "mute notifications",
            "stop notification banners",
        ],
    ),
    ToolSpec(
        name="dnd_status",
        description="Check whether GNOME Do Not Disturb is currently enabled.",
        parameters=[],
        handler=_dnd_status,
        read_only=True,
        exemplars=[
            "is do not disturb on",
            "is do not disturb enabled",
            "check do not disturb status",
            "are notifications muted",
            "is dnd on",
            "do I have do not disturb active",
        ],
    ),
    ToolSpec(
        name="gnome_titlebar_button_layout_set",
        description=(
            "Set GNOME window titlebar controls (button-layout). Optional comma-ordered "
            "parameters left and right use names: appmenu, minimize, maximize, close — "
            "omit a name to hide that button; order is preserved within each side. "
            "Omit both left and right to apply the common default appmenu:minimize,maximize,close."
        ),
        parameters=[
            ToolParam(
                name="left",
                param_type="string",
                required=False,
                default=None,
                description=(
                    "Comma-separated controls on the left of the titlebar (before ':'), "
                    "e.g. appmenu or empty side — omit parameter for no left controls when "
                    "right is set."
                ),
            ),
            ToolParam(
                name="right",
                param_type="string",
                required=False,
                default=None,
                description=(
                    "Comma-separated controls on the right, e.g. minimize,maximize,close — "
                    "omit parameter for no right controls when left is set."
                ),
            ),
        ],
        handler=_titlebar_button_layout_set,
        read_only=False,
        exemplars=[
            "show minimize and maximize buttons on windows",
            "enable window minimize maximize buttons gnome",
            "add minimize maximize to title bar",
            "I don't have minimize button gnome",
            "restore titlebar min max buttons",
            "gnome hide minimize maximize how to show them",
            "put minimize and maximize back on the window",
            "classic window buttons gnome",
            "titlebar only close button on the right",
            "put close before minimize gnome titlebar",
            "remove maximize button keep minimize and close",
        ],
    ),
    ToolSpec(
        name="gnome_alt_tab_switch_windows_mode",
        description=(
            "GNOME Alt+Tab behavior: traditional cycles every window via switch-windows; "
            "default clears that binding so the normal grouped-by-app Alt+Tab returns."
        ),
        parameters=[
            ToolParam(
                name="mode",
                param_type="string",
                required=True,
                description="One of: traditional (Alt+Tab switches each window), default (clear binding).",
            ),
        ],
        handler=_alt_tab_switch_windows_mode,
        read_only=False,
        exemplars=[
            "make alt tab switch windows not apps",
            "traditional alt tab every window",
            "alt tab should cycle each window gnome",
            "ungroup alt tab gnome",
            "stop grouping alt tab by application",
            "restore default alt tab gnome",
            "reset alt tab to grouped apps",
            "how to alt tab between all windows",
        ],
    ),
]
