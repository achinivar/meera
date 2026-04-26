"""In-memory cosine-similarity retrieval index.

Pure-Python (no numpy dependency) — sized for hundreds to a few thousand
entries which is enough for this project's tool exemplars + RAG chunks. Each
vector is L2-normalized at ingest time so cosine similarity reduces to a dot
product.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from embeddings import embed_batch
from retrieval.rag_chunker import RagChunk


KIND_TOOL = "tool_exemplar"
KIND_RAG = "rag_chunk"


@dataclass(frozen=True)
class IndexEntry:
    """One indexed item — either a tool exemplar or a RAG chunk."""
    kind: str          # KIND_TOOL or KIND_RAG
    index_text: str    # text fed to the embedder
    tool_name: str | None = None     # only set for KIND_TOOL
    rag_chunk: RagChunk | None = None  # only set for KIND_RAG


@dataclass(frozen=True)
class IndexHit:
    entry: IndexEntry
    score: float


def _dot(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n != len(b):
        return 0.0
    s = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s


@dataclass
class RetrievalIndex:
    """Holds entries + their embeddings, supports top-k cosine queries."""
    _entries: list[IndexEntry] = field(default_factory=list)
    _vectors: list[list[float]] = field(default_factory=list)
    _built: bool = False

    def add(self, entry: IndexEntry) -> None:
        if self._built:
            raise RuntimeError("Cannot add entries after build()")
        self._entries.append(entry)

    def add_many(self, entries: Iterable[IndexEntry]) -> None:
        for e in entries:
            self.add(e)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def is_built(self) -> bool:
        return self._built

    def build(self) -> None:
        """Embed all queued entries in a single batch call. Idempotent.

        Raises EmbeddingUnavailableError if the embedding server is unreachable.
        """
        if self._built:
            return
        if not self._entries:
            self._vectors = []
            self._built = True
            return
        texts = [e.index_text for e in self._entries]
        self._vectors = embed_batch(texts)
        if len(self._vectors) != len(self._entries):
            raise RuntimeError(
                f"Embedding count mismatch: got {len(self._vectors)} for {len(self._entries)} entries"
            )
        self._built = True

    def _query_vector(self, text: str) -> list[float]:
        return embed_batch([text])[0]

    def query(self, text: str, k: int = 8) -> list[IndexHit]:
        """Return the top-k entries by cosine similarity."""
        if not self._built:
            raise RuntimeError("Index not built — call build() first")
        if not self._entries or k <= 0:
            return []
        qv = self._query_vector(text)
        scored = [
            IndexHit(entry=self._entries[i], score=_dot(qv, self._vectors[i]))
            for i in range(len(self._entries))
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

    def query_split(
        self,
        text: str,
        k_tools: int = 4,
        k_rag: int = 3,
        tool_threshold: float = 0.0,
        rag_threshold: float = 0.0,
    ) -> tuple[list[IndexHit], list[IndexHit]]:
        """Return (tool_hits, rag_hits), each thresholded and deduped.

        Tool hits are deduplicated by tool_name (keeping the highest-scoring
        exemplar for each tool). RAG hits are deduplicated by (doc, section).
        """
        if not self._built:
            raise RuntimeError("Index not built — call build() first")
        if not self._entries:
            return [], []
        qv = self._query_vector(text)

        tool_best: dict[str, IndexHit] = {}
        rag_best: dict[tuple[str, str], IndexHit] = {}
        for i, entry in enumerate(self._entries):
            score = _dot(qv, self._vectors[i])
            if entry.kind == KIND_TOOL and entry.tool_name is not None:
                if score < tool_threshold:
                    continue
                cur = tool_best.get(entry.tool_name)
                if cur is None or score > cur.score:
                    tool_best[entry.tool_name] = IndexHit(entry=entry, score=score)
            elif entry.kind == KIND_RAG and entry.rag_chunk is not None:
                if score < rag_threshold:
                    continue
                key = (entry.rag_chunk.doc_path, entry.rag_chunk.section)
                cur = rag_best.get(key)
                if cur is None or score > cur.score:
                    rag_best[key] = IndexHit(entry=entry, score=score)

        tools_sorted = sorted(tool_best.values(), key=lambda h: h.score, reverse=True)
        rag_sorted = sorted(rag_best.values(), key=lambda h: h.score, reverse=True)
        return tools_sorted[:k_tools], rag_sorted[:k_rag]
