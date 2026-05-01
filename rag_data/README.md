# RAG knowledge base (`rag_data`)

## Adding a document

1. **Path** — Add a new `*.md` file **in this directory** (`rag_data/`). Only top-level `rag_data/*.md` files are indexed; the chunker does not walk subdirectories.

2. **Structure** — Start with a single **`# Title`** line. Split the rest into sections with **`## Section name`**. Chunks are cut at each `##`; everything before the first `##` is not embedded (keep it short—intro only). Use `###` inside a section for subheadings; they stay part of the same chunk.

3. **Content** — Write for short, factual passages the model can quote. Prefer concrete commands, flags, and caveats. The embedder sees `Title — Section` plus the body, so section titles should match how users might ask (e.g. “Network diagnostics”, not “Part 2”).

4. **Chunk size (512 tokens)** — Each `##` section is one retrieval chunk. The embedding model (`bge-small-en-v1.5`) accepts **at most 512 tokens** per chunk, including the title and section line in the indexed text. If a section grows too large, split it into additional `##` headings. The test suite in `tests/test_retrieval.py` guards this: `TestRagChunkSizeCap` (fast char heuristic) always runs; `TestRagBgeTokenizerCap` counts tokens with the real tokenizer when `transformers` is installed.

5. **Exclude** — `README.md` is never indexed (authoring only).

6. **Pick up changes** — Restart Meera (or restart the process that builds the retrieval index) so new files are embedded.

Run the chunk-size tests (optional locally):

```bash
MEERA_EMBED_FAKE=1 python3 -m unittest \
  tests.test_retrieval.TestRagChunkSizeCap \
  tests.test_retrieval.TestRagBgeTokenizerCap -v
```

(`TestRagBgeTokenizerCap` is skipped unless `transformers` is installed.)

## Layout

- **`*.md`** (except `README.md`) — chunked at `##` and embedded for retrieval.

Repo root `README.md` may duplicate high-level RAG notes; this file is the authoring source of truth for `rag_data/`.
