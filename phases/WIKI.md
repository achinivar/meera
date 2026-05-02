# Meera Architecture & Development Wiki

## Table of Contents
- [Model Loading & Serving](#model-loading--serving)
- [Request Flow & Agent Loop](#request-flow--agent-loop)
- [Tool System](#tool-system)
- [RAG Data](#rag-data)
- [Fast-Path System](#fast-path-system)
- [Configuration Reference](#configuration-reference)

---

## Model Loading & Serving

Meera uses two separate local `llama.cpp` servers, managed by the launcher script (`scripts/meera-launcher.sh`):

| Server | Port | Model | Purpose |
|--------|------|-------|---------|
| Chat | 8080 (default) | Chat model (e.g., qwen-based GGUF) | Conversational inference, tool calling |
| Embedding | 8081 (default) | `bge-small-en-v1.5` (q8_0) | Vector embeddings for retrieval |

### Startup Process (`meera-launcher.sh`)

1. **Backend detection** — probes for `/dev/dri/renderD*` to decide Vulkan vs CPU. Choice is persisted in `~/.config/meera/backend-choice.env`.
2. **Bundle download** — fetches the pinned `llama.cpp` binary bundle (Vulkan or CPU) to `~/.cache/meera/llama-cpp/`, verifies SHA256.
3. **Model download** — ensures chat and embedding GGUF models exist in `~/.cache/meera/models/`, with checksum verification.
4. **Server launch** — starts two `llama-server` processes:
   - Chat server: `llama-server -m <chat_model> --port 8080 -ngl 99` (Vulkan) or `-ngl 0` (CPU)
   - Embed server: `llama-server -m <embed_model> --port 8081 --embeddings -c 512`
5. **Health check** — polls `/v1/models` on each server until reachable (up to 15s wait).
6. **State persistence** — writes ports and URLs to runtime state file, exports `MEERA_BACKEND=llamacpp`, `MEERA_LLAMACPP_URL`, `MEERA_EMBED_URL`.

### Runtime Fallback

If Vulkan fails at startup (VRAM pressure, driver issues), the launcher automatically falls back to CPU mode and shows a warning popup. The fallback is transient (does not overwrite persisted preference) unless Vulkan is genuinely unavailable.

### Inference Dispatch

`llamacpp_backend.py` calls the llama.cpp chat server at port 8080 via the OpenAI-compatible `/v1/chat/completions` endpoint. Streaming yields `{"kind": "content", "text": "..."}` events progressively, then `{"kind": "tool_calls", "tool_calls": [...]}` when the model requests tool execution.

---

## Request Flow & Agent Loop

Every user message passes through `agent.run_agent_turn()`, which follows a three-stage decision pipeline:

### Stage 1: Heuristic Fast-Path
Regex patterns in `agent._HEURISTIC_PATTERNS` are tested against the user message. If a pattern matches, the tool runs directly — no embedding call, no LLM tool selection. The LLM is only invoked afterward to summarize the tool result.

### Stage 2: Retrieval
If fast-path doesn't match, the user message is embedded and queried against the in-memory index (built at startup from tool exemplars + RAG chunks). The returns are split:
- **Top tool hits** (deduped by tool name, threshold ≥ 0.75) → candidate tools for the LLM
- **Top RAG hits** (threshold ≥ 0.6) → knowledge blocks inlined into the system prompt

A **margin check** decides whether to run tool mode or chat mode: if the top tool score exceeds the top RAG score by at least `MEERA_RETRIEVAL_TOOL_MARGIN` (default 0.01), the turn goes to `llm_tools` mode. Otherwise it falls through to `llm_chat`.

### Stage 3: LLM Call
- **`llm_tools`** — single streaming call with narrowed `tools=[...]` payload and `tool_choice="auto"`. If the model emits `tool_calls`, they execute, `role:tool` responses are appended, and a follow-up call lets the model summarize. This loop repeats up to `MEERA_AGENT_MAX_PASSES` (default 3).
- **`llm_chat`** — plain chat with RAG knowledge blocks in the system prompt (no tools).

### Cross-Turn Memory
Tool results are compacted into `[Tool memory]` assistant messages so they persist across turns and survive session reload.

### Architecture Diagram

```
User message
     │
     ▼
┌─────────────────────────────┐
│  FAST-PATH REGEX MATCH      │  ← _HEURISTIC_PATTERNS (ordered, most-specific first)
│                             │     re.IGNORECASE, first match wins
└─────────-───────────────────┘
    MATCH              NO MATCH
      ▼                   ▼
┌─────────-─┐      ┌──────────────────────────┐
│ Builder   │      │  RETRIVAL PIPELINE       │
│ function  │      │                          │
│ returns   │      │  ┌────────────────────┐  │
│ {tool,    │      │  │ Embed user message │  │
│  params}  │      │  └───────┬───-────────┘  │
└─────┬─────┘      │          │               │
      │            │  ┌───────▼───────────┐   │
      │            │  │ Cosine query vs   │   │
      │            │  │ in-memory index   │   │
      │            │  │ (tool exemplars   │   │
      │            │  │  + RAG chunks)    │   │
      │            │  └───────┬───────────┘   │
      │            │          │               │
      │            │  ┌───────▼───────────┐   │
      │            │  │ Split + threshold │   │
      │            │  │ tools ≥ 0.75      │   │
      │            │  │ rag   ≥ 0.6       │   │
      │            │  └───────┬───────────┘   │
      │            │          │               │
      │            │  ┌───────▼───────────┐   │
      │            │  │ Margin check:     │   │
      │            │  │ top_tool >        │   │
      │            │  │ top_rag + margin? │   │
      │            │  └──┬──────────┬─────┘   │
      │            │  YES│          │NO       │
      │            │     ▼          ▼         │
      │            │  llm_tools  llm_chat     │
      │            │  (narrow    (RAG blocks  │
      │            │   tools)     in prompt)  │
      │            └──────────────────────────┘
      ▼
┌─────────────────────────────┐
│  RUN TOOL DIRECTLY          │
│  run_tool(name, params)     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  LLM SUMMARIZES RESULT      │  ← single streaming call,
│  (always happens)           │    tool result injected as
│                             │    role:tool or user message
└─────────────────────────────┘
```

---

## Tool System

### Organization

```
tools/
├── schema.py        # ToolSpec, ToolParam, ToolResult dataclasses
├── registry.py      # Aggregates all ToolSpecs into TOOLS list
├── runner.py        # Parameter validation + dispatch (run_tool)
├── platform.py      # Distro detection
├── _cmd.py          # Shell command execution helper
├── files.py         # Filesystem tools (list, search, read, etc.)
├── gsettings.py     # GNOME settings tools (volume, brightness, Wi-Fi, etc.)
├── packages.py      # Package management tools
├── processes.py     # Process listing/checking
├── scheduler.py     # Reminder/scheduling tools
├── screenshot.py    # Screenshot capture
├── system.py        # System info tools
└── weather.py       # Weather lookup
```

### Data Flow

1. **`ToolSpec`** (`schema.py`) — each tool is defined as a `ToolSpec` with `name`, `description`, `parameters` (list of `ToolParam`), `handler` (callable), and `exemplars` (5-10 natural-language phrases).
2. **`registry.py`** — imports all tool modules, merges their `TOOLS` lists into a single catalog. Enforces unique tool names.
3. **`runner.run_tool(name, params)`** — looks up the spec, validates/coerces parameters against the schema, injects `distro`, executes the handler, catches all exceptions.
4. **Exemplars → Index** — at startup, every exemplar string from every tool becomes an `IndexEntry(kind="tool_exemplar")` in the retrieval index.

---

### Adding a New Tool

#### Step 1: Create or edit a module under `tools/`

Pick an existing module (e.g., `tools/gsettings.py` for GNOME settings) or create a new one (e.g., `tools/newthing.py`).

#### Step 2: Define the handler function

```python
def _my_handler(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]  # always present, injected by runner
    value = params.get("some_param")
    # ... do work ...
    return tool_result_ok("It worked", data={"result": value})
    # or on failure:
    return tool_result_err("Something failed", "ERROR_CODE")
```

- Signature: `handler(args: dict) -> ToolResult`
- The runner injects `distro` automatically; always consume it to avoid "unexpected parameter" errors.

#### Step 3: Define the ToolSpec

```python
MY_TOOL = ToolSpec(
    name="my_tool_name",
    description="What this tool does, for the LLM's benefit.",
    parameters=[
        ToolParam(name="some_param", param_type="string", required=True, description="Description"),
    ],
    handler=_my_handler,
    read_only=True,           # set False if the tool modifies system state
    requires_elevation=False, # set True if root is needed
    exemplars=[
        "do the thing",
        "perform that action please",
        # ... 5-10 natural-language phrases users would type
    ],
)
```

#### Step 4: Export from the module

```python
TOOLS = [MY_TOOL]
```

#### Step 5: Register in `tools/registry.py`

```python
import tools.newthing as newthing_mod
# ...
merged: list[ToolSpec] = [
    # ...
    *newthing_mod.TOOLS,
]
```

#### Step 6: Restart Meera

The retrieval index rebuilds at startup, embedding all new exemplars. The test `tests/test_tools.py::test_every_tool_has_exemplars` enforces a minimum of 5 exemplars per tool.

---

## RAG Data

### Organization

```
rag_data/
├── README.md                    # excluded from indexing
├── distro_install_commands.md
├── downloads_basics.md
├── filesystem_basics.md
├── linux_help_and_discovery.md
├── network_diagnostics_basics.md
├── process_management_basics.md
├── software_recommendations.md
├── text_pipeline_basics.md
├── text_tools_grep_sed_awk_find.md
├── vim_basics.md
└── windows_macos_alternatives.md
```

### Chunking Pipeline (`retrieval/rag_chunker.py`)

1. Walks `rag_data/*.md` (excludes `README.md`)
2. Extracts H1 as document title
3. Splits at H2 boundaries — each H2 section becomes one `RagChunk`
4. Each chunk's `index_text` = `"{H1 title} — {H2 section}\n{body}"`
5. All chunks are batch-embedded at startup via `embed_batch()`

### Embedding Details
- Model: `bge-small-en-v1.5` (384-dim vectors)
- Context window: **512 tokens hard cap** per chunk (enforced by test)
- Vectors are L2-normalized; cosine similarity = dot product
- Index is pure Python (no numpy), sized for hundreds to low-thousands of entries

---

### Adding RAG Data

#### Step 1: Create a Markdown file in `rag_data/`

Use lowercase filename with `.md` extension (e.g., `new_topic.md`). `README.md` in that directory is excluded from indexing.

#### Step 2: Follow the heading structure

```markdown
# Document Title

## Section One
Content for the first retrievable chunk...

## Section Two
Content for the second chunk...
```

- **Single H1** for the document title
- **H2 headings** define chunk boundaries — each H2 becomes one retrievable chunk
- H3+ headings are kept inside their parent H2 chunk (not used as boundaries)

#### Step 3: Keep chunks under 512 tokens

The embedding model has a hard 512-token input cap. If a section is long, split it across multiple H2 headings. The test `tests/test_retrieval.py::test_no_rag_chunk_exceeds_embedding_cap` enforces this.

#### Step 4: Restart Meera

`retrieval/rag_chunker.py` reads the directory at startup, chunks are re-embedded, and new content is immediately queryable.

---

## Fast-Path System

### Key Properties
- **Zero-cost skip** — fast-path avoids both the embedding call and the LLM tool-selection step. The LLM still summarizes the result.
- **Order matters** — `_HEURISTIC_PATTERNS` is evaluated top-to-bottom; first match wins. More specific patterns must come before broader ones.
- **Error tolerance** — if a builder function raises `ValueError` or `KeyError`, the match is skipped and the next pattern is tried, falling back to retrieval + LLM.
- **All patterns use** `re.IGNORECASE` and `re.search()` (not full-string match).

---

### Adding a Fast-Path Pattern

Use fast-path when a tool's trigger phrases are **narrow and structural** (fixed verbs, numbers, tokens). Fast-path runs **before** retrieval and the LLM, skipping the embedding call and tool-selection tokens. It still runs the tool and uses the LLM to summarize.

#### When fast-path is a good fit
- High-frequency, repetitive phrasing (volume to N%, screenshot, time/date)
- Parameters extractable from the regex alone (percent digits, on/off toggles)
- Low false-positive risk (specific or line-anchored regexes)
- Stable tool API

#### When to skip fast-path
- Rare actions, wide natural-language variation
- Fuzzy or ambiguous phrasing
- Anything where retrieval + LLM tool choice is safer

Over-broad regexes will misfire on normal chat — when unsure, skip the fast-path and rely on **exemplars** only.

All logic lives in `agent.py` under `# ---- Heuristic fast-path patterns`.

#### Step 1: Add a builder function

```python
def _fp_my_builder(m: re.Match[str]) -> dict[str, Any]:
    value = m.group("value")  # use named capture groups
    return {"tool": "my_tool_name", "params": {"some_param": value}}
```

- Takes `re.Match[str]`, returns `{"tool": "name", "params": {...}}`
- Use named capture groups (`(?P<name>...)`) in the regex
- Clamp or validate values; let invalid matches raise so the agent falls back to retrieval + LLM

#### Step 2: Append to `_HEURISTIC_PATTERNS`

```python
_HEURISTIC_PATTERNS: list[tuple[str, Any]] = [
    # ... existing patterns ...
    (r"\bmy\s+pattern\s+(?P<value>\w+)\b", _fp_my_builder),
]
```

- **More specific patterns first** — list order is match order, first match wins
- All patterns use `re.IGNORECASE`
- Patterns use `search()` on the whole message (not full-string match)

#### Step 3: Test

Add cases under `TestFastpath` in `tests/test_agent.py`, or exercise manually with `MEERA_DEBUG_TOOL_CALLS=1` and confirm `stage=fastpath` in the debug output.

#### Step 4: Restart Meera

---

## Configuration Reference

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `MEERA_AGENT_TOOLS` | `1` | Enable tool-capable agent loop |
| `MEERA_AGENT_MAX_PASSES` | `3` | Max assistant↔tool round-trips per message (1-8) |
| `MEERA_DEBUG_TOOL_CALLS` | `0` | Show tool debug lines in stderr |
| `MEERA_DEBUG_RETRIEVAL` | `0` | Show retrieval debug output |
| `MEERA_RETRIEVAL_K_TOOLS` | `4` | Top-k tool candidates from retrieval |
| `MEERA_RETRIEVAL_K_RAG` | `2` | Top-k RAG chunks from retrieval |
| `MEERA_RETRIEVAL_TOOL_THRESHOLD` | `0.75` | Minimum cosine score for tool hits |
| `MEERA_RETRIEVAL_RAG_THRESHOLD` | `0.6` | Minimum cosine score for RAG hits |
| `MEERA_RETRIEVAL_TOOL_MARGIN` | `0.01` | Score advantage tools need over RAG to trigger tool mode |
| `MEERA_LLAMACPP_URL` | `http://127.0.0.1:8080` | Chat server URL |
| `MEERA_EMBED_URL` | `http://127.0.0.1:8081` | Embedding server URL |