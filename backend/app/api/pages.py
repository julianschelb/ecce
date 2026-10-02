"""Reading pages, the page graph and the back-of-the-book index."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.corpora import chunk_outputs
from app.api.deps import get_corpus, get_ready_graph
from app.core.database import get_session
from app.models.entities import Chunk, Corpus, Document, Entity, Mention
from app.models.schemas import (
    EntityOut,
    GraphResponse,
    IndexEntry,
    IndexResponse,
    PageEntity,
    PageOut,
    PageRef,
    PageRefList,
)
from app.services.graph import GraphCache

router = APIRouter(prefix="/corpora/{slug}", tags=["pages"])


def _page_chunks(session: Session, corpus: Corpus, number: int) -> list[Chunk]:
    if number < 1 or number > corpus.n_pages:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Page {number} does not exist")
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.corpus_id == corpus.id, Chunk.page == number)
        .order_by(col(Chunk.position))
    ).all()
    if not chunks:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Page {number} does not exist")
    return list(chunks)


def _page_entity_ids(session: Session, corpus: Corpus, number: int) -> list[int]:
    rows = session.exec(
        select(col(Mention.entity_id))
        .join(Chunk, col(Chunk.id) == col(Mention.chunk_id))
        .where(Chunk.corpus_id == corpus.id, Chunk.page == number)
        .distinct()
    ).all()
    return [int(r) for r in rows]


@router.get("/pages/{number}", response_model=PageOut)
def get_page(
    number: int, corpus: Corpus = Depends(get_corpus), session: Session = Depends(get_session)
) -> PageOut:
    """One reading page with its passages and the entities mentioned on it."""
    chunks = _page_chunks(session, corpus, number)
    outputs = chunk_outputs(session, chunks)
    document = session.get(Document, chunks[0].document_id)
    counts: dict[int, int] = {}
    for chunk in outputs:
        for mention in chunk.mentions:
            counts[mention.entity_id] = counts.get(mention.entity_id, 0) + 1
    entities = (
        session.exec(select(Entity).where(col(Entity.id).in_(list(counts)))).all() if counts else []
    )
    page_entities = sorted(
        (
            PageEntity(**EntityOut.model_validate(e).model_dump(), page_mentions=counts[e.id])  # type: ignore[index]
            for e in entities
        ),
        key=lambda e: (-e.page_mentions, -e.strength, e.text),
    )
    return PageOut(
        number=number,
        n_pages=corpus.n_pages,
        document_id=chunks[0].document_id,
        document_title=outputs[0].document_title,
        document_position=document.position if document else 0,
        opens_document=chunks[0].position == 0,
        chunks=outputs,
        entities=page_entities,
    )


@router.get("/pages/{number}/graph", response_model=GraphResponse)
def get_page_graph(
    number: int,
    corpus: Corpus = Depends(get_corpus),
    graph: GraphCache = Depends(get_ready_graph),
    session: Session = Depends(get_session),
    max_nodes: int = Query(300, ge=1, le=2000),
) -> GraphResponse:
    """The network of the entities mentioned on a page (corpus-wide edge weights)."""
    if number < 1 or number > corpus.n_pages:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Page {number} does not exist")
    return GraphResponse(
        **graph.induced(_page_entity_ids(session, corpus, number), max_nodes=max_nodes)
    )


@router.get("/documents/{document_id}/graph", response_model=GraphResponse)
def get_document_graph(
    document_id: int,
    corpus: Corpus = Depends(get_corpus),
    graph: GraphCache = Depends(get_ready_graph),
    session: Session = Depends(get_session),
    max_nodes: int = Query(150, ge=1, le=2000),
) -> GraphResponse:
    """The network of the entities mentioned in one chapter (corpus-wide edge weights)."""
    document = session.get(Document, document_id)
    if document is None or document.corpus_id != corpus.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Document {document_id} does not exist")
    rows = session.exec(
        select(col(Mention.entity_id)).where(Mention.document_id == document_id).distinct()
    ).all()
    return GraphResponse(**graph.induced([int(r) for r in rows], max_nodes=max_nodes))


@router.get("/pages", response_model=PageRefList)
def list_pages(
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    entity_id: list[int] | None = Query(
        None, description="Only pages with passages mentioning ALL of these entities"
    ),
    document_id: int | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> PageRefList:
    """Pages matching a selection in the graph: where an entity, or a pair, is mentioned."""
    query = select(  # type: ignore[call-overload]  # >4 columns
        col(Chunk.page), col(Chunk.document_id), col(Document.title), func.count()
    ).join(Document, col(Document.id) == col(Chunk.document_id))
    query = query.where(Chunk.corpus_id == corpus.id, col(Chunk.page) > 0)
    if document_id is not None:
        query = query.where(Chunk.document_id == document_id)
    for eid in entity_id or []:
        sub = select(Mention.chunk_id).where(Mention.entity_id == eid)
        query = query.where(col(Chunk.id).in_(sub))
    query = query.group_by(col(Chunk.page), col(Chunk.document_id), col(Document.title))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(query.order_by(col(Chunk.page)).offset(offset).limit(limit)).all()
    return PageRefList(
        items=[
            PageRef(number=int(page), document_id=int(doc), document_title=title, hits=int(n))
            for page, doc, title, n in rows
        ],
        total=int(total),
    )


@router.get("/index", response_model=IndexResponse)
def get_index(
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    q: str = Query("", max_length=200),
    label: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
) -> IndexResponse:
    """Every mentioned entity with the pages it appears on, most mentioned first."""
    query = select(Entity).where(Entity.corpus_id == corpus.id)
    if q.strip():
        query = query.where(col(Entity.norm).contains(q.strip().lower()))
    if label:
        query = query.where(Entity.label == label)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    entities = session.exec(
        query.order_by(
            col(Entity.count).desc(), col(Entity.strength).desc(), col(Entity.text)
        ).limit(limit)
    ).all()
    pages: dict[int, list[int]] = {}
    if entities:
        rows = session.exec(
            select(col(Mention.entity_id), col(Chunk.page))
            .join(Chunk, col(Chunk.id) == col(Mention.chunk_id))
            .where(Mention.corpus_id == corpus.id, col(Chunk.page) > 0)
            .group_by(col(Mention.entity_id), col(Chunk.page))
            .order_by(col(Mention.entity_id), col(Chunk.page))
        ).all()
        for entity_id, page in rows:
            pages.setdefault(int(entity_id), []).append(int(page))
    return IndexResponse(
        entries=[
            IndexEntry(entity=EntityOut.model_validate(e), pages=pages.get(e.id, []))  # type: ignore[arg-type]
            for e in entities
        ],
        total=int(total),
        n_pages=corpus.n_pages,
    )
