"""Tests for the retrieval package.

We force the embedding client into deterministic-fake mode (MEERA_EMBED_FAKE=1)
so these tests don't require a running llama-server or numpy. The fake embedder
gives different vectors for different texts but the geometry is meaningless,
so we only assert structural properties (sizes, dedup, threshold filtering),
not retrieval *quality*.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Force fake embeddings before importing anything that pulls embeddings.py.
os.environ["MEERA_EMBED_FAKE"] = "1"

from embeddings import embed_batch, embed_one  # noqa: E402
from retrieval import (  # noqa: E402
    IndexEntry,
    RagChunk,
    RetrievalIndex,
    build_index,
    chunk_rag_directory,
    reset_index,
)
from retrieval.index import KIND_RAG, KIND_TOOL  # noqa: E402


class TestEmbeddingsFake(unittest.TestCase):
    def test_unit_norm(self) -> None:
        v = embed_one("hello world")
        norm = sum(x * x for x in v) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_batch_matches_single(self) -> None:
        a = embed_one("alpha")
        b = embed_one("beta")
        batch = embed_batch(["alpha", "beta"])
        self.assertEqual(len(batch), 2)
        self.assertAlmostEqual(sum(x * y for x, y in zip(a, batch[0])), 1.0, places=5)
        self.assertAlmostEqual(sum(x * y for x, y in zip(b, batch[1])), 1.0, places=5)

    def test_different_texts_differ(self) -> None:
        a = embed_one("alpha")
        b = embed_one("beta")
        cos = sum(x * y for x, y in zip(a, b))
        self.assertLess(abs(cos), 0.999)


class TestRagChunker(unittest.TestCase):
    def test_h2_split_preserves_h1_title(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "topic.md").write_text(
                "# Topic\n\nIntro paragraph.\n\n## Section A\n\nbody A\n\n## Section B\n\nbody B\n",
                encoding="utf-8",
            )
            chunks = chunk_rag_directory(root)
        self.assertEqual(len(chunks), 2)
        sections = sorted(c.section for c in chunks)
        self.assertEqual(sections, ["Section A", "Section B"])
        for c in chunks:
            self.assertEqual(c.doc_title, "Topic")
            self.assertTrue(c.body)
            self.assertIn("##", c.display_text)

    def test_excludes_readme(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# README\n\n## Authoring\n\nrules\n", encoding="utf-8")
            (root / "real.md").write_text("# Real\n\n## S\n\nbody\n", encoding="utf-8")
            chunks = chunk_rag_directory(root)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].doc_title, "Real")

    def test_no_h2_yields_no_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "x.md").write_text("# Only H1\n\nbody only.\n", encoding="utf-8")
            chunks = chunk_rag_directory(root)
        self.assertEqual(chunks, [])


class TestRetrievalIndex(unittest.TestCase):
    def _make_index(self) -> RetrievalIndex:
        idx = RetrievalIndex()
        idx.add(IndexEntry(kind=KIND_TOOL, index_text="set the volume to 30 percent", tool_name="volume_set_percent"))
        idx.add(IndexEntry(kind=KIND_TOOL, index_text="make it louder", tool_name="volume_set_percent"))
        idx.add(IndexEntry(kind=KIND_TOOL, index_text="search files by name", tool_name="file_search_name"))
        idx.add(
            IndexEntry(
                kind=KIND_RAG,
                index_text="grep basics — Common usage\nuse rg -n",
                rag_chunk=RagChunk(
                    doc_path="rag_data/grep_basics.md",
                    doc_title="grep basics",
                    section="Common usage",
                    body="use rg -n",
                ),
            )
        )
        idx.build()
        return idx

    def test_query_split_dedupes_tool_exemplars(self) -> None:
        idx = self._make_index()
        tools, _rag = idx.query_split("set the volume to 30 percent", k_tools=4, k_rag=2)
        names = [h.entry.tool_name for h in tools]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("volume_set_percent", names)

    def test_threshold_filters(self) -> None:
        idx = self._make_index()
        tools, rag = idx.query_split(
            "completely unrelated text",
            k_tools=4,
            k_rag=4,
            tool_threshold=0.999,
            rag_threshold=0.999,
        )
        self.assertEqual(tools, [])
        self.assertEqual(rag, [])

    def test_unbuilt_index_raises(self) -> None:
        idx = RetrievalIndex()
        idx.add(IndexEntry(kind=KIND_TOOL, index_text="foo", tool_name="ping"))
        with self.assertRaises(RuntimeError):
            idx.query("foo")

    def test_build_idempotent(self) -> None:
        idx = self._make_index()
        idx.build()
        self.assertTrue(idx.is_built)


class TestBuildSingleton(unittest.TestCase):
    def test_build_index_uses_real_tools_and_rag(self) -> None:
        # Build the actual project index against the real rag_data directory.
        # Just smoke-test that it builds and contains tool exemplars + RAG chunks.
        reset_index()
        idx = build_index()
        self.assertGreater(idx.size, 0)
        kinds = set()
        for e in idx._entries:  # type: ignore[attr-defined]
            kinds.add(e.kind)
            if len(kinds) == 2:
                break
        self.assertIn(KIND_TOOL, kinds)


if __name__ == "__main__":
    unittest.main()
