# Software Recommendations (Linux, GNOME-friendly)

## What it is

A **broad, non-exhaustive** sampling of common desktop applications for Linux, biased toward **GNOME** and widely available packages (Flatpak, distro repos). **KDE-specific apps are omitted** on purpose. Use it as a starting point, not a complete catalog.

## When to use it

Use this when choosing defaults for a new GNOME install, when suggesting tools for MS Office–style compatibility, or when mapping **Windows/macOS habits** to **Linux equivalents** (native port vs practical alternative).

---

## Video playback

- **VLC** — Plays almost any format; strong subtitles, network streams, and troubleshooting when the default player struggles.
- **GNOME Videos (Totem)** — Simple, integrated player for local files; good enough for day-to-day viewing on GNOME.
- **Celluloid** — Minimal **mpv**-based front-end; good if you want a lightweight player with strong format support.

## Web browsers

- **Firefox** — Strong privacy defaults, wide extension support, and a common first-party choice on many Linux distributions.
- **Google Chrome** (or **Chromium**) — Best when you need tight Google account integration, certain web apps, or Chrome-only features; Chromium is the open-source base without Google branding.
- **Brave** — Chromium-based with built-in ad/tracker blocking; useful if you want less configuration than Firefox for aggressive blocking.
- **Microsoft Edge** — Official Linux build exists; relevant for Microsoft account / enterprise compatibility and some Chromium-only behaviors.

## Coding: AI-first editors and agents

- **Claude Code** — Anthropic’s AI-assisted coding flow for working inside your repo with an agent-style assistant (strength: deep model reasoning on larger changes when you already use Claude).
- **Cursor** — AI-first editor/IDE built on a VS Code–like experience (strength: inline AI, chat, and refactors without leaving the editor).
- **OpenCode** — Open-source **terminal** AI coding agent with tools for reading/editing the codebase and integrating with various model providers (strength: agentic workflows in the shell, pairs well with local models).

## Coding: editors and IDEs

- **Visual Studio Code** — General-purpose editor with the largest extension ecosystem (strength: language support, debugging, and team workflows that map cleanly from Windows/macOS).
- **VSCodium** — Community builds of VS Code **without** Microsoft branding/telemetry; same extension universe in practice for most users.
- **Zed** — Fast, modern editor with a focus on performance and collaboration features (strength: snappy UI and multiplayer-style editing for teams that want a lighter footprint than a full IDE).
- **JetBrains IDEs** (IntelliJ, PyCharm, WebStorm, etc.) — Full IDEs with native Linux installers; strong refactor/navigation when you outgrow a text editor.
- **Sublime Text** — Fast, paid/commercial editor with a loyal following; native Linux build.
- **Neovim** — Modern Vim fork; popular for terminal-first setups and LSP-driven editing.

## Photo and image editing

- **GIMP** — Full-featured raster editor (Photoshop-class workflow at a high level; steeper learning curve but very capable).
- **Inkscape** — Vector graphics (SVG) when you need logos, diagrams, or illustration rather than photo retouching.
- **darktable** — RAW photo development and non-destructive edits for photography-heavy workflows.
- **Photopea** (web) — Surprisingly capable Photoshop-like editor in the browser when you need layered PSD-style work without a local Adobe install.

## Video editing

- **Pitivi** — Straightforward, GNOME-oriented editor for cuts, titles, and light projects without a steep pro-suite learning curve.
- **Shotcut** — Cross-platform timeline editor with a broad feature set for intermediate projects.
- **DaVinci Resolve** — Professional-grade grading and editing (strength: high-end color and finishing; heavier hardware/driver expectations).
- **OpenShot** — Beginner-friendly timeline editor; good for simple family/video projects.

## Audio and music production

- **Spotify** — Streaming catalog and playlists; official Linux client or Flatpak builds are common.
- **Strawberry Music Player** — Desktop music player for local libraries (tags, playlists, Last.fm); spiritual cousin to classic Clementine.
- **Rhythmbox** — Simple GNOME-integrated player for local music and some online sources.
- **Audacity** — Multi-track recording and editing for podcasts and quick audio fixes.
- **Reaper** — Commercial DAW with a native Linux build; popular for serious multitrack work when you outgrow Audacity.
- **Ardour** — Open-source DAW for recording/mixing; steeper learning curve, very capable.

## Running local AI models

- **Ollama** — Simple way to download and run local LLMs and embeddings on your machine (strength: quick setup, `ollama run`, integrates with many desktop and CLI tools).
- **LM Studio** — Desktop app for downloading and chatting with local models (strength: GUI-first exploration; availability can vary by packaging—check current Linux support).
- **llama.cpp** / **vLLM** (more technical) — When you want maximum control, APIs, or server-style inference.

## Office suites and documents

- **ONLYOFFICE Desktop Editors** — Strong **Microsoft Office file compatibility** (DOCX/XLSX/PPTX) when fidelity to MS layouts matters.
- **LibreOffice** — Full-featured open-source suite and a safe default for ODF workflows, general documents, and spreadsheets.
- **Evince** (GNOME Document Viewer) — Lightweight PDF viewing; integrates well with the desktop.

## Text editing

- **GNOME Text Editor** (or **gedit** on older setups) — Simple “notepad-style” editing for quick notes and config tweaks with a GUI.
- **Vim / GVim** — Modal, keyboard-driven editing for terminal-centric or power-user workflows (GVim adds menus and a GUI shell around the same editor).
- **GNU nano** — Terminal editor that advertises its shortcuts on-screen; gentle step up from “notepad in a terminal.”

## Notes, knowledge bases, and PKM

- **Obsidian** — Markdown notes with plugins and local-first files; popular for second-brain style workflows.
- **Joplin** — Markdown notes with sync options; good cross-platform replacement for simpler Evernote-style capture.
- **Standard Notes** — Encrypted, long-form notes with a focus on privacy and longevity.
- **Simplenote** — Minimal, fast notes with sync when you want almost no structure.
- **Logseq** — Outliner + graph notes; strong for bullet journals and linked thought (similar headspace to Roam).

## Email and calendar

- **Thunderbird** — Full desktop mail (and calendar/tasks with add-ons); closest mainstream OSS alternative to Outlook-style desktop mail.
- **Evolution** — GNOME-integrated mail/calendar/contacts; useful if you want tight desktop calendar workflows.

## Tasks and to-do lists

- **Endeavour** (**GNOME To Do**) — Official GNOME personal task manager (the project was renamed from “GNOME To Do”); lists, due dates, and a workflow that fits the rest of the desktop. Common Flatpak id: **`org.gnome.Todo`**.

## Chat and communication

- **Discord** — Voice, communities, and screen sharing for gaming/teams (official app or Flatpak).
- **Telegram** — Fast messaging, channels, and large file sharing; official desktop client available for Linux.
- **Signal Desktop** — End-to-end encrypted messaging with an official Linux build (linked to your phone number).
- **Slack** — Official Linux client exists for many teams (also usable in the browser).
- **Microsoft Teams** — Often used via **browser** or Progressive Web App; check current packaging—Linux desktop support changes over time.
- **Zoom** — Official Linux client for meetings.
- **Element** — Desktop client for **Matrix**; common for open communities and self-hosted chat.

## Cloud sync and backups

- **Nextcloud Desktop** — Sync client for self-hosted or provider-hosted Nextcloud (files, shares, some integrations).
- **Syncthing** — Peer-to-peer folder sync between your own devices without a central cloud.
- **Deja Dup** — Simple scheduled backups on GNOME (often targets cloud or external drives).
- **Timeshift** — Filesystem snapshots for “undo bad upgrade” style recovery (similar headspace to Windows restore points).

## Passwords and security

- **KeePassXC** — Offline-friendly password database compatible with KeePass formats.
- **Bitwarden** — Synced vault with official desktop and browser integration.
- **1Password** — Commercial manager with a Linux desktop client (useful if your org standardizes on it).
- **Proton VPN** (and other major VPN vendors) — Many publish Linux apps or OpenVPN/WireGuard configs; pick based on policy and audits.

## Simple drawing (“MS Paint–like”)

- **Drawing** — Lightweight GNOME drawing app for quick sketches, arrows, and basic image markup.
- **Pinta** — Bitmap painting with layers; closer to classic Paint.NET–style workflows on Linux.

## 3D, design, and engineering-ish

- **Blender** — 3D modeling, animation, and video sequencing; industry-grade and natively cross-platform.
- **FreeCAD** — Parametric CAD when you need engineering-style models rather than mesh sculpting.
- **QCAD** / **LibreCAD** — 2D CAD and technical drawings.

## Gaming and game stores

- **Steam** — Largest store/client; **Proton** enables many Windows titles on Linux.
- **Heroic Games Launcher** — Open-source Epic/GOG/Amazon Games launcher; complements Steam.
- **Lutris** — Installer scripts and runners for non-Steam stores, emulators, and Wine prefixes.
- **Bottles** — Manage Wine prefixes with a GUI (useful for odd Windows apps that are not games).

## Media creation (streaming / capture)

- **OBS Studio** — Screen recording and live streaming; standard across Windows/macOS/Linux.

## System utilities (GNOME-friendly)

- **GNOME Disks** — Partition, format, benchmark, and image drives with a simple UI.
- **Baobab (Disk Usage Analyzer)** — Find what is eating disk space.
- **GNOME Tweaks** — Fonts, themes, window buttons, startup apps—common first install on GNOME.
- **Extension Manager** — Install/update GNOME Shell extensions without hunting browser plugins.
- **Mission Center** / **Resources** — Modern resource monitors (CPU/RAM/GPU); pick what matches your distro’s packaging.
- **Flatseal** — Tweak Flatpak permissions per app (filesystem, network, devices).
- **Wine** — Low-level Windows API compatibility (often used via **Bottles** or game tools above) for oddball Windows-only utilities.

## Virtual machines

- **GNOME Boxes** — Simple VM app for trying distros or Windows installs.
- **VirtualBox** — Mature, easy sharing of VMs across OSes (extension pack/licensing note applies).
- **QEMU/KVM** + **virt-manager** — Faster native virtualization on Linux when you are comfortable with a bit more setup.

---

## Extras worth knowing (still GNOME-friendly)

- **Flatpak** — Packaging format that keeps many apps consistent across distributions (install **Flatpak** + **GNOME Software** with the Flatpak plugin for a smooth GUI workflow).
- **Fragments** or **Transmission** — Torrent clients with simple UIs.
- **File Roller** (Archive Manager) — Zip/tar/7z from the GUI; **p7zip**/**unzip** on the CLI.

---

## Notes

- **Availability** varies by distro; **Flatpak** (`flathub.org`) is often the fastest way to get up-to-date GNOME-friendly apps.
- When in doubt, prefer apps that follow **GNOME HIG** or ship as **Flatpak** from Flathub for fewer dependency surprises.
- If an app is missing, check **Flathub**, the vendor’s **`.deb`/`.rpm`**, or ** distro-specific** packages before reaching for **Snap**—policy varies by community.
