"""Phase 3 — two-step tool routing and tool-call parsing."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from tools.schema import ToolResult

# Synthetic user messages carrying run_tool output start with this prefix (session reload UX).
TOOL_FEEDBACK_PREFIX = "[Tool result]\n"
# Synthetic assistant memory messages storing compact tool outputs for later turns.
TOOL_MEMORY_PREFIX = "[Tool memory]\n"


def agent_tools_enabled() -> bool:
    v = os.environ.get("MEERA_AGENT_TOOLS", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def build_route_system_message_content(base_identity: str) -> str:
    return (
        f"{base_identity.strip()}\n\n"
        "## Routing task\n"
        "Classify the user's latest message as either:\n"
        '- "tool" (a laptop tool should be used), or\n'
        '- "no_tool" (normal conversational reply, no tool needed).\n\n'
        'Also return a "type" when route is "tool", choosing one of:\n'
        "volume, brightness, wifi, system, files, processes, packages, reminders, screenshot, weather\n\n"
        "Reply with ONLY a single JSON object:\n"
        '{"route":"tool","type":"<type>"}\n'
        "or\n"
        '{"route":"no_tool"}\n\n'
        "- No markdown fences, no commentary, no extra text.\n"
        '- Choose "tool" when a tool can directly execute or fetch what the user asked.\n'
        '- Choose "no_tool" for general conversation, opinions, explanations, or unsupported requests.\n'
        '- If route is "tool", always include "type".\n'
        '- If you cannot determine a valid type, output {"route":"no_tool"}.\n\n'
        "Available tools (names only):\n"
        "ping\n"
        "wifi_list_networks\n"
        "wifi_status\n"
        "brightness_get\n"
        "volume_get\n"
        "volume_set_percent\n"
        "volume_mute_toggle\n"
        "volume_adjust\n"
        "brightness_set\n"
        "wifi_toggle\n"
        "system_info\n"
        "disk_space\n"
        "network_info\n"
        "datetime_query\n"
        "file_list_dir\n"
        "file_search_name\n"
        "disk_usage_top\n"
        "file_find_and_open\n"
        "process_list\n"
        "process_kill_by_name\n"
        "process_high_usage\n"
        "process_check_running\n"
        "packages_list_updates\n"
        "flatpak_list\n"
        "timer_list\n"
        "reminder_set\n"
        "reminder_delete\n"
        "screenshot_save\n"
        "weather_query\n\n"
        "Reply with ONLY a single JSON object:\n"
        '{"route":"tool","type":"<type>"}\n'
        "or\n"
        '{"route":"no_tool"}\n'
    )


def build_tool_selection_system_message_content(base_identity: str, route_type: str) -> str:
    route_key = route_type.strip().lower()
    catalogs: dict[str, str] = {
        "volume": (
            "### Volume tools only\n"
            "- volume_get — Read current volume. Params: (none)\n"
            "- volume_set_percent — Set absolute volume. Params: [percent (int, 0-100)]\n"
            "- volume_adjust — Adjust volume relatively. Params: [direction (\"up\"/\"down\"), percent (int, 1-100)]\n"
            "- volume_mute_toggle — Mute/unmute/toggle. Params: [state (\"mute\"/\"unmute\"/\"toggle\")]\n\n"
            "## Examples\n\n"
            'User: set the volume to 30%\n'
            '{"tool":"volume_set_percent","params":{"percent":30}}\n\n'
            'User: increase the volume by 20%\n'
            '{"tool":"volume_adjust","params":{"direction":"up","percent":20}}\n\n'
            'User: make it quieter\n'
            '{"tool":"volume_adjust","params":{"direction":"down","percent":10}}\n\n'
            'User: turn it all the way up\n'
            '{"tool":"volume_set_percent","params":{"percent":100}}\n\n'
        ),
        "brightness": (
            "### Brightness tools only\n"
            "- brightness_get — Read current brightness. Params: (none)\n"
            "- brightness_set — Set or adjust brightness. Params: [action (\"set\"/\"up\"/\"down\"), value (int, 0-100)]\n\n"
            "## Examples\n\n"
            'User: dim the brightness\n'
            '{"tool":"brightness_set","params":{"action":"down","value":10}}\n\n'
            'User: set brightness to 40%\n'
            '{"tool":"brightness_set","params":{"action":"set","value":40}}\n\n'
        ),
        "wifi": (
            "### Wi-Fi tools only\n"
            "- wifi_list_networks — List visible networks. Params: (none)\n"
            "- wifi_status — Show connection state. Params: (none)\n"
            "- wifi_toggle — Turn Wi-Fi on/off. Params: [state (\"on\"/\"off\")]\n\n"
            "## Examples\n\n"
            'User: turn wifi off\n'
            '{"tool":"wifi_toggle","params":{"state":"off"}}\n\n'
        ),
        "system": (
            "### System tools only\n"
            "- system_info — Uptime, CPU temp, load average. Params: (none)\n"
            "- disk_space — Disk usage summary. Params: (none)\n"
            "- network_info — IP addresses, interface, link speed. Params: (none)\n"
            "- datetime_query — Current date/time. Params: [timezone (string, optional), format (\"short\"/\"long\", optional)]\n\n"
            "## Examples\n\n"
            'User: what time is it?\n'
            '{"tool":"datetime_query","params":{}}\n\n'
        ),
        "files": (
            "### File tools only\n"
            "- file_list_dir — List files in a directory. Params: [path (string, optional), max_entries (int, optional)]\n"
            "- file_search_name — Search files by name. Params: [query (string), path (string, optional), max_results (int, optional)]\n"
            "- disk_usage_top — Largest files by disk usage. Params: [path (string, optional), depth (int, optional), max_results (int, optional)]\n"
            "- file_find_and_open — Search then open a file. Params: [query (string), path (string, optional)]\n\n"
            "## Examples\n\n"
            'User: what is in my Documents directory?\n'
            '{"tool":"file_list_dir","params":{"path":"~/Documents"}}\n\n'
        ),
        "processes": (
            "### Process tools only\n"
            "- process_list — Top processes by CPU. Params: [limit (int, optional)]\n"
            "- process_kill_by_name — Kill by name. Params: [name (string), signal (\"SIGTERM\"/\"SIGKILL\", optional)]\n"
            "- process_high_usage — Processes above CPU/mem thresholds. Params: [cpu_threshold (int, optional), mem_threshold (int, optional), limit (int, optional)]\n"
            "- process_check_running — Check if a process is running. Params: [name (string)]\n\n"
            "## Examples\n\n"
            'User: is Firefox running?\n'
            '{"tool":"process_check_running","params":{"name":"firefox"}}\n\n'
        ),
        "packages": (
            "### Package tools only\n"
            "- packages_list_updates — List available OS updates. Params: (none)\n"
            "- flatpak_list — List installed Flatpak apps. Params: (none)\n\n"
            "## Examples\n\n"
            'User: show package updates\n'
            '{"tool":"packages_list_updates","params":{}}\n\n'
        ),
        "reminders": (
            "### Reminder tools only\n"
            "- timer_list — List active timers. Params: (none)\n"
            "- reminder_set — Set a reminder. Params: [message (string), delay_minutes (int, 1-10080), unit_id (string, optional)]\n"
            "- reminder_delete — Delete a reminder. Params: [unit_id (string)]\n\n"
            "## Examples\n\n"
            'User: remind me to call mom in 30 minutes\n'
            '{"tool":"reminder_set","params":{"message":"call mom","delay_minutes":30}}\n\n'
        ),
        "screenshot": (
            "### Screenshot tools only\n"
            "- screenshot_save — Take a screenshot. Params: [directory (string, optional), filename (string, optional)]\n\n"
            "## Examples\n\n"
            'User: take a screenshot\n'
            '{"tool":"screenshot_save","params":{}}\n\n'
        ),
        "weather": (
            "### Weather tools only\n"
            "- weather_query — Weather for a city. Params: [city (string)]\n\n"
            "## Examples\n\n"
            'User: what is the weather in Tokyo?\n'
            '{"tool":"weather_query","params":{"city":"Tokyo"}}\n\n'
        ),
    }
    allowed_catalog = catalogs.get(route_key, catalogs["system"])
    return (
        f"{base_identity.strip()}\n\n"
        "## Tool selection task\n"
        "Choose exactly one tool call for the user's request.\n\n"
        "Context hint:\n"
        f'Any "it" or "that" in the user\'s prompt refers to {route_key}.\n'
        f"Only use {route_key} tools listed below.\n\n"
        "Reply with ONLY a single JSON object:\n"
        '{"tool":"<tool_id>","params":{...}}\n\n'
        "- No markdown fences, no commentary, no extra text.\n"
        "- Use parameter names exactly as listed.\n"
        "- Omit optional parameters you don't need — don't send JSON null.\n"
        "- Choose the single best tool and valid params.\n\n"
        f"{allowed_catalog}"
        "Reply with ONLY a single JSON object:\n"
        '{"tool":"<tool_id>","params":{...}}\n'
    )


def build_reply_system_message_content(base_identity: str) -> str:
    return (
        f"{base_identity.strip()}\n\n"
        "## Response mode\n"
        "Reply conversationally in plain text.\n"
        "Keep responses brief and helpful.\n"
        "Never claim you executed, changed, applied, enabled, disabled, set, or adjusted anything unless a tool result was provided.\n"
        "If the user asks for an action you cannot perform with available tool categories, clearly say you cannot do that action and ask for a supported request.\n\n"
        "Available tool categories:\n"
        "volume\n"
        "brightness\n"
        "wifi\n"
        "system\n"
        "files\n"
        "processes\n"
        "packages\n"
        "reminders\n"
        "screenshot\n"
        "weather\n"
    )


def build_summarize_system_message_content(base_identity: str) -> str:
    return (
        f"{base_identity.strip()}\n\n"
        "## Tool result follow-up\n"
        "The latest user message begins with `[Tool result]` and contains JSON from a tool that "
        "already ran on this machine.\n"
        "Reply in plain language only for the user, based strictly on that tool result.\n"
        "Do not add tips, opinions, suggestions, or extra thoughts.\n"
    )


def _normalize_tool_call(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return None
    params = obj.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return None
    return {"tool": tool.strip(), "params": params}


def _normalize_route_decision(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    route = obj.get("route")
    if route == "no_tool":
        return {"route": "no_tool"}
    if route != "tool":
        return None
    route_type_raw = obj.get("type")
    if not isinstance(route_type_raw, str):
        return None
    route_type = route_type_raw.strip().lower()
    allowed = {
        "volume",
        "brightness",
        "wifi",
        "system",
        "files",
        "processes",
        "packages",
        "reminders",
        "screenshot",
        "weather",
    }
    tool_to_type = {
        "volume_get": "volume",
        "volume_set_percent": "volume",
        "volume_mute_toggle": "volume",
        "volume_adjust": "volume",
        "brightness_get": "brightness",
        "brightness_set": "brightness",
        "wifi_list_networks": "wifi",
        "wifi_status": "wifi",
        "wifi_toggle": "wifi",
        "system_info": "system",
        "disk_space": "system",
        "network_info": "system",
        "datetime_query": "system",
        "file_list_dir": "files",
        "file_search_name": "files",
        "disk_usage_top": "files",
        "file_find_and_open": "files",
        "process_list": "processes",
        "process_kill_by_name": "processes",
        "process_high_usage": "processes",
        "process_check_running": "processes",
        "packages_list_updates": "packages",
        "flatpak_list": "packages",
        "timer_list": "reminders",
        "reminder_set": "reminders",
        "reminder_delete": "reminders",
        "screenshot_save": "screenshot",
        "weather_query": "weather",
    }
    if route_type in tool_to_type:
        route_type = tool_to_type[route_type]
    if route_type not in allowed:
        return None
    return {"route": "tool", "type": route_type}


def try_parse_tool_call(text: str) -> dict[str, Any] | None:
    """Return {\"tool\", \"params\"} if `text` is / contains a valid tool-call JSON object."""
    raw = text.strip()
    if not raw:
        return None

    blocks: list[str] = [raw]
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE):
        blocks.append(m.group(1).strip())

    seen: set[str] = set()
    dec = json.JSONDecoder()
    for block in blocks:
        if block in seen:
            continue
        seen.add(block)

        if block.startswith("{"):
            try:
                maybe = _normalize_tool_call(json.loads(block))
                if maybe:
                    return maybe
            except json.JSONDecodeError:
                pass

        for i, ch in enumerate(block):
            if ch != "{":
                continue
            try:
                obj, _ = dec.raw_decode(block[i:])
            except json.JSONDecodeError:
                continue
            maybe = _normalize_tool_call(obj)
            if maybe:
                return maybe
    return None


def try_parse_route_decision(text: str) -> dict[str, Any] | None:
    """Return {"route":"tool","type":...} or {"route":"no_tool"} when valid JSON is found."""
    raw = text.strip()
    if not raw:
        return None

    blocks: list[str] = [raw]
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE):
        blocks.append(m.group(1).strip())

    seen: set[str] = set()
    dec = json.JSONDecoder()
    for block in blocks:
        if block in seen:
            continue
        seen.add(block)

        if block.startswith("{"):
            try:
                maybe = _normalize_route_decision(json.loads(block))
                if maybe:
                    return maybe
            except json.JSONDecodeError:
                pass

        for i, ch in enumerate(block):
            if ch != "{":
                continue
            try:
                obj, _ = dec.raw_decode(block[i:])
            except json.JSONDecodeError:
                continue
            maybe = _normalize_route_decision(obj)
            if maybe:
                return maybe
    return None


def format_tool_result_message(tool_name: str, result: ToolResult) -> str:
    payload = {
        "tool": tool_name,
        "ok": result.ok,
        "message": result.message,
        "error_code": result.error_code,
        "data": result.data,
    }
    inner = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"{TOOL_FEEDBACK_PREFIX}{inner}"


def _compact_tool_data(value: Any, *, max_items: int = 80, max_str: int = 220, depth: int = 0) -> Any:
    if depth >= 3:
        return "<truncated>"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= max_items:
                out["__truncated_keys__"] = True
                break
            out[str(k)] = _compact_tool_data(v, max_items=max_items, max_str=max_str, depth=depth + 1)
        return out
    if isinstance(value, list):
        items = value[:max_items]
        out_list = [
            _compact_tool_data(v, max_items=max_items, max_str=max_str, depth=depth + 1) for v in items
        ]
        if len(value) > max_items:
            out_list.append(f"...({len(value) - max_items} more)")
        return out_list
    if isinstance(value, str):
        if len(value) <= max_str:
            return value
        return f"{value[:max_str]}...(+{len(value) - max_str} chars)"
    return value


def format_tool_memory_message(tool_name: str, result: ToolResult) -> str:
    payload = {
        "tool": tool_name,
        "ok": result.ok,
        "message": result.message,
        "error_code": result.error_code,
        "data": _compact_tool_data(result.data),
    }
    inner = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{TOOL_MEMORY_PREFIX}{inner}"


def max_agent_passes() -> int:
    try:
        return max(2, min(16, int(os.environ.get("MEERA_AGENT_MAX_PASSES", "8"))))
    except ValueError:
        return 8
