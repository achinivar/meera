"""Retrieval package: tool-exemplar + RAG-chunk index over local embeddings.

Public API:
    - RetrievalIndex / IndexEntry / IndexHit (index.py)
    - chunk_rag_directory (rag_chunker.py)
    - get_index / build_index / RetrievalResult (query.py)
"""
from retrieval.index import IndexEntry, IndexHit, RetrievalIndex
from retrieval.query import (
    RetrievalResult,
    build_index,
    get_index,
    reset_index,
    retrieve,
)
from retrieval.rag_chunker import RagChunk, chunk_rag_directory

__all__ = [
    "IndexEntry",
    "IndexHit",
    "RetrievalIndex",
    "RagChunk",
    "RetrievalResult",
    "build_index",
    "chunk_rag_directory",
    "get_index",
    "reset_index",
    "retrieve",
]
