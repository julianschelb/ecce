"""Corpus processing pipeline: documents → chunks → entities → implicit network → SQLite."""

from __future__ import annotations

import bisect
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
from implicit_word_network import Document as IWNDocument
from implicit_word_network import ImplicitNetwork, NetworkConfig
from implicit_word_network.extraction import BaseEntityExtractor
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models.entities import Chunk, Corpus, Document, Edge, Entity, Mention
from app.services.chunking import chunk_document

log = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]

_DETERMINERS = ("the ", "a ", "an ")
EXCERPT_CHARS = 700


def make_excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """First paragraph(s) of a text, cut at a word boundary, for the gallery."""
    words = " ".join(text.split()).split(" ")
    out: list[str] = []
    length = 0
    for word in words:
        if length + len(word) + 1 > limit:
            break
        out.append(word)
        length += len(word) + 1
    excerpt = " ".join(out)
    return excerpt + ("…" if len(excerpt) < len(" ".join(words)) else "")


def normalize_entity(text: str) -> str:
    """Entity identity: lowercase, collapsed whitespace, leading determiner and possessive removed.

    spaCy spans often include a leading article ("the White Rabbit"), so this
    merges them with the bare name ("White Rabbit").
    """
    norm = " ".join(text.split()).lower()
    for determiner in _DETERMINERS:
        if norm.startswith(determiner) and len(norm) > len(determiner) + 1:
            norm = norm[len(determiner) :]
            break
    for possessive in ("’s", "'s"):
        if norm.endswith(possessive) and len(norm) > len(possessive) + 1:
            norm = norm[: -len(possessive)]
    return norm


def reset_corpus_analysis(session: Session, corpus_id: int) -> None:
    """Delete chunks, entities, mentions and edges of a corpus (documents are kept)."""
    for table in (Mention, Edge, Entity, Chunk):
        session.exec(delete(table).where(col(table.corpus_id) == corpus_id))  # type: ignore[call-overload]


def process_corpus(
    session: Session,
    corpus: Corpus,
    extractor: BaseEntityExtractor,
    settings: Settings,
    *,
    extractor_name: str = "",
    progress: ProgressCallback | None = None,
) -> Corpus:
    """Run the full pipeline for one corpus and persist the results.

    The implicit network is built per document (sentence windows never cross
    documents), entity identities are merged across the whole corpus by the
    network, and mention offsets are mapped onto paragraph chunks for the
    reader and full-text search.
    """
    report = progress or (lambda _p, _m: None)
    documents = session.exec(
        select(Document).where(Document.corpus_id == corpus.id).order_by(col(Document.position))
    ).all()
    reset_corpus_analysis(session, corpus.id)  # type: ignore[arg-type]
    session.flush()

    # ---- chunks
    chunk_rows: dict[int, list[Chunk]] = {}
    for document in documents:
        rows = [
            Chunk(
                corpus_id=corpus.id,  # type: ignore[arg-type]
                document_id=document.id,  # type: ignore[arg-type]
                position=index,
                start=span.start,
                end=span.end,
                text=span.text(document.text),
            )
            for index, span in enumerate(
                chunk_document(document.text, max_words=settings.max_chunk_words)
            )
        ]
        session.add_all(rows)
        chunk_rows[document.id] = rows  # type: ignore[index]
    corpus.status = "processing"
    session.add(corpus)
    session.commit()  # release the write lock so progress updates can be written
    for rows in chunk_rows.values():
        for row in rows:
            session.refresh(row)
    report(0.1, f"{sum(len(r) for r in chunk_rows.values())} chunks")

    # ---- annotation + network
    window = corpus.window if corpus.window is not None else settings.window
    network = ImplicitNetwork(NetworkConfig(window=window), normalize_entity=normalize_entity)
    total = max(len(documents), 1)
    for index, document in enumerate(documents):
        annotated = extractor.annotate_all([IWNDocument(document.text, document.id)])  # type: ignore[arg-type]
        network.add_documents(annotated)
        report(0.1 + 0.7 * (index + 1) / total, f"annotated {index + 1}/{len(documents)} documents")

    # ---- entities
    counts = network.entity_counts()
    src, tgt, weights, edge_counts = network.edge_table()
    n = network.n_entities
    degree = np.bincount(src, minlength=n) + np.bincount(tgt, minlength=n)
    strength = np.bincount(src, weights=weights, minlength=n) + np.bincount(
        tgt, weights=weights, minlength=n
    )
    report(0.82, f"{n} entities, {len(src)} edges: writing")
    entity_rows: list[Entity] = []
    for node in network.iter_entities():
        entity_rows.append(
            Entity(
                corpus_id=corpus.id,  # type: ignore[arg-type]
                text=_display_text(node.text),
                norm=node.norm,
                label=node.label,
                count=int(counts[node.id]),
                degree=int(degree[node.id]) if n else 0,
                strength=float(strength[node.id]) if n else 0.0,
            )
        )
    session.add_all(entity_rows)
    session.flush()
    entity_db_id = [row.id for row in entity_rows]  # network id -> db id (same order)

    # ---- edges
    session.add_all(
        Edge(
            corpus_id=corpus.id,  # type: ignore[arg-type]
            source_id=entity_db_id[int(s)],  # type: ignore[arg-type]
            target_id=entity_db_id[int(t)],  # type: ignore[arg-type]
            weight=float(w),
            count=int(c),
        )
        for s, t, w, c in zip(src, tgt, weights, edge_counts)
    )

    # ---- mentions mapped onto chunks
    doc_by_id = {document.id: document for document in documents}
    chunk_index: dict[int, tuple[list[int], list[Chunk]]] = {}
    for document_id, rows in chunk_rows.items():
        chunk_index[document_id] = ([row.start for row in rows], rows)
    mention_rows: list[Mention] = []
    for node in network.iter_entities():
        for mention in network.mentions_of(node):
            document_id = int(mention.sentence.document)
            starts, rows = chunk_index.get(document_id, ([], []))  # type: ignore[arg-type]
            if not rows:
                continue
            k = bisect.bisect_right(starts, mention.start) - 1
            if k < 0:
                continue
            chunk = rows[k]
            if mention.start >= chunk.end:
                continue
            mention_rows.append(
                Mention(
                    corpus_id=corpus.id,  # type: ignore[arg-type]
                    entity_id=entity_db_id[node.id],  # type: ignore[arg-type]
                    document_id=document_id,  # type: ignore[arg-type]
                    chunk_id=chunk.id,  # type: ignore[arg-type]
                    start=mention.start - chunk.start,
                    end=min(mention.end, chunk.end) - chunk.start,
                    score=mention.score,
                )
            )
    session.add_all(mention_rows)
    _ = doc_by_id

    # ---- corpus bookkeeping
    first_chunks = next((rows for rows in chunk_rows.values() if rows), [])
    corpus.excerpt = make_excerpt(first_chunks[0].text) if first_chunks else ""
    corpus.n_documents = len(documents)
    corpus.n_chunks = sum(len(rows) for rows in chunk_rows.values())
    corpus.n_entities = n
    corpus.n_edges = int(len(src))
    corpus.n_mentions = len(mention_rows)
    corpus.window = window
    corpus.extractor = extractor_name or corpus.extractor
    corpus.status = "ready"
    corpus.error = None
    corpus.processed_at = datetime.now(UTC)
    corpus.updated_at = datetime.now(UTC)
    session.add(corpus)
    session.commit()
    report(1.0, "ready")
    log.info("processed corpus %s: %d entities, %d edges", corpus.slug, n, len(src))
    return corpus


def _display_text(text: str) -> str:
    """Strip a leading determiner from the first-seen surface form for display."""
    lowered = text.lower()
    for determiner in _DETERMINERS:
        if lowered.startswith(determiner) and len(text) > len(determiner) + 1:
            return text[len(determiner) :]
    return text
