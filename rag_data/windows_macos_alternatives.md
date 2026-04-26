# Windows and macOS Apps on Linux

## What it is

A practical mapping from **Windows/macOS habits** to **Linux equivalents**. For each well-known Windows or macOS app, this lists either the native Linux build (when one exists) or the closest practical alternative on a GNOME desktop. Many apps are **web-first** now, so "open it in the browser" is often the right answer.

## When to use it

Use this when someone is migrating from Windows or macOS and asks "is *X* on Linux?" or "what do I use instead of *X*?". It's representative, not exhaustive — when in doubt, check **Flathub** and the vendor site for an official Linux build.

## Apps that already have a native Linux build

Examples people are often surprised to find natively on Linux: **Chrome, Firefox, Brave, Edge, VS Code, VSCodium, Slack, Discord, Telegram, Signal, Zoom, Spotify, Steam, OBS, Blender, VLC, Docker, most JetBrains IDEs, Sublime Text, Thunderbird, Bitwarden, KeePassXC, Nextcloud client, Syncthing, Reaper, DaVinci Resolve, QCAD**, plus many **Electron** apps. For these, use the **official Linux build** (or the **Flatpak** on Flathub) — there's no need for an alternative.

## Microsoft Office

- **ONLYOFFICE Desktop Editors** — Best **DOCX/XLSX/PPTX** layout fidelity when you exchange files with MS Office users.
- **LibreOffice** — Full open-source suite; safe default for ODF and general docs.
- **Office on the web** — Word/Excel/PowerPoint in the browser when you need exact MS rendering for a specific file.

## Adobe Photoshop

- **GIMP** — Closest free Photoshop replacement for raster editing and retouching.
- **darktable** — Non-destructive **RAW** photo development (the Lightroom-style half of Photoshop).
- **Photopea** (web) — Browser-based, layered PSD-style editor when you need familiar Photoshop tooling without a local install.

## Adobe Illustrator

- **Inkscape** — Vector graphics editor (SVG-first); the standard Linux choice for logos, diagrams, and illustration.

## Adobe Premiere / Final Cut Pro

- **DaVinci Resolve** — Professional-grade timeline editing and color grading; native Linux build (note hardware/driver expectations).
- **Shotcut** — Cross-platform timeline editor for intermediate projects.
- **Pitivi** — Lightweight, GNOME-oriented editor for cuts, titles, and short videos.
- **OpenShot** — Beginner-friendly editor for simple family/video projects.

## Adobe Lightroom

- **darktable** — RAW workflow, non-destructive edits, library and tagging.
- **RawTherapee** — Alternative RAW developer with a different UI/feature mix.

## Sketch (macOS)

- **Figma** (web) — De facto industry standard, runs in any browser.
- **Penpot** (web / self-hostable) — Open-source Figma-like design tool.
- **Inkscape** — When you mostly need vector editing rather than collaborative UI design.

## Notion / Evernote

- **Obsidian** — Markdown notes with plugins and local-first files; popular for "second brain" workflows.
- **Joplin** — Markdown notes with sync; good for simpler Evernote-style capture.
- **Standard Notes** — Encrypted long-form notes focused on privacy and longevity.
- **Web app** — Notion and Evernote both run fine in the browser if you want to keep them.

## Microsoft To Do / Apple Reminders

- **Endeavour** (also known as **GNOME To Do**) — Official GNOME personal task manager; lists, due dates, and a workflow that fits the rest of the desktop. Common Flatpak id: **`org.gnome.Todo`**.
- **Provider web apps** — Microsoft To Do and Apple Reminders are also accessible through their respective web sites.

## Apple Photos / iCloud Photos

- **Shotwell** — Simple GNOME photo library app for local collections.
- **Folder-based workflows** — Many people on Linux organize photos as plain folders + a viewer rather than an "all-in-one" library app.
- **Provider web UI** — iCloud Photos has a web interface that works on Linux browsers.
- **rclone** — Power-user option for syncing photos across cloud providers from the CLI.

## iTunes / Apple Music

- **Spotify** — Native Linux client / Flatpak; covers most "streaming" use cases.
- **Strawberry Music Player** — Local library player for tagged music collections.
- **Rhythmbox** — GNOME-integrated local music player.
- **Apple Music** is often used as a **browser/PWA** on Linux since there is no official desktop client.

## OneDrive

- **Nextcloud** — Self-hosted or provider-hosted alternative with an official Linux desktop client.
- **Insync** — Paid commercial client that does support OneDrive on Linux.
- **rclone** — CLI tool for mounting/syncing OneDrive (and many other providers).

## Visual Studio (Windows-only IDEs)

This is the full Microsoft **Visual Studio** product, **not** VS Code (which is already cross-platform).

- **JetBrains IDEs** (IntelliJ, PyCharm, CLion, Rider, etc.) — Closest "full IDE" experience on Linux.
- **Visual Studio Code** / **VSCodium** — Lighter, extension-based editor; covers most Visual Studio use cases for many languages.
- **Qt Creator** — Strong choice for C++/Qt projects.
- **Language-specific tools** — `dotnet` SDK, `gcc`/`clang`, etc., often paired with VS Code.

## Postman

- **Postman** — Has an official Linux build (Electron); same workflows as on Windows/macOS.
- **Insomnia** — Open-source-leaning REST/GraphQL client with a similar UI.
- **Bruno** — Newer, file-based API client (collections live as files in your repo).
- **curl** + small scripts — When you don't need a GUI at all.

## Figma desktop

- **Figma in the browser** — Officially supported on Linux; same files, same plugins.
- **Penpot** — Open-source design tool you can self-host if you want to leave Figma entirely.

## NVIDIA Broadcast and OEM utilities

Vendor "broadcast/studio" tools (NVIDIA Broadcast, vendor camera/audio enhancers) usually have **no Linux equivalent** from the vendor.

- **OBS Studio** + plugins — Covers a lot of the "stream/record with effects" surface area.
- **EasyEffects** — PipeWire-based audio effects (noise suppression, EQ, compressor) for microphones and outputs system-wide.
- Vendor-specific features (RTX Voice, Studio drivers' extras) may simply not be available on Linux; pick the closest open replacement.

## Running Windows software anyway

When there is no Linux build and no good alternative, you can still run Windows software through a compatibility layer or VM:

- **Wine** — Compatibility layer for many Windows programs (quality varies wildly by app; check a compatibility database before relying on it).
- **Bottles** — GUI for managing Wine prefixes; friendlier than raw Wine.
- **CrossOver** — Commercial Wine polish with vendor support for specific tested apps.
- **VM** — **GNOME Boxes**, **VirtualBox**, or **KVM/virt-manager** for a full Windows install when compatibility layers are not enough.

## Notes

- **Availability** of Linux builds varies by distro and over time; **Flathub** (`flathub.org`) is often the fastest way to confirm and install a recent version.
- Treat this as a **starting point**, not a complete catalog — the Linux app landscape changes frequently, especially as Electron and PWA versions appear.
