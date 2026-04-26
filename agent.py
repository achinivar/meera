"""Phase 4 — single-pass agent with retrieval-narrowed native tool calling.

Per-turn flow (`run_agent_turn`):

1. Heuristic fast-path: if the user message matches a regex pattern with
   well-defined parameters, run the tool directly and have the LLM only
   summarise the result. Skips retrieval and tool selection entirely.
2. Retrieval: embed the user message against the in-memory index of tool
   exemplars + RAG chunks. Top tools (deduped by name) become the LLM's
   `tools=[...]` payload; top RAG chunks get inlined into the system prompt
   as <KNOWLEDGE> blocks.
3. Single LLM call (streaming) with the narrowed tools list and
   `tool_choice="auto"`. If the model emits `tool_calls`, run them, append
   `role:tool` feedback messages, and make a follow-up streaming call so the
   LLM can summarise in natural language.

Cross-turn memory uses compact "[Tool memory]" assistant messages (prefix
preserved from Phase 3) so session reload UX keeps working.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from embeddings import EmbeddingUnavailableError
from inference import stream_llm_events, supports_tools
from retrieval import IndexHit, RetrievalResult, retrieve
from tools.registry import TOOLS, get_tool
from tools.runner import run_tool
from tools.schema import ToolParam, ToolResult, ToolSpec

# ---- Cross-turn history prefixes (kept stable for session reload UX) -------
TOOL_FEEDBACK_PREFIX = "[Tool result]\n"
TOOL_MEMORY_PREFIX = "[Tool memory]\n"

DEFAULT_BASE_IDENTITY = (
    "You are Meera, a friendly Linux desktop assistant running locally on "
    "the user's machine. Be concise, accurate, and don't apologise."
)


# ---- Settings --------------------------------------------------------------


def agent_tools_enabled() -> bool:
    v = os.environ.get("MEERA_AGENT_TOOLS", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _debug_tools_enabled() -> bool:
    v = os.environ.get("MEERA_DEBUG_TOOL_CALLS", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _debug_tool(msg: str) -> None:
    if _debug_tools_enabled():
        print(f"[agent] {msg}", file=sys.stderr, flush=True)


def max_agent_passes() -> int:
    """Soft cap on assistant ↔ tool round-trips per turn."""
    try:
        return max(1, min(8, int(os.environ.get("MEERA_AGENT_MAX_PASSES", "3"))))
    except ValueError:
        return 3


def _retrieval_top_k_tools() -> int:
    try:
        return max(1, min(8, int(os.environ.get("MEERA_RETRIEVAL_K_TOOLS", "4"))))
    except ValueError:
        return 4


def _retrieval_top_k_rag() -> int:
    try:
        return max(0, min(6, int(os.environ.get("MEERA_RETRIEVAL_K_RAG", "3"))))
    except ValueError:
        return 3


def _retrieval_tool_threshold() -> float:
    try:
        return float(os.environ.get("MEERA_RETRIEVAL_TOOL_THRESHOLD", "0.35"))
    except ValueError:
        return 0.35


def _retrieval_rag_threshold() -> float:
    try:
        return float(os.environ.get("MEERA_RETRIEVAL_RAG_THRESHOLD", "0.35"))
    except ValueError:
        return 0.35


# ---- Heuristic fast-path patterns ------------------------------------------


def _fp_volume_set(m: re.Match[str]) -> dict[str, Any]:
    pct = max(0, min(100, int(m.group("pct"))))
    return {"tool": "volume_set_percent", "params": {"percent": pct}}


def _fp_volume_mute(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "volume_mute_toggle", "params": {"state": "mute"}}


def _fp_volume_unmute(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "volume_mute_toggle", "params": {"state": "unmute"}}


def _fp_brightness_set(m: re.Match[str]) -> dict[str, Any]:
    pct = max(0, min(100, int(m.group("pct"))))
    return {"tool": "brightness_set", "params": {"action": "set", "value": pct}}


def _fp_screenshot(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "screenshot_save", "params": {}}


def _fp_datetime(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "datetime_query", "params": {}}


def _fp_process_running(m: re.Match[str]) -> dict[str, Any]:
    name = m.group("name").strip()
    return {"tool": "process_check_running", "params": {"name": name}}


def _fp_wifi_on(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "wifi_toggle", "params": {"state": "on"}}


def _fp_wifi_off(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "wifi_toggle", "params": {"state": "off"}}


def _fp_ping(_m: re.Match[str]) -> dict[str, Any]:
    return {"tool": "ping", "params": {}}


# Order matters: more specific patterns should appear first so they win when
# multiple regexes could match. Each pattern is run with `re.IGNORECASE`.
_HEURISTIC_PATTERNS: list[tuple[str, Any]] = [
    # Volume: "set volume to 30", "volume to 30", "volume 30%", "set audio to 25%"
    (r"\b(?:set\s+)?(?:the\s+)?(?:volume|audio)\s+(?:to\s+)?(?P<pct>\d{1,3})\s*%?\b", _fp_volume_set),
    (r"^\s*volume\s+(?P<pct>\d{1,3})\s*%?\s*$", _fp_volume_set),
    # Mute / unmute (no parameters)
    (r"\b(?:please\s+)?(?:mute|silence)\s+(?:the\s+)?(?:volume|audio|sound)\b", _fp_volume_mute),
    (r"^\s*mute\s*\.?\s*$", _fp_volume_mute),
    (r"^\s*unmute\s*\.?\s*$", _fp_volume_unmute),
    # Brightness: "set brightness to 50", "brightness to 80"
    (r"\b(?:set\s+)?(?:the\s+)?brightness\s+(?:to\s+)?(?P<pct>\d{1,3})\s*%?\b", _fp_brightness_set),
    # Screenshot (parameter-free)
    (r"\b(?:take|capture|grab|save)\s+(?:a\s+|the\s+)?screenshot\b", _fp_screenshot),
    (r"^\s*screenshot\s*\.?\s*$", _fp_screenshot),
    # Date / time
    (r"\bwhat(?:'?s|\s+is)\s+(?:the\s+)?(?:current\s+)?(?:time|date|day)\b", _fp_datetime),
    (r"\bwhat\s+(?:time|date|day)\s+is\s+it\b", _fp_datetime),
    (r"^\s*time\??\s*$", _fp_datetime),
    # "is X running?"
    (r"\bis\s+(?P<name>[A-Za-z][\w.\-]{1,40})\s+running\b", _fp_process_running),
    # Wi-Fi on/off
    (r"\b(?:turn\s+)?wifi\s+on\b", _fp_wifi_on),
    (r"\b(?:turn\s+)?wifi\s+off\b", _fp_wifi_off),
    (r"\benable\s+wi[-\s]?fi\b", _fp_wifi_on),
    (r"\bdisable\s+wi[-\s]?fi\b", _fp_wifi_off),
    # Internal ping
    (r"^\s*ping\s*\.?\s*$", _fp_ping),
]

_HEURISTIC_COMPILED = [(re.compile(p, re.IGNORECASE), fn) for p, fn in _HEURISTIC_PATTERNS]


def match_fastpath(user_text: str) -> dict[str, Any] | None:
    """Return a {tool, params} dict if any heuristic pattern matches.

    Patterns are ordered most-specific-first; the first match wins. Returns
    None if no pattern matches.
    """
    if not isinstance(user_text, str) or not user_text.strip():
        return None
    for pattern, builder in _HEURISTIC_COMPILED:
        m = pattern.search(user_text)
        if m is None:
            continue
        try:
            call = builder(m)
        except (ValueError, KeyError):
            continue
        if isinstance(call, dict) and "tool" in call:
            return call
    return None


# ---- Tool spec → OpenAI function-tool schema -------------------------------


def _param_to_jsonschema(p: ToolParam) -> dict[str, Any]:
    base: dict[str, Any] = {"description": p.description}
    if p.param_type == "integer":
        base["type"] = "integer"
    elif p.param_type == "boolean":
        base["type"] = "boolean"
    else:
        base["type"] = "string"
    return base


def toolspec_to_openai_tool(spec: ToolSpec) -> dict[str, Any]:
    """Convert a ToolSpec into the OpenAI function-tool format used by llama-server."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in spec.parameters:
        if p.name == "distro":
            continue
        properties[p.name] = _param_to_jsonschema(p)
        if p.required:
            required.append(p.name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": schema,
        },
    }


# ---- System prompt assembly -------------------------------------------------


def _format_rag_block(rag_hits: list[IndexHit]) -> str:
    if not rag_hits:
        return ""
    lines: list[str] = [
        "",
        "Reference material from the local Linux knowledge base — use it to "
        "inform your answer; quote or paraphrase only the parts that help:",
        "",
    ]
    for h in rag_hits:
        chunk = h.entry.rag_chunk
        if chunk is None:
            continue
        lines.append(f'<KNOWLEDGE doc="{chunk.doc_path}" section="{chunk.section}">')
        lines.append(chunk.body.strip())
        lines.append("</KNOWLEDGE>")
        lines.append("")
    return "\n".join(lines)


def build_agent_system_prompt(
    rag_hits: list[IndexHit] | None,
    distro: str,
    base_identity: str = DEFAULT_BASE_IDENTITY,
) -> str:
    """Compose the per-turn system prompt for the agent.

    Includes identity, behaviour guidance, distro hint, and (when present)
    inlined <KNOWLEDGE> blocks for retrieved RAG chunks.
    """
    rag_block = _format_rag_block(rag_hits or [])
    return (
        f"{base_identity.strip()}\n\n"
        "You have a small set of local tools that can read or change this "
        "machine (files under home, processes, audio, brightness, networking, "
        "reminders, screenshots, weather). Call a tool whenever the user is "
        "asking for something one of the provided tools can do; otherwise "
        "reply directly in plain language.\n\n"
        "Never claim you ran, executed, set, changed, or applied anything "
        "unless a tool result is actually present in this conversation.\n\n"
        f"Host distro: {distro}."
        f"{rag_block}"
    )


# ---- Turn planning ---------------------------------------------------------


@dataclass
class TurnPlan:
    """The decision the agent has made about how to handle the current user message."""
    kind: str  # "fastpath" | "llm_tools" | "llm_chat"
    fastpath_call: dict[str, Any] | None = None
    candidate_tools: list[str] = field(default_factory=list)
    rag_hits: list[IndexHit] = field(default_factory=list)
    retrieval_query: str = ""


def decide_turn(user_text: str) -> TurnPlan:
    """Pick a turn strategy based on the user message.

    Order:
    1. Heuristic fast-path (no LLM, no embedding).
    2. Retrieval: if tools-with-native-calling supported and any candidate
       tools clear the threshold, plan an LLM call with a narrow tools list.
    3. Otherwise plan a chat-only LLM call (still inject RAG context).

    Embedding outages collapse the plan to "llm_chat" (no tools, no RAG).
    """
    fp = match_fastpath(user_text)
    if fp is not None:
        _debug_tool(f"fastpath match → {fp['tool']} params={fp['params']!r}")
        return TurnPlan(kind="fastpath", fastpath_call=fp)

    tools_ok = agent_tools_enabled() and supports_tools()
    try:
        result: RetrievalResult = retrieve(
            user_text,
            k_tools=_retrieval_top_k_tools(),
            k_rag=_retrieval_top_k_rag(),
            tool_threshold=_retrieval_tool_threshold(),
            rag_threshold=_retrieval_rag_threshold(),
        )
    except EmbeddingUnavailableError as exc:
        _debug_tool(f"retrieval unavailable: {exc} — falling back to chat-only")
        return TurnPlan(kind="llm_chat", retrieval_query=user_text)

    candidate_tools = result.candidate_tool_names if tools_ok else []
    rag_hits = result.rag

    if candidate_tools:
        return TurnPlan(
            kind="llm_tools",
            candidate_tools=candidate_tools,
            rag_hits=rag_hits,
            retrieval_query=user_text,
        )
    return TurnPlan(
        kind="llm_chat",
        rag_hits=rag_hits,
        retrieval_query=user_text,
    )


# ---- Tool result formatting (cross-turn memory) ----------------------------


def format_tool_result_message(tool_name: str, result: ToolResult) -> str:
    """Verbose tool-result text used inline during a single turn (kept for tests)."""
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
    """Compact assistant memory record kept across turns for context."""
    payload = {
        "tool": tool_name,
        "ok": result.ok,
        "message": result.message,
        "error_code": result.error_code,
        "data": _compact_tool_data(result.data),
    }
    inner = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{TOOL_MEMORY_PREFIX}{inner}"


def _format_role_tool_content(result: ToolResult) -> str:
    payload = {
        "ok": result.ok,
        "message": result.message,
        "error_code": result.error_code,
        "data": _compact_tool_data(result.data),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


# ---- Main per-turn driver --------------------------------------------------


def run_agent_turn(
    history_messages: list[dict[str, Any]],
    user_text: str,
    distro: str,
    base_identity: str = DEFAULT_BASE_IDENTITY,
) -> Iterator[dict[str, Any]]:
    """Drive one user→assistant turn. Generator yielding events for the UI.

    Event shapes:
        {"kind": "thinking", "stage": "fastpath"|"retrieval"|"chat",
         "tools": [...], "rag": [(doc, section, score), ...]}
        {"kind": "tool_running", "tool": str, "params": dict}
        {"kind": "tool_result", "tool": str, "result": ToolResult,
         "memory_message": str}
        {"kind": "content", "text": str}
        {"kind": "done", "memory_messages": [str, ...]}
    """
    plan = decide_turn(user_text)

    if plan.kind == "fastpath":
        yield from _run_fastpath_turn(history_messages, user_text, distro, plan, base_identity)
        return

    if plan.kind == "llm_tools":
        yield from _run_llm_tools_turn(history_messages, user_text, distro, plan, base_identity)
        return

    yield from _run_llm_chat_turn(history_messages, user_text, distro, plan, base_identity)


def _user_message(text: str) -> dict[str, Any]:
    return {"role": "user", "content": text}


def _system_message(text: str) -> dict[str, Any]:
    return {"role": "system", "content": text}


def _run_fastpath_turn(
    history: list[dict[str, Any]],
    user_text: str,
    distro: str,
    plan: TurnPlan,
    base_identity: str,
) -> Iterator[dict[str, Any]]:
    assert plan.fastpath_call is not None
    tool_name = plan.fastpath_call["tool"]
    params = plan.fastpath_call.get("params", {})
    yield {"kind": "thinking", "stage": "fastpath", "tools": [tool_name], "rag": []}
    yield {"kind": "tool_running", "tool": tool_name, "params": params}
    result = run_tool(tool_name, dict(params))
    memory_msg = format_tool_memory_message(tool_name, result)
    yield {
        "kind": "tool_result",
        "tool": tool_name,
        "result": result,
        "memory_message": memory_msg,
    }

    sys_prompt = build_agent_system_prompt(rag_hits=[], distro=distro, base_identity=base_identity)
    role_tool_call_id = "fp_call_1"
    msgs: list[dict[str, Any]] = [
        _system_message(sys_prompt),
        *history,
        _user_message(user_text),
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": role_tool_call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": json.dumps(params, ensure_ascii=False)},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": role_tool_call_id,
            "name": tool_name,
            "content": _format_role_tool_content(result),
        },
    ]
    if not supports_tools():
        # Ollama path: collapse tool-calling messages into a "[Tool result]" user message
        # so the model can summarize without OpenAI-tools schema.
        msgs = [
            _system_message(sys_prompt),
            *history,
            _user_message(user_text),
            _user_message(format_tool_result_message(tool_name, result)),
        ]

    for ev in stream_llm_events(msgs):
        if ev.get("kind") == "content":
            yield ev

    yield {"kind": "done", "memory_messages": [memory_msg]}


def _run_llm_tools_turn(
    history: list[dict[str, Any]],
    user_text: str,
    distro: str,
    plan: TurnPlan,
    base_identity: str,
) -> Iterator[dict[str, Any]]:
    rag_summary = [
        (
            (h.entry.rag_chunk.doc_path if h.entry.rag_chunk else "?"),
            (h.entry.rag_chunk.section if h.entry.rag_chunk else "?"),
            round(h.score, 3),
        )
        for h in plan.rag_hits
    ]
    yield {
        "kind": "thinking",
        "stage": "retrieval",
        "tools": list(plan.candidate_tools),
        "rag": rag_summary,
    }

    sys_prompt = build_agent_system_prompt(plan.rag_hits, distro=distro, base_identity=base_identity)
    msgs: list[dict[str, Any]] = [
        _system_message(sys_prompt),
        *history,
        _user_message(user_text),
    ]
    tools_payload: list[dict[str, Any]] = []
    for name in plan.candidate_tools:
        spec = get_tool(name)
        if spec is None:
            continue
        tools_payload.append(toolspec_to_openai_tool(spec))

    memory_messages: list[str] = []
    accumulated_tool_calls: list[dict[str, Any]] = []
    accumulated_content = ""

    for ev in stream_llm_events(msgs, tools=tools_payload, tool_choice="auto"):
        kind = ev.get("kind")
        if kind == "content":
            chunk = ev.get("text") or ""
            accumulated_content += chunk
            yield ev
        elif kind == "tool_calls":
            accumulated_tool_calls = ev.get("tool_calls") or []

    if not accumulated_tool_calls:
        yield {"kind": "done", "memory_messages": memory_messages}
        return

    # Append assistant tool_calls + per-call role:tool feedback, then ask the
    # model to summarise. Bound the loop with max_agent_passes.
    msgs.append(
        {
            "role": "assistant",
            "content": accumulated_content or "",
            "tool_calls": accumulated_tool_calls,
        }
    )
    for tc in accumulated_tool_calls:
        fn = tc.get("function") or {}
        tool_name = fn.get("name") or ""
        args_str = fn.get("arguments") or "{}"
        try:
            params = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            params = {}
        if not isinstance(params, dict):
            params = {}
        yield {"kind": "tool_running", "tool": tool_name, "params": params}
        result = run_tool(tool_name, dict(params))
        memory_msg = format_tool_memory_message(tool_name, result)
        memory_messages.append(memory_msg)
        yield {
            "kind": "tool_result",
            "tool": tool_name,
            "result": result,
            "memory_message": memory_msg,
        }
        msgs.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id") or f"call_{len(memory_messages)}",
                "name": tool_name,
                "content": _format_role_tool_content(result),
            }
        )

    # Bound the assistant↔tool loop. Each pass: stream model, run any new
    # tool calls, append role:tool messages, repeat. We already executed pass
    # 1 above, so start the counter at 1.
    passes = 1
    cap = max_agent_passes()
    while passes < cap:
        passes += 1
        new_tool_calls: list[dict[str, Any]] = []
        for ev in stream_llm_events(msgs, tools=tools_payload, tool_choice="auto"):
            kind = ev.get("kind")
            if kind == "content":
                yield ev
            elif kind == "tool_calls":
                new_tool_calls = ev.get("tool_calls") or []
        if not new_tool_calls:
            break
        msgs.append({"role": "assistant", "content": "", "tool_calls": new_tool_calls})
        for tc in new_tool_calls:
            fn = tc.get("function") or {}
            tool_name = fn.get("name") or ""
            args_str = fn.get("arguments") or "{}"
            try:
                params = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                params = {}
            if not isinstance(params, dict):
                params = {}
            yield {"kind": "tool_running", "tool": tool_name, "params": params}
            result = run_tool(tool_name, dict(params))
            memory_msg = format_tool_memory_message(tool_name, result)
            memory_messages.append(memory_msg)
            yield {
                "kind": "tool_result",
                "tool": tool_name,
                "result": result,
                "memory_message": memory_msg,
            }
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id") or f"call_{len(memory_messages)}",
                    "name": tool_name,
                    "content": _format_role_tool_content(result),
                }
            )

    yield {"kind": "done", "memory_messages": memory_messages}


def _run_llm_chat_turn(
    history: list[dict[str, Any]],
    user_text: str,
    distro: str,
    plan: TurnPlan,
    base_identity: str,
) -> Iterator[dict[str, Any]]:
    rag_summary = [
        (
            (h.entry.rag_chunk.doc_path if h.entry.rag_chunk else "?"),
            (h.entry.rag_chunk.section if h.entry.rag_chunk else "?"),
            round(h.score, 3),
        )
        for h in plan.rag_hits
    ]
    yield {"kind": "thinking", "stage": "chat", "tools": [], "rag": rag_summary}

    sys_prompt = build_agent_system_prompt(plan.rag_hits, distro=distro, base_identity=base_identity)
    msgs: list[dict[str, Any]] = [
        _system_message(sys_prompt),
        *history,
        _user_message(user_text),
    ]

    for ev in stream_llm_events(msgs):
        if ev.get("kind") == "content":
            yield ev

    yield {"kind": "done", "memory_messages": []}
