"""Export/import of precomputed corpora (JSON) so the app runs without live extraction."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models.entities import Chunk, Corpus, Document, Edge, Entity, Mention

log = logging.getLogger(__name__)

SEED_FORMAT = 1


def export_corpus(session: Session, corpus: Corpus) -> dict[str, Any]:
    """Serialise a processed corpus (documents, chunks, entities, mentions, edges)."""
    documents = session.exec(
        select(Document).where(Document.corpus_id == corpus.id).order_by(Document.position)
    ).all()
    chunks = session.exec(
        select(Chunk).where(Chunk.corpus_id == corpus.id).order_by(Chunk.id)
    ).all()
    entities = session.exec(
        select(Entity).where(Entity.corpus_id == corpus.id).order_by(Entity.id)
    ).all()
    mentions = session.exec(
        select(Mention).where(Mention.corpus_id == corpus.id).order_by(Mention.id)
    ).all()
    edges = session.exec(select(Edge).where(Edge.corpus_id == corpus.id).order_by(Edge.id)).all()
    doc_pos = {d.id: i for i, d in enumerate(documents)}
    chunk_pos = {c.id: i for i, c in enumerate(chunks)}
    entity_pos = {e.id: i for i, e in enumerate(entities)}
    return {
        "format": SEED_FORMAT,
        "corpus": {
            "slug": corpus.slug,
            "title": corpus.title,
            "description": corpus.description,
            "genre": corpus.genre,
            "source": corpus.source,
            "language": corpus.language,
            "window": corpus.window,
            "extractor": corpus.extractor,
        },
        "documents": [{"title": d.title, "text": d.text} for d in documents],
        "chunks": [[doc_pos[c.document_id], c.position, c.start, c.end] for c in chunks],
        "entities": [[e.text, e.norm, e.label, e.count, e.degree, e.strength] for e in entities],
        "mentions": [
            [entity_pos[m.entity_id], chunk_pos[m.chunk_id], m.start, m.end, m.score]
            for m in mentions
        ],
        "edges": [
            [entity_pos[e.source_id], entity_pos[e.target_id], e.weight, e.count] for e in edges
        ],
    }


def import_corpus(session: Session, payload: dict[str, Any], *, visible: bool = True) -> Corpus:
    """Insert a serialised corpus; the slug must not exist yet."""
    if payload.get("format") != SEED_FORMAT:
        raise ValueError(f"Unsupported seed format {payload.get('format')!r}")
    meta = payload["corpus"]
    now = datetime.now(UTC)
    corpus = Corpus(
        **meta, status="ready", visible=visible, created_at=now, updated_at=now, processed_at=now
    )
    session.add(corpus)
    session.flush()
    documents = [
        Document(corpus_id=corpus.id, position=i, title=d["title"], text=d["text"])
        for i, d in enumerate(payload["documents"])
    ]  # type: ignore[arg-type]
    session.add_all(documents)
    session.flush()
    chunks = [
        Chunk(
            corpus_id=corpus.id,
            document_id=documents[d].id,
            position=p,
            start=s,
            end=e,
            text=documents[d].text[s:e],
        )  # type: ignore[arg-type]
        for d, p, s, e in payload["chunks"]
    ]
    session.add_all(chunks)
    session.flush()
    entities = [
        Entity(corpus_id=corpus.id, text=t, norm=n, label=lbl, count=c, degree=dg, strength=st)  # type: ignore[arg-type]
        for t, n, lbl, c, dg, st in payload["entities"]
    ]
    session.add_all(entities)
    session.flush()
    session.add_all(
        Mention(
            corpus_id=corpus.id,
            entity_id=entities[e].id,
            document_id=chunks[c].document_id,
            chunk_id=chunks[c].id,
            start=s,
            end=t,
            score=sc,
        )  # type: ignore[arg-type]
        for e, c, s, t, sc in payload["mentions"]
    )
    session.add_all(
        Edge(
            corpus_id=corpus.id,
            source_id=entities[a].id,
            target_id=entities[b].id,
            weight=w,
            count=n,
        )  # type: ignore[arg-type]
        for a, b, w, n in payload["edges"]
    )
    corpus.n_documents = len(documents)
    corpus.n_chunks = len(chunks)
    corpus.n_entities = len(entities)
    corpus.n_edges = len(payload["edges"])
    corpus.n_mentions = len(payload["mentions"])
    session.add(corpus)
    session.commit()
    session.refresh(corpus)
    return corpus


def import_seed_directory(engine: Engine, seed_dir: Path) -> list[str]:
    """Import every ``*.json`` seed whose slug is not in the database yet."""
    imported: list[str] = []
    if not seed_dir.exists():
        return imported
    for path in sorted(seed_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        slug = payload.get("corpus", {}).get("slug")
        if not slug:
            continue
        with Session(engine) as session:
            if session.exec(select(Corpus).where(Corpus.slug == slug)).first() is not None:
                continue
            import_corpus(session, payload)
            imported.append(slug)
            log.info("imported seed corpus %s from %s", slug, path.name)
    return imported
