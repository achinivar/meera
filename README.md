# Meera — Local GNOME AI Assistant (Prototype)

Meera is a local-only AI assistant prototype designed for GNOME desktops.  
It streams chat from a local model using **[llama.cpp](https://github.com/ggml-org/llama.cpp)** `llama-server` (default) or **[Ollama](https://ollama.com/)**, and presents a native GTK4 chat UI.

> ⚠️ This is an early prototype: it's a simple chat UI + local LLM, no system actions yet.

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

- **`run_meera.sh` + llama.cpp (default):** On first run, the script downloads the **pinned** [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) **CPU** tarball (with **SHA256 check**), extracts it under `.cache/meera/llama-cpp/`, and runs `llama-server` with `LD_LIBRARY_PATH` set to the bundle. **Debian/Ubuntu** (`apt`) uses the upstream **Ubuntu** `*-ubuntu-{x64,arm64}.tar.gz` assets; **Fedora** (`dnf`, including Silverblue) uses the upstream **openEuler** `*-310p-openEuler-{x86,aarch64}.tar.gz` assets. It also downloads the default **[unsloth/Qwen3.5-2B-GGUF](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF)** `Qwen3.5-2B-Q4_K_M.gguf` (~1.3 GB) if needed. Qwen-style **thinking is off**, same as Ollama’s `think: false`: `run_meera.sh` starts `llama-server` with **`--reasoning-budget 0`**, and **`llamacpp_backend.py`** sends **`chat_template_kwargs.enable_thinking: false`** on each chat request.
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
├── backend.py             # Ollama chat API client
├── llamacpp_backend.py    # llama-server OpenAI-compatible streaming client
├── inference.py           # Dispatches to backend by MEERA_BACKEND
├── history.py             # Chat history storage and management
├── ui/
│   └── window.py          # GTK4 UI definition with conversation history
├── assets/
│   └── meera_bg.png       # Background image for chat area
└── run_meera.sh           # Setup + run script
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
