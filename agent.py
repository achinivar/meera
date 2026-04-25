"""Phase 3 — parse model tool JSON, augment system prompt with tool catalog."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from tools.registry import tools_prompt_catalog_json
from tools.schema import ToolResult

# Synthetic user messages carrying run_tool output start with this prefix (session reload UX).
TOOL_FEEDBACK_PREFIX = "[Tool result]\n"


def agent_tools_enabled() -> bool:
    v = os.environ.get("MEERA_AGENT_TOOLS", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def build_system_message_content(base_identity: str) -> str:
    return (
        f"{base_identity.strip()}\n\n"
        "## Tools\n"
        "You have laptop tools to help the user. When a request matches a tool, reply with ONLY a single JSON object:\n"
        '{"tool":"<tool_id>","params":{...}}\n'
        "- No markdown fences, no commentary, no extra text.\n"
        "- Use parameter names exactly as listed.\n"
        "- Omit optional parameters you don't need — don't send JSON null.\n"
        "- If the user's pronoun (\"it\", \"that\") refers to the previous topic, resolve it to the correct tool.\n"
        "- If no tool fits, answer conversationally in plain text.\n\n"

        "### Volume\n"
        "- volume_get — Read current volume. Params: (none)\n"
        "- volume_set_percent — Set absolute volume. Params: [percent (int, 0-150)]\n"
        "- volume_adjust — Adjust volume relatively. Params: [direction (\"up\"/\"down\"), percent (int, 1-150)]\n"
        "- volume_mute_toggle — Mute/unmute/toggle. Params: [state (\"mute\"/\"unmute\"/\"toggle\")]\n\n"

        "### Brightness\n"
        "- brightness_get — Read current brightness. Params: (none)\n"
        "- brightness_set — Set or adjust brightness. Params: [action (\"set\"/\"up\"/\"down\"), value (int, 0-100)]\n\n"

        "### Wi-Fi\n"
        "- wifi_list_networks — List visible networks. Params: (none)\n"
        "- wifi_status — Show connection state. Params: (none)\n"
        "- wifi_toggle — Turn Wi-Fi on/off. Params: [state (\"on\"/\"off\")]\n\n"

        "### System Info\n"
        "- system_info — Uptime, CPU temp, load average. Params: (none)\n"
        "- disk_space — Disk usage summary. Params: (none)\n"
        "- network_info — IP addresses, interface, link speed. Params: (none)\n"
        "- datetime_query — Current date/time. Params: [timezone (string, optional), format (\"short\"/\"long\", optional)]\n\n"

        "### Files\n"
        "- file_list_dir — List files in a directory. Params: [path (string, optional), max_entries (int, optional)]\n"
        "- file_search_name — Search files by name. Params: [query (string), path (string, optional), max_results (int, optional)]\n"
        "- disk_usage_top — Largest files by disk usage. Params: [path (string, optional), depth (int, optional), max_results (int, optional)]\n"
        "- file_find_and_open — Search then open a file. Params: [query (string), path (string, optional)]\n\n"

        "### Processes\n"
        "- process_list — Top processes by CPU. Params: [limit (int, optional)]\n"
        "- process_kill_by_name — Kill by name. Params: [name (string), signal (\"SIGTERM\"/\"SIGKILL\", optional)]\n"
        "- process_high_usage — Processes above CPU/mem thresholds. Params: [cpu_threshold (int, optional), mem_threshold (int, optional), limit (int, optional)]\n"
        "- process_check_running — Check if a process is running. Params: [name (string)]\n\n"

        "### Packages\n"
        "- packages_list_updates — List available OS updates. Params: (none)\n"
        "- flatpak_list — List installed Flatpak apps. Params: (none)\n\n"

        "### Reminders\n"
        "- timer_list — List active timers. Params: (none)\n"
        "- reminder_set — Set a reminder. Params: [message (string), delay_minutes (int, 1-10080), unit_id (string, optional)]\n"
        "- reminder_delete — Delete a reminder. Params: [unit_id (string)]\n\n"

        "### Screenshot\n"
        "- screenshot_save — Take a screenshot. Params: [directory (string, optional), filename (string, optional)]\n\n"

        "### Weather\n"
        "- weather_query — Weather for a city. Params: [city (string)]\n\n"

        "## Examples\n\n"

        'User: set the volume to 30%\n'
        '{"tool":"volume_set_percent","params":{"percent":30}}\n\n'

        'User: increase the volume by 20%\n'
        '{"tool":"volume_adjust","params":{"direction":"up","percent":20}}\n\n'

        'User: make it quieter\n'
        '{"tool":"volume_adjust","params":{"direction":"down","percent":10}}\n\n'

        'User: dim the brightness\n'
        '{"tool":"brightness_set","params":{"action":"down","value":10}}\n\n'

        'User: is Firefox running?\n'
        '{"tool":"process_check_running","params":{"name":"firefox"}}\n\n'

        'User: what time is it?\n'
        '{"tool":"datetime_query","params":{}}\n\n'

        'User: remind me to call mom in 30 minutes\n'
        '{"tool":"reminder_set","params":{"message":"call mom","delay_minutes":30}}\n\n'

        'User: how are you?\n'
        "I'm doing great, thanks for asking! How can I help you?\n"
    )


def build_summarize_system_message_content(base_identity: str) -> str:
    """After a tool ran: no catalog — only instruct plain-language reply from tool JSON."""
    return (
        f"{base_identity.strip()}\n\n"
        "## Tool result follow-up\n"
        "The latest user message begins with `[Tool result]` and contains JSON from a tool that "
        "already ran on this machine. Reply in **plain language only** for the user — explain "
        "volume, brightness, Wi‑Fi status, file lists, errors, etc., using ok/message/data.\n"
        "Do **not** output JSON tool calls or `{\"tool\":...}` blocks.\n"
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


def max_agent_passes() -> int:
    try:
        return max(2, min(16, int(os.environ.get("MEERA_AGENT_MAX_PASSES", "8"))))
    except ValueError:
        return 8
