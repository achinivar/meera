"""
HTTP client for the embedding llama-server (OpenAI-compatible /v1/embeddings).

The embedding server is a separate llama-server instance loaded with a small
sentence-transformer GGUF (default: bge-small-en-v1.5 q8_0). It runs on
MEERA_EMBED_URL (default http://127.0.0.1:8081) and exposes /v1/embeddings.

Vectors are L2-normalized so cosine similarity reduces to a dot product.

Test/dev: set MEERA_EMBED_FAKE=1 to use a deterministic hash-based fake embedder
that does not require the embedding server to be running.
"""
from __future__ import annotations

import hashlib
import math
import os
import struct
from typing import Iterable

import requests


_FAKE_DIM = 384
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_BATCH_SIZE = 128


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the embedding server is unreachable or returns an error.

    Callers (e.g. the retrieval module, agent) should catch this and degrade
    gracefully — typically by skipping retrieval and falling back to plain chat.
    """


def _base_url() -> str:
    return os.environ.get("MEERA_EMBED_URL", "http://127.0.0.1:8081").rstrip("/")


def _model_name() -> str:
    return os.environ.get("MEERA_EMBED_MODEL", "local")


def _fake_enabled() -> bool:
    return os.environ.get("MEERA_EMBED_FAKE", "").strip().lower() in ("1", "true", "yes", "on")


def _batch_size() -> int:
    """How many inputs to POST per /v1/embeddings request.

    llama-server allocates a fixed parallel-slot / KV-cache budget at startup,
    so very large single requests can exceed that budget and 500. Splitting
    into chunks of this size keeps each request well within typical defaults
    while still amortizing HTTP overhead. Override with MEERA_EMBED_BATCH_SIZE.
    """
    try:
        n = int(os.environ.get("MEERA_EMBED_BATCH_SIZE", str(_DEFAULT_BATCH_SIZE)))
    except ValueError:
        return _DEFAULT_BATCH_SIZE
    return max(1, n)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [v / norm for v in vec]


def _fake_embed_one(text: str) -> list[float]:
    """Deterministic hash-derived vector for offline tests.

    Maps each text to a fixed 384-d unit vector. Different texts get different
    vectors (with high probability), but the geometry is meaningless — only
    use this for code-path tests, not retrieval-quality tests.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    floats: list[float] = []
    while len(floats) < _FAKE_DIM:
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                break
            (val,) = struct.unpack("<I", chunk)
            floats.append((val / 0xFFFFFFFF) * 2.0 - 1.0)
            if len(floats) >= _FAKE_DIM:
                break
        digest = hashlib.sha256(digest).digest()
    return _l2_normalize(floats[:_FAKE_DIM])


def _post_embed_chunk(items: list[str]) -> list[list[float]]:
    """POST one chunk to /v1/embeddings and return one normalized vector per item."""
    url = f"{_base_url()}/v1/embeddings"
    payload = {"model": _model_name(), "input": items}
    try:
        resp = requests.post(url, json=payload, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise EmbeddingUnavailableError(
            f"Embedding server unreachable at {url}: {exc}"
        ) from exc

    try:
        body = resp.json()
    except ValueError as exc:
        raise EmbeddingUnavailableError(
            f"Embedding server returned non-JSON response: {exc}"
        ) from exc

    err = body.get("error") if isinstance(body, dict) else None
    if err is not None:
        msg = err if isinstance(err, str) else err.get("message", str(err))
        raise EmbeddingUnavailableError(f"Embedding server error: {msg}")

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or len(data) != len(items):
        raise EmbeddingUnavailableError(
            f"Embedding server returned malformed payload (expected {len(items)} items)"
        )

    out: list[list[float]] = [None] * len(items)  # type: ignore[list-item]
    for entry in data:
        if not isinstance(entry, dict):
            raise EmbeddingUnavailableError("Embedding payload contains non-dict entry")
        idx = entry.get("index")
        vec = entry.get("embedding")
        if not isinstance(idx, int) or not isinstance(vec, list):
            raise EmbeddingUnavailableError("Embedding payload missing index/embedding")
        if idx < 0 or idx >= len(items):
            raise EmbeddingUnavailableError(f"Embedding index out of range: {idx}")
        try:
            floats = [float(v) for v in vec]
        except (TypeError, ValueError) as exc:
            raise EmbeddingUnavailableError(f"Embedding vector has non-numeric entries: {exc}") from exc
        out[idx] = _l2_normalize(floats)

    if any(v is None for v in out):
        raise EmbeddingUnavailableError("Embedding server returned incomplete batch")
    return out  # type: ignore[return-value]


def embed_batch(texts: Iterable[str]) -> list[list[float]]:
    """Return one L2-normalized vector per input text, in the same order.

    Inputs are split into chunks of MEERA_EMBED_BATCH_SIZE (default 128) and
    POSTed sequentially, then concatenated. This keeps each /v1/embeddings
    request well within llama-server's parallel-slot budget regardless of how
    many tools / RAG chunks the index has accumulated.
    """
    items = [t if isinstance(t, str) else str(t) for t in texts]
    if not items:
        return []

    if _fake_enabled():
        return [_fake_embed_one(t) for t in items]

    chunk = _batch_size()
    out: list[list[float]] = []
    for start in range(0, len(items), chunk):
        out.extend(_post_embed_chunk(items[start : start + chunk]))
    return out


def embed_one(text: str) -> list[float]:
    """Return a single L2-normalized vector."""
    vectors = embed_batch([text])
    if not vectors:
        raise EmbeddingUnavailableError("Empty embedding result")
    return vectors[0]


def embedder_available() -> bool:
    """Cheap reachability probe; True iff /v1/models responds (or fake mode is on)."""
    if _fake_enabled():
        return True
    url = f"{_base_url()}/v1/models"
    try:
        resp = requests.get(url, timeout=3.0)
        return resp.ok
    except requests.exceptions.RequestException:
        return False
