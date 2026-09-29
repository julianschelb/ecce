"""API router aggregation."""

from fastapi import APIRouter

from app.api import admin, auth, contact, corpora, graph, pages, search

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(corpora.router)
api_router.include_router(graph.router)
api_router.include_router(pages.router)
api_router.include_router(search.router)
api_router.include_router(admin.router)
api_router.include_router(contact.router)
api_router.include_router(contact.admin_router)
