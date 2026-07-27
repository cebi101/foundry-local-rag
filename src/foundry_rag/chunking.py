"""Split documents into retrieval-sized chunks.

Strategy (structure-aware, then paragraph-aware, then sentence-aware):

1. Walk the document and track the most recent Markdown heading, so every chunk
   knows which section it came from.
2. Accumulate whole paragraphs until adding another would exceed ``chunk_size``.
3. A single paragraph longer than ``chunk_size`` is split on sentence boundaries.
4. Consecutive chunks share ``chunk_overlap`` characters so a fact sitting on a
   boundary is not lost by either side.

This module is pure: no I/O, no models. That makes it the easiest part of the
project to unit-test, which is why the tests start here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterator

# A sentence ends at . ! ? … possibly followed by quotes/brackets, then whitespace.
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+")
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage."""

    source: str
    index: int
    heading: str
    text: str

    @property
    def content_hash(self) -> str:
        """Stable id for the chunk's text, used to skip unchanged work."""
        payload = f"{self.source}\x00{self.heading}\x00{self.text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def with_heading_prefix(self) -> str:
        """Text as it should be embedded: heading included for context.

        A chunk torn out of its document loses the section it belonged to.
        Prefixing the heading measurably improves retrieval on structured docs.
        """
        if self.heading:
            return f"{self.heading}\n\n{self.text}"
        return self.text


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences, never returning empty strings."""
    parts = [s.strip() for s in _SENTENCE_END.split(paragraph)]
    return [s for s in parts if s]


def _hard_split(text: str, size: int) -> list[str]:
    """Last-resort split for a single sentence longer than one chunk."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def _tail_overlap(text: str, overlap: int) -> str:
    """Take the last ``overlap`` characters, snapped to a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    # avoid starting the overlap mid-word
    space = tail.find(" ")
    if 0 <= space < len(tail) - 1:
        tail = tail[space + 1 :]
    return tail.strip()


def _iter_sections(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(heading, body)`` pairs, splitting on Markdown headings."""
    heading = ""
    buffer: list[str] = []
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if buffer:
                yield heading, "\n".join(buffer)
                buffer = []
            heading = match.group(2)
        else:
            buffer.append(line)
    if buffer:
        yield heading, "\n".join(buffer)


def _pack_units(units: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Greedily pack text units into chunks, carrying overlap between them."""
    chunks: list[str] = []
    current = ""

    for unit in units:
        if not unit:
            continue
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= chunk_size or not current:
            current = candidate
            # a single oversized unit still has to be broken up
            while len(current) > chunk_size:
                head, current = current[:chunk_size], current[chunk_size:].lstrip()
                chunks.append(head.strip())
                if current:
                    current = f"{_tail_overlap(head, chunk_overlap)} {current}".strip()
        else:
            chunks.append(current.strip())
            overlap = _tail_overlap(current, chunk_overlap)
            current = f"{overlap}\n\n{unit}".strip() if overlap else unit

    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def chunk_text(text: str, chunk_size: int = 900, chunk_overlap: int = 150) -> list[str]:
    """Split raw text into overlapping chunks. Returns plain strings."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if not text or not text.strip():
        return []

    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        # paragraph too long on its own -> go down to sentences
        for sentence in _split_sentences(paragraph):
            if len(sentence) <= chunk_size:
                units.append(sentence)
            else:
                units.extend(_hard_split(sentence, chunk_size))

    return _pack_units(units, chunk_size, chunk_overlap)


def chunk_document(
    text: str,
    source: str,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> list[Chunk]:
    """Split a document into :class:`Chunk` objects, preserving section headings."""
    chunks: list[Chunk] = []
    index = 0
    for heading, body in _iter_sections(text):
        for piece in chunk_text(body, chunk_size, chunk_overlap):
            chunks.append(Chunk(source=source, index=index, heading=heading, text=piece))
            index += 1
    return chunks
