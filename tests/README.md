# Tests

Run from the **repository root** (`meera/`), not from inside `tests/`.

## All tests

```bash
cd /path/to/meera
python3 -m unittest discover -s tests -v
```

`tests/test_retrieval.py` sets `MEERA_EMBED_FAKE=1` before importing the embedding client, so retrieval tests do not need a running embedding server. You can still prefix commands with `MEERA_EMBED_FAKE=1` for consistency with docs elsewhere.

## RAG chunk size (512-token cap)

Two tests cover `rag_data/` H2 chunks:

| Test | What it does |
|------|----------------|
| `TestRagChunkSizeCap` | Fast **character** heuristic vs the BGE 512-token limit. **Runs with stock `python3`** (only stdlib + project imports). |
| `TestRagBgeTokenizerCap` | Counts tokens with the real **`BAAI/bge-small-en-v1.5`** tokenizer. **Skipped** unless `transformers` is importable. |

```bash
python3 -m unittest \
  tests.test_retrieval.TestRagChunkSizeCap \
  tests.test_retrieval.TestRagBgeTokenizerCap -v
```

If `TestRagBgeTokenizerCap` is skipped, your interpreter does not have Hugging Face `transformers` (common on PEP 668–managed distros where `pip install` to the system Python is blocked).

### Running the BGE tokenizer test

Pick one:

1. **Virtual environment** (recommended):

   ```bash
   cd /path/to/meera
   python3 -m venv .venv
   .venv/bin/pip install requests transformers sentencepiece
   MEERA_EMBED_FAKE=1 .venv/bin/python -m unittest \
     tests.test_retrieval.TestRagChunkSizeCap \
     tests.test_retrieval.TestRagBgeTokenizerCap -v
   ```

   First run may download tokenizer files for `BAAI/bge-small-en-v1.5` (needs network). PyTorch is **not** required for this test; only the tokenizer is used.

2. **Distro packages**, if available (e.g. Debian/Ubuntu): install `python3-transformers` / `python3-requests` so `python3` can import them, then rerun the unittest command with `python3`.

Do **not** assume `pip install` on the system Python will work without `--break-system-packages`; prefer a venv.
