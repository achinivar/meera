# Meera — Local GNOME AI Assistant (Prototype)

Meera is a local-only AI assistant prototype designed for GNOME desktops.  
It streams chat from a local model using **[llama.cpp](https://github.com/ggml-org/llama.cpp)** `llama-server` (default) or **[Ollama](https://ollama.com/)**, and presents a native GTK4 chat UI.

> ⚠️ **Prototype.** The chat UI runs **allowlisted laptop tools** when agent mode is on (default). Each user message goes through a **retrieval-first agent**: a heuristic fast-path catches obvious intents, otherwise an embedding index narrows down 2–4 candidate tools and pulls in any relevant `rag_data/*.md` snippets, then a **single** LLM call decides whether to call a tool (via llama.cpp native tool calling) or reply directly. Set **`MEERA_AGENT_TOOLS=0`** to disable tools and use plain chat only. See [`tools/README.md`](./tools/README.md), [`phases/Phase4_plan.md`](./phases/Phase4_plan.md), and the **Adding a tool**, **Adding a fast-path regex**, and **Adding RAG data** sections below.

---

## Agent loop

Two `llama-server` instances run side-by-side: the chat model on **port 8080** and a small `bge-small-en-v1.5` embedding model on **port 8081**. `run_meera.sh` starts both and exits cleanly on Ctrl+C.

| Variable | Purpose |
|----------|---------|
| `MEERA_AGENT_TOOLS` | **`1` (default)** — give the chat model a retrieval-narrowed tools list and run any tool calls it emits. Set **`0`** for plain chat only. |
| `MEERA_AGENT_MAX_PASSES` | Max assistant↔tool round-trips per user message. Default **`3`**, clamped **1–8**. |
| `MEERA_DEBUG_TOOL_CALLS` | Set to **`1`** to print retrieval / tool-call debug lines into the chat view. |
| `MEERA_DEBUG_RETRIEVAL` | Set to **`1`** to print embedding / retrieval debug to stderr. |
| `MEERA_RETRIEVAL_K_TOOLS` / `MEERA_RETRIEVAL_K_RAG` | Top-k caps for tools / RAG chunks per turn. Defaults **`4`** / **`3`**. |
| `MEERA_RETRIEVAL_TOOL_THRESHOLD` / `MEERA_RETRIEVAL_RAG_THRESHOLD` | Cosine-similarity floors. Defaults **`0.35`** / **`0.35`**. |
| `MEERA_EMBED_URL` | Embedding server URL (default `http://127.0.0.1:8081`). |
| `MEERA_EMBED_FAKE` | Set **`1`** in tests to use a deterministic hash embedder (no server needed). |
| `MEERA_DISABLE_EMBED` | Set **`1`** to skip starting the embedding server in `run_meera.sh`. The agent then falls back to chat-only (no tools, no RAG). |

Implementation: **`agent.py`** (`decide_turn` + `run_agent_turn` event generator), **`retrieval/`** (in-memory cosine index over tool exemplars + Markdown chunks), **`embeddings.py`** (HTTP client for the embedding server), **`ui/window.py`** (consumes the agent event stream and drives GTK4). Tool calls go over llama-server's OpenAI-compatible `tools=[...]` + `tool_choice=auto` API; if the embedding server is unreachable the agent degrades to plain chat.

---

## Adding a tool

1. Pick or create a module under `tools/` (e.g. `tools/files.py`).
2. Define a handler with the signature `handler(args: dict) -> ToolResult` and add a `ToolSpec(name=..., description=..., parameters=[...], handler=...)` to the module's exported list.
3. **Add 5–10 `exemplars`** — natural-language phrases real users would type. These power retrieval; the test in `tests/test_tools.py::test_every_tool_has_exemplars` enforces a minimum.
4. Register the spec by exporting it from your module and listing it in `tools/registry.py::TOOLS`.
5. Restart Meera. The retrieval index is rebuilt at startup, so the new tool is immediately reachable.

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

## Adding RAG data

1. Drop a Markdown file into `rag_data/` (lowercase filename, ending in `.md`). `README.md` in that folder is excluded from the index; every other `rag_data/*.md` file is chunked and indexed at startup (for example `software_recommendations.md`, `windows_macos_alternatives.md`).
2. Use a single **H1** for the document title, and split the body with **H2** headings — each H2 becomes one retrievable chunk that includes the H1 title for context.
3. Keep chunks small and self-contained (a few paragraphs or one fenced code example each); don't rely on H3+ as boundaries. The embedding model (`bge-small-en-v1.5`) has a hard **512-token input cap**, so any single H2 chunk must stay under that — long lists or tables should be split across multiple H2s, one topic per heading. `tests/test_retrieval.py::test_no_rag_chunk_exceeds_embedding_cap` enforces this.
4. Restart Meera. `retrieval/rag_chunker.py` reads the directory, the index re-embeds, and the new chunks are now eligible to be inlined into the system prompt as `<KNOWLEDGE>` blocks when the user asks a related question.

---

## Tool layer (Phase 2)

Allowlisted helpers (Wi‑Fi readouts, volume, listing files under `$HOME`, package/flatpak lists, etc.) live under **`tools/`**. They use fixed command lines and validation, not a raw shell.

Run unit tests:

```bash
python3 -m unittest discover -s tests -v
```

---

## Features

- 🖥️ Native GTK4 chat window (GNOME-friendly)
- 💬 Streaming responses (token-by-token, like ChatGPT)
- 💾 Chat history storage (last 10 sessions automatically saved in `./history/`)
- 📜 View and load previous chat sessions from menu
- 🆕 New Chat option to start fresh conversations
- 🎛️ Menu bar in titlebar with About dialog
- 🌓 Automatic theme detection (adapts to light/dark system theme)
- 🐶 Custom background image for the chat area
- ↔️ Right-aligned user messages, left-aligned for Meera
- ⏹ "Stop" button while Meera is typing, ↑ send button when idle
- ⇧⏎ Multi-line input with auto-grow from 1–6 lines

---

## Inference backends

| Variable | Purpose |
|----------|---------|
| `MEERA_BACKEND` | **`llamacpp` by default** (in `inference.py` and when using `run_meera.sh`). Set `MEERA_BACKEND=ollama` for Ollama. |
| `MEERA_LLAMACPP_URL` | Base URL for llama-server (default `http://127.0.0.1:8080`) |
| `MEERA_LLAMACPP_MODEL` | `model` field in the API body (default `local`; many single-model servers accept any name) |
| `MEERA_LLAMACPP_GGUF` | Optional path to a `.gguf` file. If unset, `run_meera.sh` uses a cached file under `MEERA_GGUF_CACHE_DIR` (see below). |
| `MEERA_GGUF_CACHE_DIR` | Where the default GGUF is stored (default: `./.cache/meera/models` under the repo; ignored by git). |
| `MEERA_LLAMA_CACHE` | Cache directory for the llama.cpp tarball + extract (default: `./.cache/meera/llama-cpp`). |
| `MEERA_LLAMA_CPP_TAG` | Override release tag (default `b8672`). If you change this, update the SHA256 constants in `run_meera.sh` to match. |
| `MEERA_LLAMACPP_SERVER_EXTRA` | Optional: extra arguments passed to `llama-server` (e.g. `-ngl 99`). Unquoted so multiple words work. |

- **`run_meera.sh` + llama.cpp (default):** On first run, the script downloads the **pinned** [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) **CPU** tarball (with **SHA256 check**), extracts it under `.cache/meera/llama-cpp/`, and runs `llama-server` with `LD_LIBRARY_PATH` set to the bundle. **Debian/Ubuntu** (`apt`) uses the upstream **Ubuntu** `*-ubuntu-{x64,arm64}.tar.gz` assets; **Fedora** (`dnf`, including Silverblue) uses the upstream **openEuler** `*-310p-openEuler-{x86,aarch64}.tar.gz` assets. It also downloads the default **[unsloth/Qwen3.5-2B-GGUF](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF)** `Qwen3.5-2B-Q4_K_M.gguf` (~1.3 GB) if needed. Qwen-style **thinking is off**, same as Ollama’s `think: false`: `llamacpp_backend.py` sends **`chat_template_kwargs.enable_thinking: false`** on each chat request.
- **Ollama:** Set `MEERA_BACKEND=ollama`. `run_meera.sh` installs/starts Ollama and pulls `qwen3.5:2b-q4_K_M`. `backend.py` uses `think: false` and the same model family.

**Quick start:**

```bash
chmod +x run_meera.sh
./run_meera.sh
```

**Ollama instead:**

```bash
MEERA_BACKEND=ollama ./run_meera.sh
```

**Custom GGUF** (skip the default download by pointing at your file):

```bash
MEERA_LLAMACPP_GGUF=/path/to/other.gguf ./run_meera.sh
```

---

## Requirements

- A Linux desktop with **GTK4** (GNOME recommended)
- **Python 3.10+**
- **Network** on first `run_meera.sh` with llama.cpp (GitHub: llama.cpp bundle + Hugging Face: default GGUF); later runs use `.cache/meera/`
- **Ollama** only if you use `MEERA_BACKEND=ollama`

The provided script supports:

- Fedora / Silverblue (via `dnf`)
- Ubuntu / Debian (via `apt`)

Other distros may need manual package installation.

---

## Install dependencies and run meera

```bash
chmod +x run_meera.sh
./run_meera.sh
```

---

## Project Structure

Expected repo layout:

```text
meera/
├── meera.py               # Main application entry
├── backend.py             # Ollama chat API client (event-aware streaming)
├── llamacpp_backend.py    # llama-server OpenAI-compatible streaming client + tool calls
├── inference.py           # Dispatches to backend by MEERA_BACKEND, exposes supports_tools()
├── agent.py               # Retrieval-first agent: decide_turn + run_agent_turn event stream
├── embeddings.py          # HTTP client for the embedding llama-server (port 8081)
├── retrieval/             # In-memory cosine index (tool exemplars + rag_data chunks)
├── rag_data/              # Markdown knowledge base; one H1 per file, split at H2 headings
├── history.py             # Chat history storage and management
├── tools/                 # Typed tools, runner, registry (see tools/README.md)
├── tests/                 # test_agent.py, test_retrieval.py, test_tools.py
├── phases/                # Phase2_plan.md, Phase4_plan.md, progress_summary.md
├── ui/
│   └── window.py          # GTK4 UI definition; consumes the agent event stream
├── assets/
│   └── meera_bg.png       # Background image for chat area
└── run_meera.sh           # Setup + run script (starts both llama-server instances)
```

### Dependencies (installed by `run_meera.sh` for Ubuntu and Fedora)

Before running Meera, you must install (these are installed by the script where applicable):

- **Python 3.10+**
- **GTK4**
- **PyGObject (Python bindings for GTK)**
- **GObject Introspection**
- **Cairo + Cairo GObject bindings**
- **requests** (Python HTTP client)
- **curl** (for downloading the llama.cpp bundle and default GGUF on first llama.cpp run)
- **Ollama** when using `MEERA_BACKEND=ollama` (script skips Ollama when using llama.cpp)

## Chat History

Meera automatically saves your conversation history when you close the window. The last 10 sessions are stored in a `history/` directory relative to where you run the application. You can:

- **View saved sessions**: Click the menu button (☰) → "Chat History"
- **Load a previous session**: Click "Load" on any session in the history dialog
- **Start a new chat**: Click the menu button (☰) → "New Chat"

Sessions older than the last 10 are automatically deleted when new ones are saved.
