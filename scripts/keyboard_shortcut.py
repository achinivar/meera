#!/usr/bin/env python3
"""Manage Meera's GNOME custom keyboard shortcut."""

from __future__ import annotations

import ast
import subprocess
import sys


MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_BINDING_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
MEERA_BINDING_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/meera/"
COMMON_CONTROL_KEYS = frozenset(
    {
        "a",
        "c",
        "f",
        "h",
        "l",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "v",
        "w",
        "x",
        "y",
        "z",
        "0",
        "equal",
        "minus",
        "plus",
    }
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, check=False, text=True)


def _gsettings_available() -> bool:
    return _run(["gsettings", "list-schemas"]).returncode == 0


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _custom_paths() -> list[str]:
    result = _run(["gsettings", "get", MEDIA_KEYS_SCHEMA, "custom-keybindings"])
    if result.returncode != 0:
        return []
    raw = result.stdout.strip()
    if raw == "@as []":
        return []
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _set_custom_paths(paths: list[str]) -> int:
    rendered = "[" + ", ".join(_shell_quote(path) for path in paths) + "]"
    return _run(["gsettings", "set", MEDIA_KEYS_SCHEMA, "custom-keybindings", rendered]).returncode


def _current_binding() -> str:
    result = _run(
        [
            "gsettings",
            "get",
            f"{CUSTOM_BINDING_SCHEMA}:{MEERA_BINDING_PATH}",
            "binding",
        ]
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip().strip("'")


def _binding_conflict(binding: str) -> bool:
    result = _run(["gsettings", "list-recursively"])
    if result.returncode != 0:
        return False
    needle = _shell_quote(binding)
    for line in result.stdout.splitlines():
        if needle not in line:
            continue
        if MEERA_BINDING_PATH in line:
            continue
        return True
    return False


def _binding_reserved(binding: str) -> bool:
    normalized = binding.lower().replace("<primary>", "<control>").replace("<ctrl>", "<control>")
    has_control = "<control>" in normalized
    has_non_editing_modifier = any(
        token in normalized for token in ("<alt>", "<super>", "<hyper>", "<meta>")
    )
    key = normalized.rsplit(">", 1)[-1]
    return has_control and not has_non_editing_modifier and key in COMMON_CONTROL_KEYS


def _set_binding(binding: str, command: str) -> int:
    if not _gsettings_available():
        print("GNOME gsettings is not available.", file=sys.stderr)
        return 2
    if _binding_reserved(binding):
        print(
            "Shortcut is commonly used by applications. Try Super+key or Ctrl+Alt+key.",
            file=sys.stderr,
        )
        return 4
    if _binding_conflict(binding):
        print("Shortcut is already in use.", file=sys.stderr)
        return 3

    paths = _custom_paths()
    if MEERA_BINDING_PATH not in paths:
        paths.append(MEERA_BINDING_PATH)
        if _set_custom_paths(paths) != 0:
            print("Could not update GNOME custom keybindings list.", file=sys.stderr)
            return 1

    schema_path = f"{CUSTOM_BINDING_SCHEMA}:{MEERA_BINDING_PATH}"
    updates = [
        ("name", "Meera"),
        ("command", command),
        ("binding", binding),
    ]
    for key, value in updates:
        if _run(["gsettings", "set", schema_path, key, _shell_quote(value)]).returncode != 0:
            print(f"Could not set {key}.", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: keyboard_shortcut.py get|set BINDING COMMAND|check BINDING", file=sys.stderr)
        return 2

    command = argv[1]
    if command == "get":
        print(_current_binding())
        return 0
    if command == "check" and len(argv) == 3:
        if _binding_reserved(argv[2]):
            return 4
        return 3 if _binding_conflict(argv[2]) else 0
    if command == "set" and len(argv) == 4:
        return _set_binding(argv[2], argv[3])

    print("Usage: keyboard_shortcut.py get|set BINDING COMMAND|check BINDING", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
