"""Safe filesystem tools."""
from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _resolve_under_home(path_str: str) -> Path | ToolResult:
    raw = (path_str or "").strip() or "~"
    expanded = Path(os.path.expanduser(raw)).resolve()
    home = Path.home().resolve()
    try:
        expanded.relative_to(home)
    except ValueError:
        return tool_result_err(
            f"Path must stay under home directory: {home}",
            "VALIDATION_ERROR",
        )
    if ".." in Path(path_str).parts:
        return tool_result_err("Path must not contain '..'", "VALIDATION_ERROR")
    return expanded


def _file_list_dir(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    path_str = str(params.get("path") or "~")
    max_entries = int(params.get("max_entries") or 200)
    max_entries = max(1, min(max_entries, 500))

    resolved = _resolve_under_home(path_str)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return tool_result_err(f"Not a directory: {resolved}", "VALIDATION_ERROR")

    names: list[str] = []
    try:
        for i, entry in enumerate(sorted(resolved.iterdir(), key=lambda p: p.name.lower())):
            if i >= max_entries:
                names.append(f"…({max_entries} cap)")
                break
            suffix = "/" if entry.is_dir() else ""
            names.append(entry.name + suffix)
    except OSError as e:
        return tool_result_err(str(e), "OS_ERROR")

    return tool_result_ok(
        f"{len(names)} entries in {resolved}",
        data={"path": str(resolved), "entries": names},
    )


def _file_search_name(params: Mapping[str, Any]) -> ToolResult:
    query = str(params.get("query") or "").strip()
    if not query:
        return tool_result_err("query is required", "VALIDATION_ERROR")
    path_str = str(params.get("path") or "~")
    max_results = int(params.get("max_results") or 50)
    max_results = max(1, min(max_results, 500))

    resolved = _resolve_under_home(path_str)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return tool_result_err(f"Not a directory: {resolved}", "VALIDATION_ERROR")

    if shutil.which("fd"):
        result = run_argv(
            ["fd", "-H", "--max-results", str(max_results), "--glob", f"*{query}*", str(resolved)],
            timeout=30.0,
        )
        if isinstance(result, ToolResult):
            return result
        out_text = result.stdout
    else:
        find_result = run_argv(
            [
                "find",
                str(resolved),
                "-maxdepth",
                "5",
                "-iname",
                f"*{query}*",
                "-type",
                "f",
                "-print",
            ],
            timeout=30.0,
        )
        if isinstance(find_result, ToolResult):
            return find_result
        all_lines = [l.strip() for l in find_result.stdout.strip().splitlines() if l.strip()]
        out_text = "\n".join(all_lines[:max_results])

    lines = [l.strip() for l in out_text.strip().splitlines() if l.strip()]
    return tool_result_ok(
        f"Found {len(lines)} matching file(s)",
        data={"query": query, "path": str(resolved), "files": lines},
    )


def _disk_usage_top(params: Mapping[str, Any]) -> ToolResult:
    path_str = str(params.get("path") or "~")
    depth = int(params.get("depth") or 1)
    depth = max(1, min(depth, 3))
    max_results = int(params.get("max_results") or 15)
    max_results = max(1, min(max_results, 500))

    resolved = _resolve_under_home(path_str)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return tool_result_err(f"Not a directory: {resolved}", "VALIDATION_ERROR")

    import subprocess as _sub
    try:
        du_proc = _sub.Popen(
            ["du", "-h", "--max-depth", str(depth), str(resolved)],
            stdout=_sub.PIPE, stderr=_sub.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        sort_proc = _sub.Popen(
            ["sort", "-hr"],
            stdin=du_proc.stdout, stdout=_sub.PIPE, stderr=_sub.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        du_proc.stdout.close()
        head_proc = _sub.Popen(
            ["head", "-n", str(max_results)],
            stdin=sort_proc.stdout, stdout=_sub.PIPE, stderr=_sub.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        sort_proc.stdout.close()
        out, err = head_proc.communicate(timeout=60)
        if head_proc.returncode != 0:
            return tool_result_err(err or "disk usage pipeline failed", "SUBPROCESS_ERROR")
    except (_sub.TimeoutExpired, OSError) as e:
        return tool_result_err(str(e), "SUBPROCESS_ERROR")

    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    entries: list[dict[str, str]] = []
    for line in lines:
        parts = line.rsplit("\t", 1)
        if len(parts) == 2:
            entries.append({"size": parts[0], "path": parts[1]})
        else:
            entries.append({"size": line.split()[0] if line.split() else line, "path": line})

    return tool_result_ok(
        f"Top {len(entries)} entries by disk usage",
        data={"path": str(resolved), "depth": depth, "entries": entries},
    )


def _file_find_and_open(params: Mapping[str, Any]) -> ToolResult:
    query = str(params.get("query") or "").strip()
    if not query:
        return tool_result_err("query is required", "VALIDATION_ERROR")
    path_str = str(params.get("path") or "~")

    resolved = _resolve_under_home(path_str)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return tool_result_err(f"Not a directory: {resolved}", "VALIDATION_ERROR")

    if shutil.which("fd"):
        search_result = run_argv(
            [
                "fd",
                "-H",
                "--max-results",
                "5",
                "--glob",
                f"*{query}*",
                str(resolved),
            ],
            timeout=30.0,
        )
    else:
        search_result = run_argv(
            [
                "find",
                str(resolved),
                "-maxdepth",
                "5",
                "-iname",
                f"*{query}*",
                "-type",
                "f",
                "-print",
            ],
            timeout=30.0,
        )

    if isinstance(search_result, ToolResult):
        return search_result

    lines = [l.strip() for l in search_result.stdout.strip().splitlines() if l.strip()]

    if not lines:
        return tool_result_err(f"No file found matching '{query}'", "NOT_FOUND")

    if len(lines) == 1:
        target = lines[0]
        open_result = run_argv(["xdg-open", target], timeout=10.0)
        if isinstance(open_result, ToolResult):
            return open_result
        if open_result.returncode != 0:
            return tool_result_err(
                f"Failed to open file: {open_result.stderr}",
                "SUBPROCESS_ERROR",
            )
        return tool_result_ok(
            f"Opened file: {target}",
            data={"opened": target},
        )
    else:
        return tool_result_ok(
            f"Found {len(lines)} matching files — please pick one to open",
            data={"query": query, "files": lines},
        )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="file_list_dir",
        description="List files in a directory under the user's home (non-recursive).",
        parameters=[
            ToolParam(
                name="path",
                param_type="string",
                required=False,
                description="Optional directory under home to list; omit for home (~).",
                default="~",
            ),
            ToolParam(
                name="max_entries",
                param_type="integer",
                required=False,
                description="Max entries (1–500)",
                default=200,
            ),
        ],
        handler=_file_list_dir,
        read_only=True,
        exemplars=[
            "what's in my Documents folder",
            "list files in ~/Downloads",
            "show me what's in this directory",
            "ls my home folder",
            "what files are in ~/Pictures",
            "contents of the Music directory",
            "list home directory contents",
            "show files under ~/Desktop",
            "what's inside my Downloads",
        ],
    ),
    ToolSpec(
        name="file_search_name",
        description="Recursively search for files by name pattern under a directory.",
        parameters=[
            ToolParam(
                name="query",
                param_type="string",
                required=True,
                description="Filename pattern to search for (substring match).",
            ),
            ToolParam(
                name="path",
                param_type="string",
                required=False,
                description="Starting directory under home to search; omit for home (~).",
                default="~",
            ),
            ToolParam(
                name="max_results",
                param_type="integer",
                required=False,
                description="Maximum number of results to return (1-500).",
                default=50,
            ),
        ],
        handler=_file_search_name,
        read_only=True,
        exemplars=[
            "find a file called report",
            "search for a file named meeting",
            "where is the file invoice",
            "find files with 'tax' in the name",
            "look for files containing 'backup'",
            "search files in Documents for 'pdf'",
            "locate a file named resume",
            "do I have a file called notes anywhere",
        ],
    ),
    ToolSpec(
        name="disk_usage_top",
        description="Show largest files/directories by disk usage under a path.",
        parameters=[
            ToolParam(
                name="path",
                param_type="string",
                required=False,
                description="Directory to analyze under home; omit for home (~).",
                default="~",
            ),
            ToolParam(
                name="depth",
                param_type="integer",
                required=False,
                description="Recursion depth for du (1-3).",
                default=1,
            ),
            ToolParam(
                name="max_results",
                param_type="integer",
                required=False,
                description="Number of top entries to show (1-500).",
                default=15,
            ),
        ],
        handler=_disk_usage_top,
        read_only=True,
        exemplars=[
            "what's taking up disk space",
            "show me the largest directories",
            "biggest folders in my home",
            "find what's using disk space",
            "what's hogging my storage",
            "top space-consuming directories",
            "where is my disk usage going",
        ],
    ),
    ToolSpec(
        name="file_find_and_open",
        description="Search for a file by name then open it with the default application.",
        parameters=[
            ToolParam(
                name="query",
                param_type="string",
                required=True,
                description="Filename or pattern to search for.",
            ),
            ToolParam(
                name="path",
                param_type="string",
                required=False,
                description="Directory to search under home; omit for home (~).",
                default="~",
            ),
        ],
        handler=_file_find_and_open,
        read_only=False,
        exemplars=[
            "find and open the file resume",
            "open my latest report",
            "search for and open invoice.pdf",
            "find a file called notes and open it",
            "open the file budget",
            "locate and launch tax_returns",
        ],
    ),
]
