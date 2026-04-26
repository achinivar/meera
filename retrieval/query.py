"""High-level retrieval: build a process-wide index from tools + rag_data.

Public surface:
    - build_index(): assemble (but don't cache) a fresh RetrievalIndex
    - get_index(): lazy, cached singleton (build on first call)
    - reset_index(): clear the singleton (used by tests)
    - retrieve(): convenience wrapper returning a RetrievalResult
"""
from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from embeddings import EmbeddingUnavailableError
from retrieval.index import (
    KIND_RAG,
    KIND_TOOL,
    IndexEntry,
    IndexHit,
    RetrievalIndex,
)
from retrieval.rag_chunker import chunk_rag_directory
from tools.registry import TOOLS

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_RAG_DIR = _PROJECT_ROOT / "rag_data"


@dataclass
class RetrievalResult:
    """Outcome of one retrieval over the user query."""
    query: str
    tools: list[IndexHit] = field(default_factory=list)
    rag: list[IndexHit] = field(default_factory=list)

    @property
    def candidate_tool_names(self) -> list[str]:
        return [h.entry.tool_name for h in self.tools if h.entry.tool_name]


def _debug_retrieval_enabled() -> bool:
    return os.environ.get("MEERA_DEBUG_RETRIEVAL", "").strip().lower() in ("1", "true", "yes", "on")


def _debug(msg: str) -> None:
    if _debug_retrieval_enabled():
        print(f"[retrieval] {msg}", file=sys.stderr, flush=True)


def _populate_tool_entries(index: RetrievalIndex) -> int:
    count = 0
    for spec in TOOLS:
        for ex in spec.exemplars:
            if not isinstance(ex, str) or not ex.strip():
                continue
            index.add(
                IndexEntry(
                    kind=KIND_TOOL,
                    index_text=ex.strip(),
                    tool_name=spec.name,
                )
            )
            count += 1
    return count


def _populate_rag_entries(index: RetrievalIndex, rag_dir: Path) -> int:
    chunks = chunk_rag_directory(rag_dir)
    for c in chunks:
        index.add(
            IndexEntry(
                kind=KIND_RAG,
                index_text=c.index_text,
                rag_chunk=c,
            )
        )
    return len(chunks)


def build_index(rag_dir: Path | None = None) -> RetrievalIndex:
    """Construct and embed a fresh RetrievalIndex.

    Raises EmbeddingUnavailableError if the embedding server is unreachable.
    Callers that want a graceful no-retrieval fallback should catch this.
    """
    rag_dir = rag_dir or _DEFAULT_RAG_DIR
    index = RetrievalIndex()
    n_tools = _populate_tool_entries(index)
    n_rag = _populate_rag_entries(index, rag_dir)
    _debug(f"queued entries: {n_tools} tool exemplars + {n_rag} rag chunks")
    index.build()
    _debug(f"index built ({index.size} entries embedded)")
    return index


_lock = threading.Lock()
_singleton: RetrievalIndex | None = None
_build_error: Exception | None = None


def get_index(rag_dir: Path | None = None) -> RetrievalIndex:
    """Return a process-wide singleton index, building it on first call.

    Subsequent calls return the same object. If the first build fails, the
    failure is cached and re-raised — call reset_index() to retry.
    """
    global _singleton, _build_error
    with _lock:
        if _singleton is not None:
            return _singleton
        if _build_error is not None:
            raise _build_error
        try:
            _singleton = build_index(rag_dir)
        except Exception as exc:
            _build_error = exc
            raise
        return _singleton


def reset_index() -> None:
    """Drop the cached singleton; next get_index() will rebuild."""
    global _singleton, _build_error
    with _lock:
        _singleton = None
        _build_error = None


def retrieve(
    query: str,
    k_tools: int = 4,
    k_rag: int = 3,
    tool_threshold: float = 0.0,
    rag_threshold: float = 0.0,
    index: RetrievalIndex | None = None,
) -> RetrievalResult:
    """Convenience wrapper: query the singleton and return a RetrievalResult.

    Returns an empty RetrievalResult on EmbeddingUnavailableError so callers
    can degrade gracefully without try/except boilerplate at every call site.
    """
    idx = index if index is not None else _try_get_index()
    if idx is None:
        return RetrievalResult(query=query)
    try:
        tools, rag = idx.query_split(
            query,
            k_tools=k_tools,
            k_rag=k_rag,
            tool_threshold=tool_threshold,
            rag_threshold=rag_threshold,
        )
    except EmbeddingUnavailableError as exc:
        _debug(f"retrieve failed: {exc}")
        return RetrievalResult(query=query)
    if _debug_retrieval_enabled():
        names = [(h.entry.tool_name, round(h.score, 3)) for h in tools]
        rags = [
            (
                h.entry.rag_chunk.doc_path if h.entry.rag_chunk else "?",
                h.entry.rag_chunk.section if h.entry.rag_chunk else "?",
                round(h.score, 3),
            )
            for h in rag
        ]
        _debug(f"query={query!r} tools={names} rag={rags}")
    return RetrievalResult(query=query, tools=tools, rag=rag)


def _try_get_index() -> RetrievalIndex | None:
    """Best-effort access to the singleton; returns None if unavailable."""
    try:
        return get_index()
    except EmbeddingUnavailableError as exc:
        _debug(f"index unavailable: {exc}")
        return None
