"""Public corpus gallery, documents and chunk reader."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.deps import get_corpus, get_graphs
from app.core.database import get_session
from app.core.security import AdminPrincipal, optional_admin
from app.models.entities import Chunk, Corpus, Document, Entity, Mention
from app.models.schemas import (
    ChunkOut,
    ChunkPage,
    CorpusDetail,
    CorpusSummary,
    DocumentOut,
    EntityOut,
    MentionOut,
)
from app.services.graph import GraphRegistry

router = APIRouter(prefix="/corpora", tags=["corpora"])


@router.get("", response_model=list[CorpusSummary])
def list_corpora(
    session: Session = Depends(get_session),
    admin: AdminPrincipal | None = Depends(optional_admin),
    include_all: bool = Query(
        False, alias="all", description="Admins: include hidden/unprocessed corpora"
    ),
) -> list[Corpus]:
    """Gallery of ready, visible corpora (admins may list everything)."""
    query = select(Corpus).order_by(col(Corpus.created_at).desc())
    if admin is None or not include_all:
        query = query.where(Corpus.visible == True, Corpus.status == "ready")  # noqa: E712
    return list(session.exec(query).all())


@router.get("/{slug}", response_model=CorpusDetail)
def corpus_detail(
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    graphs: GraphRegistry = Depends(get_graphs),
) -> CorpusDetail:
    """Corpus metadata with entity type counts, page count and the strongest entities."""
    label_rows = session.exec(
        select(Entity.label, func.count())
        .where(Entity.corpus_id == corpus.id)
        .group_by(col(Entity.label))
    ).all()
    top = session.exec(
        select(Entity)
        .where(Entity.corpus_id == corpus.id)
        .order_by(col(Entity.strength).desc(), col(Entity.count).desc())
        .limit(12)
    ).all()
    detail = CorpusDetail.model_validate(corpus)
    detail.label_counts = {label: int(n) for label, n in sorted(label_rows, key=lambda r: -r[1])}
    detail.top_entities = [EntityOut.model_validate(e) for e in top]
    if corpus.status == "ready":
        graph = graphs.get(corpus.id)  # type: ignore[arg-type]
        detail.max_weight = graph.max_weight
        detail.max_strength = graph.max_strength
        detail.suggested_min_weight = graph.suggested_min_weight()
    return detail


@router.get("/{slug}/documents", response_model=list[DocumentOut])
def list_documents(
    corpus: Corpus = Depends(get_corpus), session: Session = Depends(get_session)
) -> list[DocumentOut]:
    """Documents (chapters/files) of a corpus."""
    rows = session.exec(
        select(  # type: ignore[call-overload]  # >4 columns
            col(Document.id),
            col(Document.position),
            col(Document.title),
            func.length(col(Document.text)),
            func.count(col(Chunk.id)),
            func.min(col(Chunk.page)),
        )
        .join(Chunk, col(Chunk.document_id) == col(Document.id), isouter=True)
        .where(Document.corpus_id == corpus.id)
        .group_by(col(Document.id))
        .order_by(col(Document.position))
    ).all()
    return [
        DocumentOut(
            id=i,
            position=p,
            title=t or f"Document {p + 1}",
            n_chars=int(n or 0),
            n_chunks=int(c or 0),
            first_page=int(fp or 0),
        )
        for i, p, t, n, c, fp in rows
    ]


def chunk_outputs(session: Session, chunks: list[Chunk]) -> list[ChunkOut]:
    """Attach mention spans and document titles to chunks."""
    if not chunks:
        return []
    ids = [c.id for c in chunks]
    mentions = session.exec(
        select(Mention.chunk_id, Mention.entity_id, Mention.start, Mention.end, Entity.label)  # type: ignore[call-overload]  # >4 columns
        .join(Entity, col(Entity.id) == col(Mention.entity_id))
        .where(col(Mention.chunk_id).in_(ids))
        .order_by(col(Mention.start))
    ).all()
    by_chunk: dict[int, list[MentionOut]] = {}
    for chunk_id, entity_id, start, end, label in mentions:
        by_chunk.setdefault(chunk_id, []).append(
            MentionOut(entity_id=entity_id, label=label, start=start, end=end)
        )
    doc_ids = {c.document_id for c in chunks}
    titles = dict(
        session.exec(
            select(col(Document.id), col(Document.title)).where(col(Document.id).in_(doc_ids))
        ).all()
    )
    return [
        ChunkOut(
            id=c.id,  # type: ignore[arg-type]
            document_id=c.document_id,
            document_title=titles.get(c.document_id, ""),
            position=c.position,
            page=c.page,
            text=c.text,
            mentions=by_chunk.get(c.id, []),  # type: ignore[arg-type]
        )
        for c in chunks
    ]


@router.get("/{slug}/chunks", response_model=ChunkPage)
def list_chunks(
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    document_id: int | None = Query(None),
    entity_id: list[int] | None = Query(
        None, description="Only chunks mentioning ALL of these entities"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> ChunkPage:
    """Paginated reader: chunks of a document and/or chunks mentioning given entities."""
    query = select(Chunk).where(Chunk.corpus_id == corpus.id)
    if document_id is not None:
        query = query.where(Chunk.document_id == document_id)
    for eid in entity_id or []:
        sub = select(Mention.chunk_id).where(Mention.entity_id == eid)
        query = query.where(col(Chunk.id).in_(sub))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    chunks = session.exec(
        query.order_by(col(Chunk.document_id), col(Chunk.position))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ChunkPage(
        items=chunk_outputs(session, list(chunks)), total=int(total), page=page, page_size=page_size
    )


@router.get("/{slug}/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(
    chunk_id: int, corpus: Corpus = Depends(get_corpus), session: Session = Depends(get_session)
) -> ChunkOut:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or chunk.corpus_id != corpus.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    return chunk_outputs(session, [chunk])[0]
