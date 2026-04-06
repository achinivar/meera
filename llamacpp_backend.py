"""
Streaming chat client for llama.cpp's HTTP server (OpenAI-compatible /v1/chat/completions).

Env: MEERA_LLAMACPP_URL (default http://127.0.0.1:8080), MEERA_LLAMACPP_MODEL (default local).
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator

import requests

_MAX_TOKENS = 1024  # align with backend.py Ollama num_predict


def _base_url() -> str:
    return os.environ.get("MEERA_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")


def _model_name() -> str:
    return os.environ.get("MEERA_LLAMACPP_MODEL", "local")


def stream_llm(messages: list) -> Iterator[str]:
    """Yield assistant text chunks from llama-server SSE stream."""
    url = f"{_base_url()}/v1/chat/completions"
    payload = {
        "model": _model_name(),
        "messages": messages,
        "stream": True,
        "max_tokens": _MAX_TOKENS,
        # Match Ollama backend.py think: false for Qwen-style models (llama-server chat template).
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        with requests.post(url, json=payload, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            # OpenAI-style SSE is UTF-8 JSON; without charset, requests may decode as latin-1 and break emojis.
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
                    yield f"[Model error: {msg}]"
                    break
                for choice in obj.get("choices") or []:
                    delta = choice.get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield chunk
    except Exception as e:
        yield f"[Error contacting model: {e}]"
