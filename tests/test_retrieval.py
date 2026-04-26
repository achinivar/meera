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
from unittest.mock import patch

# Force fake embeddings before importing anything that pulls embeddings.py.
os.environ["MEERA_EMBED_FAKE"] = "1"

import embeddings  # noqa: E402
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


class _FakeEmbedResponse:
    """Stand-in for requests.Response carrying a fake /v1/embeddings body.

    Each input "text-N" is encoded as the 3-D vector (N+1, 1, 0). After L2
    normalization the first coordinate stays monotonic in N, so callers can
    recover the original input ordering across chunks.
    """

    def __init__(self, items: list[str]) -> None:
        self._items = items
        self.ok = True

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        data = []
        for i, txt in enumerate(self._items):
            n = int(txt.rsplit("-", 1)[1])
            data.append({"index": i, "embedding": [float(n + 1), 1.0, 0.0]})
        return {"data": data}


class TestEmbedBatchChunking(unittest.TestCase):
    """Verify embed_batch splits inputs into MEERA_EMBED_BATCH_SIZE-sized POSTs."""

    def _run_with_real_http(self, env: dict[str, str]) -> tuple[list[list[float]], list]:
        """Invoke embed_batch with HTTP path enabled and a mocked requests.post."""
        items = [f"text-{i}" for i in range(10)]
        captured: list = []

        def fake_post(url, json=None, timeout=None):  # noqa: A002 — mirrors requests API
            captured.append({"url": url, "json": json, "timeout": timeout})
            return _FakeEmbedResponse(json["input"])

        env_patch = {**env, "MEERA_EMBED_FAKE": "0"}
        with patch.dict(os.environ, env_patch, clear=False), patch.object(
            embeddings.requests, "post", side_effect=fake_post
        ):
            out = embed_batch(items)
        return out, captured

    def test_single_chunk_when_under_batch_size(self) -> None:
        out, calls = self._run_with_real_http({"MEERA_EMBED_BATCH_SIZE": "128"})
        self.assertEqual(len(out), 10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]["json"]["input"]), 10)

    def test_splits_into_multiple_chunks(self) -> None:
        out, calls = self._run_with_real_http({"MEERA_EMBED_BATCH_SIZE": "4"})
        self.assertEqual(len(out), 10)
        self.assertEqual(len(calls), 3)
        self.assertEqual([len(c["json"]["input"]) for c in calls], [4, 4, 2])

    def test_preserves_order_across_chunks(self) -> None:
        out, calls = self._run_with_real_http({"MEERA_EMBED_BATCH_SIZE": "3"})
        flat_inputs: list[str] = []
        for c in calls:
            flat_inputs.extend(c["json"]["input"])
        self.assertEqual(flat_inputs, [f"text-{i}" for i in range(10)])
        # First coord encodes (n+1) before L2-normalization; after normalization
        # it stays strictly monotonic in n, so the global output order must be
        # increasing in vec[0] — proving cross-chunk order is preserved.
        first = [v[0] for v in out]
        self.assertEqual(len(first), 10)
        for a, b in zip(first, first[1:]):
            self.assertLess(a, b)

    def test_empty_input_makes_no_request(self) -> None:
        captured: list = []

        def fake_post(*a, **kw):
            captured.append((a, kw))
            return _FakeEmbedResponse([])

        with patch.dict(os.environ, {"MEERA_EMBED_FAKE": "0"}, clear=False), patch.object(
            embeddings.requests, "post", side_effect=fake_post
        ):
            self.assertEqual(embed_batch([]), [])
        self.assertEqual(captured, [])

    def test_invalid_batch_size_env_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"MEERA_EMBED_BATCH_SIZE": "not-a-number"}, clear=False):
            self.assertEqual(embeddings._batch_size(), 128)
        with patch.dict(os.environ, {"MEERA_EMBED_BATCH_SIZE": "0"}, clear=False):
            self.assertEqual(embeddings._batch_size(), 1)


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


class TestRagChunkSizeCap(unittest.TestCase):
    """Guard against RAG chunks that exceed the embedding model's input cap.

    The embedding server runs `bge-small-en-v1.5`, which has a hard 512-token
    input limit. A single oversized H2 makes the whole index build fail with a
    500 from llama-server, which silently disables retrieval. To prevent that
    regression we cap each chunk's `index_text` at a conservative byte length:

      max_chars = (512 - safety_margin) * worst_case_chars_per_token

    The worst-case ratio (~2.88 chars/token) was measured from a real failure:
    a 2700-char table chunk tokenized to 939 tokens. A 32-token safety margin
    covers `[CLS]`/`[SEP]`, title/heading variation, and tokenizer surprises.
    """

    EMBED_MODEL_TOKEN_CAP = 512
    SAFETY_MARGIN_TOKENS = 32
    WORST_CASE_CHARS_PER_TOKEN = 2.88

    @classmethod
    def _max_chars(cls) -> int:
        return int(
            (cls.EMBED_MODEL_TOKEN_CAP - cls.SAFETY_MARGIN_TOKENS)
            * cls.WORST_CASE_CHARS_PER_TOKEN
        )

    def test_no_rag_chunk_exceeds_embedding_cap(self) -> None:
        rag_root = Path(__file__).resolve().parent.parent / "rag_data"
        chunks = chunk_rag_directory(rag_root)
        self.assertGreater(len(chunks), 0, f"no rag chunks found under {rag_root}")
        cap = self._max_chars()
        oversized = [
            (c.doc_path, c.section, len(c.index_text))
            for c in chunks
            if len(c.index_text) > cap
        ]
        if oversized:
            details = "\n".join(
                f"  {path} :: {section} — {n} chars (cap {cap})"
                for path, section, n in oversized
            )
            self.fail(
                "Oversized rag_data H2 chunk(s) would blow past the "
                f"{self.EMBED_MODEL_TOKEN_CAP}-token embedding-model cap; "
                "split the H2 into smaller sections:\n" + details
            )


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
