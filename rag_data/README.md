# RAG Seed Data for Meera

This directory contains curated Markdown documents intended to seed Meera's Linux-help knowledge base.

## Scope

- Distro-specific package install commands (Debian/Ubuntu, Fedora/RPM, Arch).
- Fedora Silverblue concepts (immutable OS, Toolbox, layering with rpm-ostree).
- Basics for common CLI tools (`vim`, `grep`, `sed`, `awk`, and others).

## MD-only RAG authoring format

For stronger retrieval and answer quality, each topic file should include:

1. What it is (plain-language definition)
2. When to use it
3. Common syntax/flags
4. Practical examples
5. Common mistakes or gotchas
6. Safety notes (if relevant)
7. Related commands
8. Sources

## Retrieval hints (no SQL required)

- Keep one topic per file with clear headings.
- Prefer short sections with explicit command names in headings.
- Repeat key terms users might ask (for example: "install package", "remove package", "update").
- Keep distro-specific commands in clearly labeled subsections.
- Include beginner wording in definitions so semantic retrieval works for novice questions.

## Authoring notes

- Keep each topic in a focused file.
- Prefer short, practical command examples.
- Add a "Sources" section for traceability.
- When commands are distro-specific, label them clearly.

