"""Reading pages: fixed word budgets over consecutive chunks that never cross a document.

Pages are the navigation unit of the reader. They are assigned deterministically
from the chunk order, so seeds do not need to store them and older databases can
be paginated on start-up.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import bindparam, update
from sqlmodel import Session, col, select

from app.models.entities import Chunk, Corpus, Document

PAGE_WORDS = 300


def count_words(text: str) -> int:
    return len(text.split())


def assign_pages(chunks: Iterable[tuple[int, int]], *, page_words: int = PAGE_WORDS) -> list[int]:
    """Page number (1-based) for every ``(document key, word count)`` in reading order.

    A page collects consecutive chunks of one document until adding the next chunk
    would exceed ``page_words``. Documents (chapters) always start on a new page,
    and a chunk longer than the budget gets a page of its own.
    """
    pages: list[int] = []
    page = 0
    words = 0
    current: int | None = None
    for document, n in chunks:
        if page == 0 or document != current or (words > 0 and words + n > page_words):
            page += 1
            words = 0
            current = document
        words += n
        pages.append(page)
    return pages


def paginate_corpus(session: Session, corpus: Corpus, *, page_words: int = PAGE_WORDS) -> int:
    """(Re)assign pages to all chunks of ``corpus`` and store ``corpus.n_pages``."""
    rows = session.exec(
        select(col(Chunk.id), col(Chunk.document_id), col(Chunk.text))
        .join(Document, col(Document.id) == col(Chunk.document_id))
        .where(Chunk.corpus_id == corpus.id)
        .order_by(col(Document.position), col(Chunk.position))
    ).all()
    pages = assign_pages(
        [(document_id, count_words(text)) for _, document_id, text in rows], page_words=page_words
    )
    if rows:
        statement = (
            update(Chunk)
            .where(col(Chunk.id) == bindparam("chunk"))
            .values(page=bindparam("number"))
        )
        session.connection().execute(
            statement, [{"chunk": row[0], "number": page} for row, page in zip(rows, pages)]
        )
    corpus.n_pages = pages[-1] if pages else 0
    session.add(corpus)
    return corpus.n_pages
