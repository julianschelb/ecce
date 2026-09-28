"""Splitting raw text into documents (chapters/sections) and chunks (paragraphs)."""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(
    r"^(?:#{1,3}\s+.+|(?:CHAPTER|Chapter|BOOK|Book|PART|Part|LIBER|Liber)\s+[A-Z0-9IVXLC]+\.?.*)$",
    re.M,
)
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(\[])")


@dataclass(frozen=True)
class DocumentPart:
    """A document produced by splitting a text."""

    title: str
    text: str


@dataclass(frozen=True)
class ChunkSpan:
    """A chunk as a character span of its document."""

    start: int
    end: int

    def text(self, document: str) -> str:
        return document[self.start : self.end]


def split_documents(
    text: str, mode: str = "auto", *, default_title: str = ""
) -> list[DocumentPart]:
    """Split ``text`` into documents.

    ``"headings"`` splits at chapter/part or Markdown headings, ``"none"`` keeps
    one document and ``"auto"`` splits only when at least two headings exist.
    A heading line followed directly by a short title line (Gutenberg style
    ``CHAPTER I.`` / ``Down the Rabbit-Hole``) is merged into the title.
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    headings = list(HEADING_RE.finditer(text))
    if mode == "none" or (mode == "auto" and len(headings) < 2) or not headings:
        return [DocumentPart(default_title, text)]

    parts: list[DocumentPart] = []
    preface = text[: headings[0].start()].strip()
    if preface:
        parts.append(DocumentPart(default_title or "Preface", preface))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end() : end].strip("\n")
        title = match.group(0).strip().lstrip("#").strip()
        lines = body.split("\n", 2)
        if (
            lines
            and lines[0].strip()
            and len(lines[0].strip()) <= 80
            and not lines[0].strip().endswith((".", ","))
            and (len(lines) < 2 or not lines[1].strip())
        ):
            title = f"{title} {lines[0].strip()}"
            body = lines[2] if len(lines) > 2 else ""
        body = body.strip()
        if body:
            parts.append(DocumentPart(title, body))
    return parts or [DocumentPart(default_title, text)]


def chunk_document(text: str, *, max_words: int = 180) -> list[ChunkSpan]:
    """Split a document into paragraph chunks of at most ``max_words`` words.

    Paragraphs (blank-line separated) are the primary unit; long paragraphs
    are divided at sentence boundaries. Offsets refer to ``text``.
    """
    spans: list[ChunkSpan] = []
    position = 0
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        start = text.index(paragraph, position) if paragraph else position
        position = start + len(paragraph)
        stripped = paragraph.strip()
        if not stripped:
            continue
        lead = len(paragraph) - len(paragraph.lstrip())
        p_start = start + lead
        p_end = p_start + len(stripped)
        if len(stripped.split()) <= max_words:
            spans.append(ChunkSpan(p_start, p_end))
            continue
        # sentence-level split of an overlong paragraph
        current_start = p_start
        words = 0
        cursor = p_start
        for match in _SENTENCE_SPLIT.finditer(text, p_start, p_end):
            sentence_end = match.start()
            words += len(text[cursor:sentence_end].split())
            cursor = match.end()
            if words >= max_words:
                spans.extend(_split_words(text, current_start, sentence_end, max_words))
                current_start = cursor
                words = 0
        if current_start < p_end:
            spans.extend(_split_words(text, current_start, p_end, max_words))
    return spans


def _split_words(text: str, start: int, end: int, max_words: int) -> list[ChunkSpan]:
    """Split a span at whitespace so that no piece exceeds ``max_words`` words."""
    if len(text[start:end].split()) <= max_words:
        return [ChunkSpan(start, end)]
    pieces: list[ChunkSpan] = []
    piece_start = start
    count = 0
    position = start
    while position < end:
        while position < end and text[position].isspace():
            position += 1
        word_start = position
        while position < end and not text[position].isspace():
            position += 1
        if position > word_start:
            count += 1
            if count > max_words:
                pieces.append(ChunkSpan(piece_start, _rstrip(text, piece_start, word_start)))
                piece_start = word_start
                count = 1
    if piece_start < end:
        pieces.append(ChunkSpan(piece_start, end))
    return pieces


def _rstrip(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1].isspace():
        end -= 1
    return end


def slugify(value: str, *, max_length: int = 60) -> str:
    """Lowercase ASCII slug for URLs."""
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:max_length].strip("-") or "corpus"
