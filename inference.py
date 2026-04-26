"""
Dispatch chat streaming to Ollama or llama.cpp (llama-server) based on MEERA_BACKEND.

- MEERA_BACKEND=llamacpp (default): llamacpp_backend.py → llama-server OpenAI API
- MEERA_BACKEND=ollama: backend.py → Ollama /api/chat
"""
from __future__ import annotations

import os
from collections.abc import Iterator


def stream_llm(messages: list) -> Iterator[str]:
    mode = os.environ.get("MEERA_BACKEND", "llamacpp").strip().lower()
    if mode == "llamacpp":
        from llamacpp_backend import stream_llm as _run

        yield from _run(messages)
        return
    from backend import stream_llm as _run

    yield from _run(messages)


def stream_llm_events(messages: list) -> Iterator[dict[str, str]]:
    mode = os.environ.get("MEERA_BACKEND", "llamacpp").strip().lower()
    if mode == "llamacpp":
        from llamacpp_backend import stream_llm_events as _run

        yield from _run(messages)
        return
    from backend import stream_llm_events as _run

    yield from _run(messages)
