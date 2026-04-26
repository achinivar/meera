"""Split rag_data Markdown files into retrieval chunks at H2 boundaries.

Each chunk carries its parent H1 title and H2 section so the LLM gets enough
context when the chunk is shown to it. README.md is excluded (it documents
authoring conventions, not subject knowledge).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# We deliberately match exactly two leading hash characters at start-of-line.
# Three-or-more would be H3+, which we keep inside its parent H2 chunk.
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_EXCLUDE_FILENAMES = {"README.md", "readme.md"}


@dataclass(frozen=True)
class RagChunk:
    """A retrievable section of an rag_data document."""
    doc_path: str       # repo-relative path, e.g. "rag_data/grep_basics.md"
    doc_title: str      # H1 title, e.g. "grep Basics"
    section: str        # H2 heading, e.g. "Common usage"
    body: str           # raw markdown body of this H2 section (no heading line)

    @property
    def index_text(self) -> str:
        """Text used to compute the chunk's embedding.

        Includes the doc title and section heading so semantically related
        queries (e.g. "how do I tar a folder?") can match a chunk titled
        "archives_basics.md / Common usage".
        """
        return f"{self.doc_title} — {self.section}\n{self.body}".strip()

    @property
    def display_text(self) -> str:
        """Text shown to the LLM when this chunk is selected.

        Reconstitutes the heading so the LLM sees a self-contained Markdown
        snippet that's identifiable to the user as well.
        """
        return f"## {self.doc_title} — {self.section}\n\n{self.body}".strip()


def _split_at_h2(content: str) -> list[tuple[str, str]]:
    """Return [(section_title, body), ...] split at H2 boundaries.

    Anything before the first H2 is dropped (typically just the H1 title and
    maybe a one-line summary). Bodies preserve their original indentation and
    code fences.
    """
    matches = list(_H2_RE.finditer(content))
    if not matches:
        return []

    chunks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        section = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        if body:
            chunks.append((section, body))
    return chunks


def _extract_h1(content: str, fallback: str) -> str:
    m = _H1_RE.search(content)
    if m:
        return m.group(1).strip()
    return fallback


def chunk_markdown(content: str, doc_path: str) -> list[RagChunk]:
    """Split a single Markdown document into RagChunks at H2 boundaries."""
    fallback_title = Path(doc_path).stem.replace("_", " ").title()
    title = _extract_h1(content, fallback_title)
    sections = _split_at_h2(content)
    return [
        RagChunk(doc_path=doc_path, doc_title=title, section=section, body=body)
        for section, body in sections
    ]


def chunk_rag_directory(rag_root: Path) -> list[RagChunk]:
    """Walk an rag_data directory and return all RagChunks across all docs."""
    if not rag_root.is_dir():
        return []
    out: list[RagChunk] = []
    for md_path in sorted(rag_root.glob("*.md")):
        if md_path.name in _EXCLUDE_FILENAMES:
            continue
        try:
            content = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = f"rag_data/{md_path.name}"
        out.extend(chunk_markdown(content, rel))
    return out


def iter_chunk_index_texts(chunks: Iterable[RagChunk]) -> list[str]:
    """Convenience: pull index_text from each chunk in order."""
    return [c.index_text for c in chunks]
