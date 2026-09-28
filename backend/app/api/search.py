"""Full-text search over chunks, cross-referenced with entities."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlmodel import Session, col, select

from app.api.corpora import chunk_outputs
from app.api.deps import get_corpus
from app.core.database import get_session
from app.models.entities import Chunk, Corpus, Mention
from app.models.schemas import SearchHit, SearchResponse

router = APIRouter(prefix="/corpora/{slug}", tags=["search"])

_TOKEN = re.compile(r"[\w'’-]+", re.UNICODE)


def fts_query(raw: str) -> str:
    """Turn free text into a safe FTS5 query: quoted terms, prefix match on the last one."""
    terms = [t.replace('"', "") for t in _TOKEN.findall(raw)]
    terms = [t for t in terms if t]
    if not terms:
        return ""
    quoted = [f'"{t}"' for t in terms[:-1]] + [f'"{terms[-1]}"*']
    return " ".join(quoted)


def _highlight(text_: str, terms: list[str], width: int = 220) -> str:
    """LIKE fallback: crude snippet with <mark> tags around the first term hit."""
    lowered = text_.lower()
    pos = min((lowered.find(t.lower()) for t in terms if lowered.find(t.lower()) >= 0), default=0)
    start = max(0, pos - width // 3)
    snippet = text_[start : start + width]
    for term in terms:
        snippet = re.sub(
            re.escape(term), lambda m: f"<mark>{m.group(0)}</mark>", snippet, flags=re.I
        )
    return ("…" if start > 0 else "") + snippet + ("…" if start + width < len(text_) else "")


@router.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    q: str = Query(..., min_length=1, max_length=200),
    entity_id: list[int] | None = Query(
        None, description="Only chunks that also mention these entities"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SearchResponse:
    """Keyword search over chunks (FTS5 with BM25 ranking and snippets; LIKE fallback)."""
    terms = _TOKEN.findall(q)
    if not terms:
        return SearchResponse(query=q, hits=[], total=0)
    params: dict = {"cid": corpus.id, "limit": limit, "offset": offset}
    scope = "SELECT id FROM chunk WHERE corpus_id = :cid"
    for i, eid in enumerate(entity_id or []):
        scope += f" AND id IN (SELECT chunk_id FROM mention WHERE entity_id = :e{i})"
        params[f"e{i}"] = eid

    if getattr(request.app.state, "fts", False):
        params["q"] = fts_query(q)
        connection = session.connection()
        total = int(
            connection.execute(
                text(
                    f"SELECT COUNT(*) FROM chunk_fts WHERE chunk_fts MATCH :q AND rowid IN ({scope})"
                ),
                params,
            ).scalar_one()
        )
        rows = connection.execute(
            text(
                "SELECT rowid, snippet(chunk_fts, 0, '<mark>', '</mark>', '…', 28), bm25(chunk_fts) "
                f"FROM chunk_fts WHERE chunk_fts MATCH :q AND rowid IN ({scope}) "
                "ORDER BY bm25(chunk_fts) LIMIT :limit OFFSET :offset"
            ),
            params,
        ).all()
        ids = [int(r[0]) for r in rows]
        snippets = {int(r[0]): (str(r[1]), -float(r[2])) for r in rows}
    else:  # pragma: no cover - only without FTS5
        query = select(Chunk).where(Chunk.corpus_id == corpus.id)
        for term in terms:
            query = query.where(col(Chunk.text).icontains(term))
        for eid in entity_id or []:
            query = query.where(
                col(Chunk.id).in_(select(Mention.chunk_id).where(Mention.entity_id == eid))
            )
        matches = session.exec(query.order_by(col(Chunk.document_id), col(Chunk.position))).all()
        total = len(matches)
        page = list(matches[offset : offset + limit])
        ids = [c.id for c in page]  # type: ignore[misc]
        snippets = {c.id: (_highlight(c.text, terms), 1.0) for c in page}  # type: ignore[misc]

    chunks = session.exec(select(Chunk).where(col(Chunk.id).in_(ids))).all() if ids else []
    by_id = {c.id: c for c in chunks}
    ordered = [by_id[i] for i in ids if i in by_id]
    outputs = chunk_outputs(session, ordered)
    hits = [
        SearchHit(chunk=out, snippet=snippets[out.id][0], score=snippets[out.id][1])
        for out in outputs
    ]
    return SearchResponse(query=q, hits=hits, total=total)
