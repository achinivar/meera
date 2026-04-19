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
    catalog = tools_prompt_catalog_json()
    return (
        f"{base_identity.strip()}\n\n"
        "## Laptop tools\n"
        "When (and only when) the user's request should use a capability from the catalog, "
        "reply with **only** a single JSON object — no markdown fences, no commentary:\n"
        '{"tool":"<tool_id>","params":{...}}\n'
        "Use parameter names exactly as in the catalog.\n"
        "For optional parameters, omit keys you do not need instead of JSON `null`.\n"
        "If no tool fits, answer with normal conversational plain text (not JSON).\n\n"
        f"Tool catalog JSON:\n{catalog}\n"
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
