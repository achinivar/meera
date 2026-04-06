"""Bounded subprocess helpers — never shell=True."""
from __future__ import annotations

import subprocess
from typing import NamedTuple, Sequence

from tools.schema import ToolResult, tool_result_err


class CmdOutput(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def run_argv(
    argv: Sequence[str],
    *,
    timeout: float = 30.0,
    max_stdout_chars: int = 65536,
    max_stderr_chars: int = 16384,
) -> CmdOutput | ToolResult:
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return tool_result_err(
            f"Command not found: {argv[0]!r}",
            "COMMAND_NOT_FOUND",
        )
    except subprocess.TimeoutExpired:
        return tool_result_err(
            f"Command timed out after {timeout}s: {argv[0]!r}",
            "TIMEOUT",
        )
    except OSError as e:
        return tool_result_err(str(e), "OS_ERROR")

    out = proc.stdout or ""
    err = proc.stderr or ""
    if len(out) > max_stdout_chars:
        out = out[:max_stdout_chars] + "\n…(truncated)"
    if len(err) > max_stderr_chars:
        err = err[:max_stderr_chars] + "\n…(truncated)"
    return CmdOutput(proc.returncode, out, err)
