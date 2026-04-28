# Meera — AI Assistant for Linux Gnome Desktops

Meera is a local-first AI assistant for Linux GNOME desktops. It provides a native GTK4 chat UI, uses `llama.cpp` model servers locally, and includes optional allowlisted desktop tools through a retrieval-first agent loop.

## Overview

- Native GTK4 desktop app, designed for GNOME
- Local `llama.cpp` chat + embedding servers managed by the launcher
- Streaming chat responses with Markdown rendering
- Built-in chat history with load/new-chat actions
- Optional tool-enabled assistant mode (`MEERA_AGENT_TOOLS=1`, default)
- Local model cache and first-run setup flow

## Installation

Clone the repo and run the installer:

```bash
git clone https://github.com/achinivar/meera.git
cd meera
chmod +x install.sh
./install.sh
```

After install, launch with:

```bash
meera
```

Useful commands:

```bash
meera doctor
meera logs
meera restart-model
meera unload-model
meera uninstall
```

## Requirements

- Linux desktop (GNOME recommended)
- Python 3.10+
- Network access on first run (to download pinned `llama.cpp` bundle and default models)

The installer currently supports dependency installation on:

- Ubuntu / Debian (`apt`)
- Fedora (`dnf`, excluding immutable ostree auto-installs)

## Runtime Notes

- Meera runs local `llama.cpp` servers for chat and embeddings.
- Default setup downloads pinned artifacts and verifies checksums where configured.
- Chat history is saved automatically and can be loaded from the app menu.

## Key directories:

- `ui/` — GTK UI
- `tools/` — allowlisted desktop tools
- `retrieval/` and `rag_data/` — retrieval + local knowledge chunks
- `scripts/` — installer/launcher helper scripts

## Configuration

- `MEERA_AGENT_TOOLS` — `1` (default) enables tool-capable agent loop; `0` for plain chat
- `MEERA_AGENT_MAX_PASSES` — max assistant↔tool passes per message (default `3`)
- `MEERA_DEBUG_TOOL_CALLS` — set `1` to show tool debug lines in UI
- `MEERA_DEBUG_RETRIEVAL` — set `1` to show retrieval debug output

## Adding a tool

1. Pick or create a module under `tools/` (e.g. `tools/files.py`).
2. Define a handler with the signature `handler(args: dict) -> ToolResult` and add a `ToolSpec(name=..., description=..., parameters=[...], handler=...)` to the module's exported list.
3. **Add 5–10 `exemplars`** — natural-language phrases real users would type. These power retrieval; the test in `tests/test_tools.py::test_every_tool_has_exemplars` enforces a minimum.
4. Register the spec by exporting it from your module and listing it in `tools/registry.py::TOOLS`.
5. Restart Meera. The retrieval index is rebuilt at startup, so the new tool is immediately reachable.

## Adding RAG data

1. Drop a Markdown file into `rag_data/` (lowercase filename, ending in `.md`). `README.md` in that folder is excluded from the index; every other `rag_data/*.md` file is chunked and indexed at startup (for example `software_recommendations.md`, `windows_macos_alternatives.md`).
2. Use a single **H1** for the document title, and split the body with **H2** headings — each H2 becomes one retrievable chunk that includes the H1 title for context.
3. Keep chunks small and self-contained (a few paragraphs or one fenced code example each); don't rely on H3+ as boundaries. The embedding model (`bge-small-en-v1.5`) has a hard **512-token input cap**, so any single H2 chunk must stay under that — long lists or tables should be split across multiple H2s, one topic per heading. `tests/test_retrieval.py::test_no_rag_chunk_exceeds_embedding_cap` enforces this.
4. Restart Meera. `retrieval/rag_chunker.py` reads the directory, the index re-embeds, and the new chunks are now eligible to be inlined into the system prompt as `<KNOWLEDGE>` blocks when the user asks a related question.

## Adding a fast-path regex (optional)

Use this when a tool’s trigger phrases are **narrow and structural** (fixed verbs, numbers, or tokens). The fast-path runs **before** retrieval and the LLM, so those utterances cost no embed call and no tool-selection tokens. It still **runs the tool** and uses the LLM to **summarize** the result; only retrieval and tool-choice for that turn are skipped.

**When a fast-path is a good fit**

- **High-frequency, repetitive phrasing** — The same intent shows up often (volume to N%, screenshot, time/date), so skipping embedding and tool retrieval is worthwhile.
- **Parameters from the regex alone** — You can build `params` deterministically (percent digits, on/off, a bounded process name). Fuzzy timing or free-text (“remind me in a bit”) belongs in **exemplars + retrieval**, not regex.
- **Low false-positive risk** — Patterns should not fire on normal chat; prefer specific or line-anchored regexes over loose substrings.
- **Stable tool API** — Tool name and parameter shape are unlikely to change often; fast-path builders must be updated when they do.

**When to skip the fast-path**

- Rare actions, wide natural-language variation, or error-prone extraction.
- Anything safety- or ambiguity-sensitive where you want retrieval + the LLM’s tool choice every time.

Over-broad regexes will misfire on normal chat — when unsure, skip the fast-path and rely on **exemplars** only.

All logic lives in **`agent.py`** under `# ---- Heuristic fast-path patterns`:

1. **Add a builder function** — takes `m: re.Match[str]`, returns `{"tool": "your_tool_name", "params": {...}}`. Prefer **named capture groups** in the regex (`(?P<name>...)`) and read them with `m.group("name")`. Clamp or validate values; let invalid matches raise so the agent falls back to retrieval + LLM.
2. **Append** `(r"…pattern…", _fp_your_builder)` to **`_HEURISTIC_PATTERNS`**. List order is the match order: **more specific patterns first**, broader patterns later (the first match wins; patterns use `re.IGNORECASE` and `search()` on the whole message).
3. **Restart** Meera.
4. **Test** — add cases under `TestFastpath` in `tests/test_agent.py`, or exercise the phrase manually with `MEERA_DEBUG_TOOL_CALLS=1` and confirm `stage=fastpath` in the debug line.

See **`phases/Phase4_plan.md` §5** for the full design note and pitfalls.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```
