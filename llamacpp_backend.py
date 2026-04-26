"""
Streaming chat client for llama.cpp's HTTP server (OpenAI-compatible /v1/chat/completions).

Supports two flavors:
- Plain streaming chat (no tools)        → yields {"kind":"content"} events
- Streaming with native OpenAI tools     → yields {"kind":"content"} progressively,
                                            then {"kind":"tool_calls", "tool_calls":[...]}
                                            once the response is complete.

Env: MEERA_LLAMACPP_URL (default http://127.0.0.1:8080), MEERA_LLAMACPP_MODEL (default local).
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import requests

_MAX_TOKENS = 1024  # align with backend.py Ollama num_predict


def _base_url() -> str:
    return os.environ.get("MEERA_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")


def _model_name() -> str:
    return os.environ.get("MEERA_LLAMACPP_MODEL", "local")


def _merge_tool_call_delta(acc: list[dict[str, Any]], delta_calls: list[dict[str, Any]]) -> None:
    """Merge an OpenAI streaming tool_calls delta into the running accumulator.

    Each delta entry has an `index`. Fields (id, type, function.name,
    function.arguments) arrive piecewise; arguments in particular is a JSON
    string streamed character-by-character. We append to `arguments` and
    overwrite scalar fields when present.
    """
    for d in delta_calls:
        if not isinstance(d, dict):
            continue
        idx = d.get("index", 0)
        while len(acc) <= idx:
            acc.append({"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
        cur = acc[idx]
        if d.get("id"):
            cur["id"] = d["id"]
        if d.get("type"):
            cur["type"] = d["type"]
        fn = d.get("function") or {}
        cur_fn = cur.setdefault("function", {"name": "", "arguments": ""})
        name_part = fn.get("name")
        if isinstance(name_part, str) and name_part:
            cur_fn["name"] = (cur_fn.get("name") or "") + name_part
        args_part = fn.get("arguments")
        if isinstance(args_part, str) and args_part:
            cur_fn["arguments"] = (cur_fn.get("arguments") or "") + args_part


def stream_llm_events(
    messages: list,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield assistant events from llama-server SSE stream.

    When `tools` is provided, accumulated tool_calls are emitted as a single
    {"kind": "tool_calls"} event after the stream completes.
    """
    url = f"{_base_url()}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": _model_name(),
        "messages": messages,
        "stream": True,
        "max_tokens": _MAX_TOKENS,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"

    tool_call_acc: list[dict[str, Any]] = []
    try:
        with requests.post(url, json=payload, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            resp.encoding = "utf-8"
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line.split(":", 1)[1].lstrip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                err = obj.get("error")
                if err is not None:
                    msg = err if isinstance(err, str) else err.get("message", str(err))
                    yield {"kind": "content", "text": f"[Model error: {msg}]"}
                    break
                for choice in obj.get("choices") or []:
                    delta = choice.get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield {"kind": "content", "text": chunk}
                    delta_tools = delta.get("tool_calls")
                    if isinstance(delta_tools, list) and delta_tools:
                        _merge_tool_call_delta(tool_call_acc, delta_tools)
    except Exception as e:
        yield {"kind": "content", "text": f"[Error contacting model: {e}]"}
        return

    if tool_call_acc:
        yield {"kind": "tool_calls", "tool_calls": tool_call_acc}


def stream_llm(messages: list) -> Iterator[str]:
    """Backward-compatible content-only text stream."""
    for event in stream_llm_events(messages):
        if event.get("kind") == "content":
            chunk = event.get("text")
            if chunk:
                yield chunk
