# Meera — AI Assistant for Linux GNOME Desktops

Meera is a local-first AI assistant for Linux GNOME desktops. It lets you control your system, manage files, and get Linux help — all through a native chat UI, with a lightweight model running entirely offline on your machine.

<div align="center">

![Demo](./assets/office_n_dark.gif)

</div>

## Overview

Meera sits in your GNOME desktop and lets you control your system, manage files, and get Linux help — all through natural conversation, with everything running locally on your machine.

- **Native GTK4 app**, built for GNOME with adaptive dark/light theme support
- **Control your desktop** — adjust volume and brightness, GNOME settings and desktop themes, manage processes, search for files, schedule reminders and calendar events and more with several built-in tools
- **Linux help on demand** — a local knowledge base covers filesystem basics, text processing tools, process management, network diagnostics, Vim, Windows/Mac software alternatives, and more. Meera retrieves relevant documentation to answer your questions accurately
- **Intelligent agent loop** — understands your intent, retrieves the right tools and knowledge, then acts. No cloud API needed
- **Runs offline** — a lightweight 2B local model handles reasoning and tool dispatch. Fast enough for CPU-only laptops
- **Privacy-first** — your chats, file system, and tool calls never leave your machine

## Requirements

- Linux desktop (GNOME recommended)
- Python 3.10+
- Network access on first run (to download pinned `llama.cpp` bundle and default models)

The installer currently supports dependency installation on:

- Ubuntu / Debian (`apt`)
- Fedora (`dnf`, excluding immutable ostree auto-installs)

## Installation

Run the following command in your terminal to download and install Meera to your GNOME Linux Desktop:

```bash
curl -fsSL https://github.com/achinivar/meera/releases/latest/download/install.sh | sh
```

Then start Meera from the GNOME **Activities** overview (search for **Meera**) or from a terminal:

```bash
meera
```

### CLI helpers

```bash
meera doctor
meera logs
meera restart-model
meera unload-model
meera uninstall
```

## Getting Started

The first launch runs a short GUI setup (autostart and keyboard shortcut options, then downloads the default chat model). Later launches go straight to the App.

- Meera runs local `llama.cpp` servers for chat and embeddings. Default setup downloads pinned artifacts and verifies checksums where configured.
- Chat history is saved automatically and can be loaded from the App menu.

## Development

- For details on the architecture, tool system, RAG pipeline and fast path, see the [wiki](https://github.com/achinivar/meera/wiki)
- For reporting bugs or requesting new features, please use the appropriate template in [issues](https://github.com/achinivar/meera/issues)

### Key directories

- `ui/` — GTK UI
- `tools/` — allowlisted desktop tools
- `retrieval/` and `rag_data/` — retrieval + local knowledge chunks
- `scripts/` — installer/launcher helper scripts

### Adding capabilities

- **Adding a tool** — Create a module under `tools/`, define a handler with a `ToolSpec`, add exemplars for intent matching, and register it in `tools/registry.py`. See the [wiki](https://github.com/achinivar/meera/wiki#tool-system) for a full walkthrough.
- **Adding RAG data** — Drop a Markdown file into `rag_data/` using H1/H2 headings to define chunks. Meera indexes it at startup so it's available for retrieval. See the [wiki](https://github.com/achinivar/meera/wiki#rag-data) for guidelines and constraints.
- **Adding a fast-path regex** — Define heuristic patterns in `agent.py` for high-frequency, structurally predictable commands that skip retrieval and go straight to tool execution. See the [wiki](https://github.com/achinivar/meera/wiki#fast-path-system) for design notes and pitfalls.

### Debug options

- `MEERA_AGENT_TOOLS` — `1` (default) enables tool-capable agent loop; `0` for plain chat
- `MEERA_AGENT_MAX_PASSES` — max assistant↔tool passes per message (default `3`)
- `MEERA_DEBUG_TOOL_CALLS` — set `1` to show tool debug lines in UI
- `MEERA_DEBUG_RETRIEVAL` — set `1` to show retrieval debug output

