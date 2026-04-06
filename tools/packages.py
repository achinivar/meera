"""Package listing — branches on distro (dnf vs apt)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _packages_list_updates(params: Mapping[str, Any]) -> ToolResult:
    distro = params["distro"]
    if distro == "fedora":
        r = run_argv(
            ["dnf", "list", "--upgrades", "--quiet"],
            timeout=120.0,
            max_stdout_chars=131072,
        )
        if isinstance(r, ToolResult):
            return r
        # dnf exits 0 even when no upgrades sometimes; still return stdout
        msg = "Package upgrades (dnf)"
        if not r.stdout.strip():
            msg = "No package upgrades listed (dnf)"
        return tool_result_ok(msg, data={"raw": r.stdout.strip(), "distro": distro})

    if distro == "ubuntu":
        r = run_argv(
            ["apt", "list", "--upgradable"],
            timeout=120.0,
            max_stdout_chars=131072,
        )
        if isinstance(r, ToolResult):
            return r
        lines = [ln for ln in r.stdout.splitlines() if ln and not ln.startswith("Listing")]
        msg = f"{len(lines)} upgradable package line(s) (apt)"
        if not lines:
            msg = "No upgradable packages listed (apt)"
        return tool_result_ok(msg, data={"lines": lines[:500], "distro": distro})

    return tool_result_err(f"Unsupported distro: {distro}", "VALIDATION_ERROR")


def _flatpak_list(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    r = run_argv(
        ["flatpak", "list", "--columns=application,version", "--app"],
        timeout=60.0,
        max_stdout_chars=131072,
    )
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            r.stderr or r.stdout or "flatpak list failed",
            "COMMAND_FAILED",
        )
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return tool_result_ok(
        f"{len(lines)} Flatpak app(s)",
        data={"lines": lines[:500]},
    )


_DISTRO = ToolParam(
    name="distro",
    param_type="string",
    required=True,
    description='Must be "ubuntu" or "fedora".',
)


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="packages_list_updates",
        description="List OS package upgrades (dnf on Fedora, apt on Ubuntu). Read-only.",
        parameters=[_DISTRO],
        handler=_packages_list_updates,
        read_only=True,
    ),
    ToolSpec(
        name="flatpak_list",
        description="List installed Flatpak applications.",
        parameters=[_DISTRO],
        handler=_flatpak_list,
        read_only=True,
    ),
]
