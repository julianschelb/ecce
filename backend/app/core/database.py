"""SQLite engine, session dependency and schema initialisation (incl. FTS5)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

log = logging.getLogger(__name__)

FTS_STATEMENTS = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
        text, content='chunk', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
    )""",
    """CREATE TRIGGER IF NOT EXISTS chunk_fts_ai AFTER INSERT ON chunk BEGIN
        INSERT INTO chunk_fts(rowid, text) VALUES (new.id, new.text);
    END""",
    """CREATE TRIGGER IF NOT EXISTS chunk_fts_ad AFTER DELETE ON chunk BEGIN
        INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.id, old.text);
    END""",
    """CREATE TRIGGER IF NOT EXISTS chunk_fts_au AFTER UPDATE ON chunk BEGIN
        INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.id, old.text);
        INSERT INTO chunk_fts(rowid, text) VALUES (new.id, new.text);
    END""",
]


def create_db_engine(url: str) -> Engine:
    """Create a SQLite engine tuned for a single-process web app."""
    kwargs: dict = {"connect_args": {"check_same_thread": False, "timeout": 30}}
    if url.endswith(":memory:") or url == "sqlite://":
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def init_db(engine: Engine) -> bool:
    """Create tables and the full-text index. Returns whether FTS5 is available."""
    from app.models import entities  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            for statement in FTS_STATEMENTS:
                connection.execute(text(statement))
        return True
    except Exception as error:  # pragma: no cover - depends on the sqlite build
        log.warning("FTS5 unavailable, falling back to LIKE search: %s", error)
        return False


def get_session(request: Request) -> Iterator[Session]:
    """Per-request session bound to the app's engine."""
    with Session(request.app.state.engine) as session:
        yield session
