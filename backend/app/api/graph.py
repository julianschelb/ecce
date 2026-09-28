"""Graph queries: filtered network view, entity and edge details."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.corpora import chunk_outputs
from app.api.deps import get_corpus, get_ready_graph
from app.core.database import get_session
from app.models.entities import Chunk, Corpus, Entity, Mention
from app.models.schemas import EdgeDetail, EntityDetail, EntityOut, GraphResponse, NeighborOut
from app.services.graph import GraphCache

router = APIRouter(prefix="/corpora/{slug}", tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    graph: GraphCache = Depends(get_ready_graph),
    min_weight: float = Query(0.0, ge=0.0, description="Drop edges lighter than this"),
    max_nodes: int = Query(120, ge=1, le=2000, description="Keep the strongest N entities"),
    labels: list[str] | None = Query(None, description="Entity types to include"),
    focus: int | None = Query(None, description="Entity id: return its ego network"),
) -> GraphResponse:
    """Filtered entity network for the interactive canvas."""
    return GraphResponse(
        **graph.subgraph(
            min_weight=min_weight,
            max_nodes=max_nodes,
            labels=set(labels) if labels else None,
            focus=focus,
        )
    )


@router.get("/entities", response_model=list[EntityOut])
def search_entities(
    corpus: Corpus = Depends(get_corpus),
    session: Session = Depends(get_session),
    q: str = Query("", max_length=200),
    label: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
) -> list[Entity]:
    """Entity lookup by (partial) name, strongest first."""
    query = select(Entity).where(Entity.corpus_id == corpus.id)
    if q.strip():
        query = query.where(col(Entity.norm).contains(q.strip().lower()))
    if label:
        query = query.where(Entity.label == label)
    return list(
        session.exec(
            query.order_by(col(Entity.strength).desc(), col(Entity.count).desc()).limit(limit)
        ).all()
    )


@router.get("/entities/{entity_id}", response_model=EntityDetail)
def entity_detail(
    entity_id: int,
    corpus: Corpus = Depends(get_corpus),
    graph: GraphCache = Depends(get_ready_graph),
    session: Session = Depends(get_session),
    k: int = Query(25, ge=1, le=200),
) -> EntityDetail:
    """An entity with its strongest neighbours and the number of chunks mentioning it."""
    entity = session.get(Entity, entity_id)
    if entity is None or entity.corpus_id != corpus.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    n_chunks = session.exec(
        select(func.count(func.distinct(Mention.chunk_id))).where(Mention.entity_id == entity_id)
    ).one()
    neighbors = [
        NeighborOut(entity=EntityOut(**n["entity"]), weight=n["weight"], count=n["count"])
        for n in graph.neighbors(entity_id, k=k)
    ]
    return EntityDetail(
        **EntityOut.model_validate(entity).model_dump(), n_chunks=int(n_chunks), neighbors=neighbors
    )


@router.get("/edges/{source_id}/{target_id}", response_model=EdgeDetail)
def edge_detail(
    source_id: int,
    target_id: int,
    corpus: Corpus = Depends(get_corpus),
    graph: GraphCache = Depends(get_ready_graph),
    session: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
) -> EdgeDetail:
    """Edge weight/count and the chunks where both entities are mentioned (provenance)."""
    source, target = session.get(Entity, source_id), session.get(Entity, target_id)
    if (
        source is None
        or target is None
        or source.corpus_id != corpus.id
        or target.corpus_id != corpus.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    edge = graph.edge(source_id, target_id)
    if edge is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "These entities are not connected")
    weight, count = edge
    a = select(Mention.chunk_id).where(Mention.entity_id == source_id)
    b = select(Mention.chunk_id).where(Mention.entity_id == target_id)
    chunks = session.exec(
        select(Chunk)
        .where(col(Chunk.id).in_(a), col(Chunk.id).in_(b))
        .order_by(col(Chunk.document_id), col(Chunk.position))
        .limit(limit)
    ).all()
    return EdgeDetail(
        source=EntityOut.model_validate(source),
        target=EntityOut.model_validate(target),
        weight=weight,
        count=count,
        chunks=chunk_outputs(session, list(chunks)),
    )
