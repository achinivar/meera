"""
Dispatch chat streaming to Ollama or llama.cpp (llama-server) based on MEERA_BACKEND.

- MEERA_BACKEND=llamacpp (default): llamacpp_backend.py → llama-server OpenAI API
- MEERA_BACKEND=ollama: backend.py → Ollama /api/chat

Native tool calling (`tools` / `tool_choice`) is implemented for the llama.cpp
backend only. The Ollama backend silently ignores those args (callers fall back
to chat-only mode).
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any


def _backend_mode() -> str:
    return os.environ.get("MEERA_BACKEND", "llamacpp").strip().lower()


def supports_tools() -> bool:
    """True when the active backend can handle native tool calling."""
    return _backend_mode() == "llamacpp"


def stream_llm(messages: list) -> Iterator[str]:
    mode = _backend_mode()
    if mode == "llamacpp":
        from llamacpp_backend import stream_llm as _run

        yield from _run(messages)
        return
    from backend import stream_llm as _run

    yield from _run(messages)


def stream_llm_events(
    messages: list,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    mode = _backend_mode()
    if mode == "llamacpp":
        from llamacpp_backend import stream_llm_events as _run

        yield from _run(messages, tools=tools, tool_choice=tool_choice)
        return
    from backend import stream_llm_events as _run

    yield from _run(messages)
