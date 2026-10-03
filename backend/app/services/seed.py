"""Export/import of precomputed corpora (JSON) so the app runs without live extraction."""

from __future__ import annotations

import gzip
import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.models.entities import Chunk, Corpus, Document, Edge, Entity, Mention
from app.services.pagination import assign_pages, count_words

log = logging.getLogger(__name__)

SEED_FORMAT = 1
# slugs of bundled corpora that were withdrawn (e.g. rights not fully cleared): deleted on start-up
WITHDRAWN_FILE = "withdrawn.txt"


def withdrawn_slugs(seed_dir: Path) -> set[str]:
    path = seed_dir / WITHDRAWN_FILE
    if not path.exists():
        return set()
    lines = (
        line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()
    )
    return {line for line in lines if line}


def export_corpus(session: Session, corpus: Corpus) -> dict[str, Any]:
    """Serialise a processed corpus (documents, chunks, entities, mentions, edges)."""
    documents = session.exec(
        select(Document).where(Document.corpus_id == corpus.id).order_by(col(Document.position))
    ).all()
    chunks = session.exec(
        select(Chunk).where(Chunk.corpus_id == corpus.id).order_by(col(Chunk.id))
    ).all()
    entities = session.exec(
        select(Entity).where(Entity.corpus_id == corpus.id).order_by(col(Entity.id))
    ).all()
    mentions = session.exec(
        select(Mention).where(Mention.corpus_id == corpus.id).order_by(col(Mention.id))
    ).all()
    edges = session.exec(
        select(Edge).where(Edge.corpus_id == corpus.id).order_by(col(Edge.id))
    ).all()
    doc_pos = {d.id: i for i, d in enumerate(documents)}
    chunk_pos = {c.id: i for i, c in enumerate(chunks)}
    entity_pos = {e.id: i for i, e in enumerate(entities)}
    return {
        "format": SEED_FORMAT,
        "corpus": {
            "slug": corpus.slug,
            "title": corpus.title,
            "author": corpus.author,
            "year": corpus.year,
            "description": corpus.description,
            "genre": corpus.genre,
            "source": corpus.source,
            "source_url": corpus.source_url,
            "license": corpus.license,
            "license_url": corpus.license_url,
            "rights": corpus.rights,
            "language": corpus.language,
            "window": corpus.window,
            "extractor": corpus.extractor,
            "revision": corpus.seed_revision,
        },
        "documents": [{"title": d.title, "text": d.text} for d in documents],
        "chunks": [[doc_pos[c.document_id], c.position, c.start, c.end] for c in chunks],
        "entities": [[e.text, e.norm, e.label, e.count, e.degree, e.strength] for e in entities],
        "mentions": [
            [entity_pos[m.entity_id], chunk_pos[m.chunk_id], m.start, m.end, m.score]
            for m in mentions
        ],
        "edges": [  # a fifth element holds the typed relations, when there are any
            [entity_pos[e.source_id], entity_pos[e.target_id], e.weight, e.count]
            + ([json.loads(e.relations)] if e.relations else [])
            for e in edges
        ],
    }


def import_corpus(session: Session, payload: dict[str, Any], *, visible: bool = True) -> Corpus:
    """Insert a serialised corpus with bulk inserts; the slug must not exist yet."""
    if payload.get("format") != SEED_FORMAT:
        raise ValueError(f"Unsupported seed format {payload.get('format')!r}")
    meta = dict(payload["corpus"])
    revision = int(meta.pop("revision", 0) or 0)
    now = datetime.now(UTC)
    corpus = Corpus(
        **meta,
        seed_revision=revision,
        status="ready",
        visible=visible,
        created_at=now,
        updated_at=now,
        processed_at=now,
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
    reading_order = sorted(
        range(len(chunks)), key=lambda i: (payload["chunks"][i][0], payload["chunks"][i][1])
    )
    for i, page in zip(
        reading_order,
        assign_pages(
            [(chunks[i]["document_id"], count_words(chunks[i]["text"])) for i in reading_order]
        ),
    ):
        chunks[i]["page"] = page
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
                "weight": edge[2],
                "count": edge[3],
                "relations": json.dumps(edge[4]) if len(edge) > 4 else "",
            }
            for edge in payload["edges"]
            for a, b in [edge[:2]]
        ],
    )
    from app.services.processing import pick_excerpt, top_entity_names

    corpus.excerpt = pick_excerpt([c["text"] for c in chunks[:12]])
    corpus.highlights = top_entity_names([(e["text"], e["count"], e["strength"]) for e in entities])
    corpus.n_documents = len(documents)
    corpus.n_chunks = len(chunks)
    corpus.n_entities = len(entities)
    corpus.n_edges = len(payload["edges"])
    corpus.n_mentions = len(payload["mentions"])
    corpus.n_pages = max((c["page"] for c in chunks), default=0)
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


def import_seed_directory(
    engine: Engine, seed_dir: Path, on_replaced: Callable[[int], None] | None = None
) -> list[str]:
    """Import every ``*.json`` / ``*.json.gz`` seed whose slug is not in the database yet.

    A seed whose ``revision`` is newer than the one a corpus was imported from replaces that
    corpus (e.g. after its text was cleaned); otherwise only the metadata is synchronised.
    ``on_replaced`` receives the id of every replaced corpus (to drop cached graphs: SQLite may
    hand the same id to the new corpus).
    """
    imported: list[str] = []
    if not seed_dir.exists():
        return imported
    withdrawn = withdrawn_slugs(seed_dir)
    if withdrawn:
        with Session(engine) as session:
            gone = session.exec(select(Corpus).where(col(Corpus.slug).in_(withdrawn))).all()
            for corpus in gone:
                corpus_id, slug = corpus.id, corpus.slug
                session.delete(corpus)
                session.commit()
                log.info("removed withdrawn corpus %s", slug)
                if on_replaced is not None and corpus_id is not None:
                    on_replaced(corpus_id)
    paths = sorted(list(seed_dir.glob("*.json")) + list(seed_dir.glob("*.json.gz")))
    for path in paths:
        try:
            payload = read_seed(path)
        except Exception as error:  # noqa: BLE001
            log.warning("skipping unreadable seed %s: %s", path.name, error)
            continue
        slug = payload.get("corpus", {}).get("slug")
        if not slug or slug in withdrawn:
            continue
        with Session(engine) as session:
            existing = session.exec(select(Corpus).where(Corpus.slug == slug)).first()
            revision = int(payload["corpus"].get("revision", 0) or 0)
            if existing is not None and revision > existing.seed_revision:
                visible, old_id = existing.visible, existing.id
                session.delete(existing)
                session.commit()
                import_corpus(session, payload, visible=visible)
                if on_replaced is not None and old_id is not None:
                    on_replaced(old_id)
                imported.append(slug)
                log.info("replaced seed corpus %s with revision %d", slug, revision)
                continue
            if existing is not None:
                if sync_corpus_metadata(session, existing, payload):
                    log.info("updated metadata of seed corpus %s", slug)
                continue
            import_corpus(session, payload)
            imported.append(slug)
            log.info("imported seed corpus %s from %s", slug, path.name)
    return imported


SYNCED_FIELDS = (
    "title",
    "author",
    "year",
    "description",
    "genre",
    "source",
    "source_url",
    "license",
    "license_url",
    "rights",
    "language",
)


def sync_corpus_metadata(session: Session, corpus: Corpus, payload: dict[str, Any]) -> bool:
    """Refresh descriptive metadata and the excerpt of an already imported seed corpus."""
    from app.services.processing import pick_excerpt, top_entity_names

    meta = payload.get("corpus", {})
    changed = False
    for key in SYNCED_FIELDS:
        if key in meta and getattr(corpus, key) != meta[key]:
            setattr(corpus, key, meta[key])
            changed = True
    documents = payload.get("documents", [])
    texts = [documents[d]["text"][s:e] for d, _p, s, e in payload.get("chunks", [])[:12]]
    excerpt = pick_excerpt(texts)
    if excerpt and corpus.excerpt != excerpt:
        corpus.excerpt = excerpt
        changed = True
    top = top_entity_names([(e[0], e[3], e[5]) for e in payload.get("entities", [])])
    if top != "[]" and corpus.highlights != top:
        corpus.highlights = top
        changed = True
    if changed:
        corpus.updated_at = datetime.now(UTC)
        session.add(corpus)
        session.commit()
    return changed


def import_seeds_in_background(
    engine: Engine, seed_dir: Path, on_replaced: Callable[[int], None] | None = None
) -> threading.Thread:
    """Import seeds on a daemon thread so the API answers immediately."""

    def run() -> None:
        try:
            imported = import_seed_directory(engine, seed_dir, on_replaced)
            if imported:
                log.info("seeded corpora: %s", ", ".join(imported))
        except Exception:  # noqa: BLE001
            log.exception("seed import failed")

    thread = threading.Thread(target=run, name="ecce-seed", daemon=True)
    thread.start()
    return thread
