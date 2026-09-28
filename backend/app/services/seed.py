"""Export/import of precomputed corpora (JSON) so the app runs without live extraction."""

from __future__ import annotations

import gzip
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert
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
    """Insert a serialised corpus with bulk inserts; the slug must not exist yet."""
    if payload.get("format") != SEED_FORMAT:
        raise ValueError(f"Unsupported seed format {payload.get('format')!r}")
    meta = payload["corpus"]
    now = datetime.now(UTC)
    corpus = Corpus(
        **meta, status="ready", visible=visible, created_at=now, updated_at=now, processed_at=now
    )
    session.add(corpus)
    session.flush()
    connection = session.connection()

    def bulk(model, rows: list[dict[str, Any]]) -> list[int]:
        """Insert rows and return their ids (SQLite assigns them sequentially)."""
        if not rows:
            return []
        for start in range(0, len(rows), 5000):
            connection.execute(insert(model), rows[start : start + 5000])
        last = connection.execute(
            insert(model).values(**{**rows[-1], "id": None}).returning(model.id)
        ).scalar_one()
        connection.execute(model.__table__.delete().where(model.id == last))  # type: ignore[attr-defined]
        first = last - len(rows)
        return list(range(first, last))

    documents = [
        {"corpus_id": corpus.id, "position": i, "title": d["title"], "text": d["text"]}
        for i, d in enumerate(payload["documents"])
    ]
    doc_ids = bulk(Document, documents)
    chunks = [
        {
            "corpus_id": corpus.id,
            "document_id": doc_ids[d],
            "position": p,
            "start": s,
            "end": e,
            "text": documents[d]["text"][s:e],
        }
        for d, p, s, e in payload["chunks"]
    ]
    chunk_ids = bulk(Chunk, chunks)
    entities = [
        {
            "corpus_id": corpus.id,
            "text": t,
            "norm": n,
            "label": lbl,
            "count": c,
            "degree": dg,
            "strength": st,
        }
        for t, n, lbl, c, dg, st in payload["entities"]
    ]
    entity_ids = bulk(Entity, entities)
    bulk(
        Mention,
        [
            {
                "corpus_id": corpus.id,
                "entity_id": entity_ids[e],
                "document_id": chunks[c]["document_id"],
                "chunk_id": chunk_ids[c],
                "start": s,
                "end": t,
                "score": sc,
            }
            for e, c, s, t, sc in payload["mentions"]
        ],
    )
    bulk(
        Edge,
        [
            {
                "corpus_id": corpus.id,
                "source_id": entity_ids[a],
                "target_id": entity_ids[b],
                "weight": w,
                "count": n,
            }
            for a, b, w, n in payload["edges"]
        ],
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


def read_seed(path: Path) -> dict[str, Any]:
    """Load a ``.json`` or ``.json.gz`` seed file."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_seed(path: Path, payload: dict[str, Any]) -> Path:
    """Write a seed file, gzip-compressed when the path ends with ``.gz``."""
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
            handle.write(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def import_seed_directory(engine: Engine, seed_dir: Path) -> list[str]:
    """Import every ``*.json`` / ``*.json.gz`` seed whose slug is not in the database yet."""
    imported: list[str] = []
    if not seed_dir.exists():
        return imported
    paths = sorted(list(seed_dir.glob("*.json")) + list(seed_dir.glob("*.json.gz")))
    for path in paths:
        try:
            payload = read_seed(path)
        except Exception as error:  # noqa: BLE001
            log.warning("skipping unreadable seed %s: %s", path.name, error)
            continue
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


def import_seeds_in_background(engine: Engine, seed_dir: Path) -> threading.Thread:
    """Import seeds on a daemon thread so the API answers immediately."""

    def run() -> None:
        try:
            imported = import_seed_directory(engine, seed_dir)
            if imported:
                log.info("seeded corpora: %s", ", ".join(imported))
        except Exception:  # noqa: BLE001
            log.exception("seed import failed")

    thread = threading.Thread(target=run, name="ecce-seed", daemon=True)
    thread.start()
    return thread
