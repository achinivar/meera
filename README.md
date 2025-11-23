# Meera — Local GNOME AI Assistant (Prototype)

Meera is a local-only AI assistant prototype designed for GNOME desktops.  
It runs a small language model via [Ollama](https://ollama.com/) and presents a native GTK4 chat UI.

> ⚠️ This is an early prototype: it’s a simple chat UI + local LLM, no system actions yet.

---

## Features

- 🖥️ Native GTK4 chat window (GNOME-friendly)
- 💬 Streaming responses (token-by-token, like ChatGPT)
- 🧠 Conversation context maintained across messages (like `ollama run`)
- 💾 Chat history storage (last 10 sessions automatically saved)
- 📜 View and load previous chat sessions from menu
- 🆕 New Chat option to start fresh conversations
- 🎛️ Menu bar in titlebar with About dialog
- 🌓 Works in both light/dark themes (text forced to white)
- 🐶 Custom background image for the chat area
- ↔️ Right-aligned bubbles for user messages, left-aligned for Meera
- ⏹ "Stop" button while Meera is typing, ↑ send button when idle
- ⇧⏎ Multi-line input with auto-grow from 1–6 lines

---

## Requirements

- A Linux desktop with **GTK4** (GNOME recommended)
- **Python 3.10+**
- **Ollama** (for local LLM inference)

The provided script supports:

- Fedora / Silverblue (via `dnf`)
- Ubuntu / Debian (via `apt`)

Other distros may need manual package installation.

---

## Install dependencies and run meera

chmod +x run_meera.sh
./run_meera.sh

---

## Project Structure

Expected repo layout:

```text
meera/
├── meera.py               # Main application entry
├── backend.py             # LLM streaming client (Ollama chat API)
├── history.py             # Chat history storage and management
├── ui/
│   └── window.py          # GTK4 UI definition with conversation history
├── assets/
│   └── meera_bg.png       # Background image for chat area
└── run_meera.sh           # Setup + run script

## Dependencies (installed by the run_meera.sh script) 

Before running Meera, you must install (these are installed by the run_meera.sh script for ubuntu and fedora):

- **Python 3.10+**
- **GTK4**
- **PyGObject (Python bindings for GTK)**
- **GObject Introspection**
- **Cairo + Cairo GObject bindings**
- **Ollama** (for local LLM inference)

## Chat History

Meera automatically saves your conversation history when you close the window. The last 10 sessions are stored in `~/.local/share/meera/history/` (or `$XDG_DATA_HOME/meera/history/`). You can:

- **View saved sessions**: Click the menu button (☰) → "Chat History"
- **Load a previous session**: Click "Load" on any session in the history dialog
- **Start a new chat**: Click the menu button (☰) → "New Chat"

Sessions older than the last 10 are automatically deleted when new ones are saved.


