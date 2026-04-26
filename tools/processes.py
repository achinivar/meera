"""Process tools."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _process_list(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    limit = int(params.get("limit") or 25)
    limit = max(1, min(limit, 100))

    r = run_argv(
        [
            "ps",
            "-eo",
            "pid,comm,%cpu,%mem",
            "--sort=-%cpu",
            "--no-headers",
        ],
        timeout=15.0,
    )
    if isinstance(r, ToolResult):
        return r
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()][:limit]
    return tool_result_ok(
        f"Top {len(lines)} processes by CPU",
        data={"processes": lines},
    )


def _process_kill_by_name(params: Mapping[str, Any]) -> ToolResult:
    name = params["name"]
    signal = str(params.get("signal") or "SIGTERM").upper()
    if signal not in ("SIGTERM", "SIGKILL"):
        return tool_result_err(
            f"Invalid signal {signal!r}; use SIGTERM or SIGKILL",
            "INVALID_SIGNAL",
        )
    signal_flag = "-TERM" if signal == "SIGTERM" else "-KILL"

    r = run_argv(["pkill", signal_flag, name], timeout=10.0)
    if isinstance(r, ToolResult):
        return r
    if r.returncode != 0:
        return tool_result_err(
            f"pkill failed (exit {r.returncode}): {r.stderr.strip()}",
            "PKILL_FAILED",
        )
    return tool_result_ok(
        f"Sent {signal} to processes named {name!r}",
        data={"name": name, "signal": signal},
    )


def _process_high_usage(params: Mapping[str, Any]) -> ToolResult:
    cpu_threshold = int(params.get("cpu_threshold") or 50)
    mem_threshold = int(params.get("mem_threshold") or 50)
    limit = int(params.get("limit") or 20)

    if not 0 <= cpu_threshold <= 100:
        return tool_result_err(
            f"cpu_threshold must be 0–100, got {cpu_threshold}",
            "INVALID_PARAMETER",
        )
    if not 0 <= mem_threshold <= 100:
        return tool_result_err(
            f"mem_threshold must be 0–100, got {mem_threshold}",
            "INVALID_PARAMETER",
        )
    if not 1 <= limit <= 100:
        return tool_result_err(
            f"limit must be 1–100, got {limit}",
            "INVALID_PARAMETER",
        )

    r = run_argv(
        [
            "ps",
            "-eo",
            "pid,comm,%cpu,%mem",
            "--sort=-%cpu",
            "--no-headers",
        ],
        timeout=15.0,
    )
    if isinstance(r, ToolResult):
        return r
    matches = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            comm = parts[1]
            cpu = float(parts[2])
            mem = float(parts[3])
        except (ValueError, IndexError):
            continue
        if cpu > cpu_threshold or mem > mem_threshold:
            matches.append({"pid": pid, "comm": comm, "cpu": cpu, "mem": mem})
        if len(matches) >= limit:
            break
    return tool_result_ok(
        f"Found {len(matches)} processes exceeding thresholds (CPU>{cpu_threshold}%, MEM>{mem_threshold}%)",
        data={"matches": matches, "cpu_threshold": cpu_threshold, "mem_threshold": mem_threshold},
    )


def _process_check_running(params: Mapping[str, Any]) -> ToolResult:
    name = params["name"]

    r = run_argv(["pgrep", "-x", name], timeout=10.0)
    if isinstance(r, ToolResult):
        return r

    if r.returncode != 0:
        return tool_result_ok(
            f"Process {name!r} is not running",
            data={"running": False, "pid_count": 0, "pids": []},
        )

    pids = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                pids.append(int(line))
            except ValueError:
                pass

    pids_sliced = pids[:50]
    return tool_result_ok(
        f"Process {name!r} is running ({len(pids)} instance{'s' if len(pids) != 1 else ''})",
        data={"running": True, "pid_count": len(pids), "pids": pids_sliced},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="process_list",
        description="List top processes by CPU use (ps).",
        parameters=[
            ToolParam(
                name="limit",
                param_type="integer",
                required=False,
                description="Max rows (1–100)",
                default=25,
            ),
        ],
        handler=_process_list,
        read_only=True,
        exemplars=[
            "what's running",
            "show me running processes",
            "list active processes",
            "top CPU processes",
            "what processes are using CPU",
            "show all processes",
            "ps aux equivalent",
        ],
    ),
    ToolSpec(
        name="process_kill_by_name",
        description="Kill processes by name using pkill. Sends SIGTERM by default.",
        parameters=[
            ToolParam(
                name="name",
                param_type="string",
                required=True,
                description="Process name to kill",
            ),
            ToolParam(
                name="signal",
                param_type="string",
                required=False,
                description="Signal to send: SIGTERM or SIGKILL",
                default="SIGTERM",
            ),
        ],
        handler=_process_kill_by_name,
        read_only=False,
        requires_elevation=False,
        exemplars=[
            "kill firefox",
            "stop the chrome process",
            "force kill spotify",
            "terminate slack",
            "end the process called vlc",
            "shut down zoom",
            "kill the python script",
        ],
    ),
    ToolSpec(
        name="process_high_usage",
        description="Find processes exceeding CPU or memory usage thresholds.",
        parameters=[
            ToolParam(
                name="cpu_threshold",
                param_type="integer",
                required=False,
                description="CPU percentage threshold (0-100)",
                default=50,
            ),
            ToolParam(
                name="mem_threshold",
                param_type="integer",
                required=False,
                description="Memory percentage threshold (0-100)",
                default=50,
            ),
            ToolParam(
                name="limit",
                param_type="integer",
                required=False,
                description="Max results to return (1-100)",
                default=20,
            ),
        ],
        handler=_process_high_usage,
        read_only=True,
        exemplars=[
            "what's using lots of CPU",
            "show me high CPU processes",
            "what's hogging memory",
            "find resource-heavy processes",
            "what's eating my CPU",
            "show me processes using too much memory",
            "anything pegging the CPU",
        ],
    ),
    ToolSpec(
        name="process_check_running",
        description="Check whether a process with a given name is currently running (pgrep -x).",
        parameters=[
            ToolParam(
                name="name",
                param_type="string",
                required=True,
                description="Process name to check",
            ),
        ],
        handler=_process_check_running,
        read_only=True,
        exemplars=[
            "is firefox running",
            "check if chrome is open",
            "is slack running right now",
            "is the python process up",
            "is docker running",
            "is X currently active",
        ],
    ),
]
