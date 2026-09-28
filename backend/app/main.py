"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine

from app import __version__
from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.database import create_db_engine, init_db
from app.core.logging import configure_logging
from app.core.security import LoginRateLimiter
from app.models.schemas import HealthOut
from app.services.graph import GraphRegistry
from app.services.jobs import JobRunner
from app.services.seed import import_seed_directory

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    """Build the application (tests pass their own settings/engine)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = engine or create_db_engine(settings.resolved_database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.fts = init_db(engine)
        if settings.seed_on_startup:
            imported = import_seed_directory(engine, settings.seed_dir)
            if imported:
                log.info("seeded corpora: %s", ", ".join(imported))
        yield
        app.state.jobs.shutdown()

    app = FastAPI(
        title="ECCE API",
        version=__version__,
        description="Explore text corpora as implicit entity networks.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.graphs = GraphRegistry(engine)
    app.state.jobs = JobRunner(engine, settings, app.state.graphs)
    app.state.login_limiter = LoginRateLimiter(settings.login_attempts_per_minute)
    app.state.fts = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/api/health", response_model=HealthOut, tags=["meta"])
    def health() -> HealthOut:
        return HealthOut(
            status="ok",
            version=__version__,
            extractor=app.state.jobs.extractor_name,
            admin_enabled=settings.admin_enabled,
            fts=bool(app.state.fts),
        )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    mount_frontend(app, settings.frontend_dist)
    return app


def mount_frontend(app: FastAPI, dist: Path | None) -> None:
    """Serve a built single-page app (if present) with history-API fallback."""
    if dist is None or not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
