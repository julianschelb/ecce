"""Shared dependencies for routers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import AdminPrincipal, optional_admin
from app.models.entities import Corpus
from app.services.graph import GraphCache, GraphRegistry
from app.services.jobs import JobRunner


def get_graphs(request: Request) -> GraphRegistry:
    return request.app.state.graphs


def get_jobs(request: Request) -> JobRunner:
    return request.app.state.jobs


def get_corpus(
    slug: str,
    session: Session = Depends(get_session),
    admin: AdminPrincipal | None = Depends(optional_admin),
) -> Corpus:
    """Resolve a corpus by slug; anonymous users only see visible, ready corpora."""
    corpus = session.exec(select(Corpus).where(Corpus.slug == slug)).first()
    if corpus is None or (admin is None and not (corpus.visible and corpus.status == "ready")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Corpus {slug!r} not found")
    return corpus


def get_ready_graph(
    corpus: Corpus = Depends(get_corpus), graphs: GraphRegistry = Depends(get_graphs)
) -> GraphCache:
    if corpus.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Corpus {corpus.slug!r} is not processed yet"
        )
    return graphs.get(corpus.id)  # type: ignore[arg-type]
