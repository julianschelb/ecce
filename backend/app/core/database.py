"""SQLite engine, session dependency and schema initialisation (incl. FTS5)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

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
    # (re)created so that page assignments do not re-index the text
    "DROP TRIGGER IF EXISTS chunk_fts_au",
    """CREATE TRIGGER IF NOT EXISTS chunk_fts_au AFTER UPDATE OF text ON chunk BEGIN
        INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.id, old.text);
        INSERT INTO chunk_fts(rowid, text) VALUES (new.id, new.text);
    END""",
]

# indexes on columns added by ``migrate_columns`` (``create_all`` only indexes new tables)
INDEX_STATEMENTS = ["CREATE INDEX IF NOT EXISTS ix_chunk_page ON chunk (page)"]


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


def migrate_columns(engine: Engine) -> list[str]:
    """Add columns that exist in the models but not yet in the database (additive migrations).

    SQLite supports ``ALTER TABLE ... ADD COLUMN``; new columns get the model
    default so older databases (e.g. on a persistent volume) keep working
    after an upgrade.
    """
    added: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                type_ = column.type.compile(dialect=engine.dialect)
                raw_default = getattr(column.default, "arg", None)
                default = (
                    raw_default if raw_default is not None and not callable(raw_default) else None
                )
                clause = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {type_}'
                if default is not None:
                    literal = (
                        f"'{default}'"
                        if isinstance(default, str)
                        else ("1" if default is True else "0" if default is False else str(default))
                    )
                    clause += f" DEFAULT {literal}"
                connection.execute(text(clause))
                added.append(f"{table.name}.{column.name}")
    if added:
        log.info("added columns: %s", ", ".join(added))
    return added


def backfill_excerpts(engine: Engine) -> int:
    """Fill ``corpus.excerpt`` for corpora processed before the column existed."""
    from app.services.processing import pick_excerpt

    with engine.begin() as connection:
        ids = [
            row[0]
            for row in connection.execute(
                text("SELECT id FROM corpus WHERE excerpt IS NULL OR excerpt = ''")
            ).all()
        ]
        for corpus_id in ids:
            texts = [
                row[0]
                for row in connection.execute(
                    text("SELECT text FROM chunk WHERE corpus_id = :i ORDER BY id LIMIT 12"),
                    {"i": corpus_id},
                ).all()
            ]
            if texts:
                connection.execute(
                    text("UPDATE corpus SET excerpt = :e WHERE id = :i"),
                    {"e": pick_excerpt(texts), "i": corpus_id},
                )
    return len(ids)


def backfill_pages(engine: Engine) -> int:
    """Assign reading pages to processed corpora that predate the page column."""
    from app.models.entities import Corpus
    from app.services.pagination import paginate_corpus

    with Session(engine) as session:
        corpora = session.exec(
            select(Corpus).where(Corpus.status == "ready", Corpus.n_pages == 0)
        ).all()
        for corpus in corpora:
            if paginate_corpus(session, corpus):
                log.info("paginated corpus %s: %d pages", corpus.slug, corpus.n_pages)
        session.commit()
    return len(corpora)


def init_db(engine: Engine) -> bool:
    """Create tables, apply additive migrations and the full-text index. Returns whether FTS5 is available."""
    from app.models import entities  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    migrate_columns(engine)
    with engine.begin() as connection:
        for statement in INDEX_STATEMENTS:
            connection.execute(text(statement))
    backfill_excerpts(engine)
    backfill_pages(engine)
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
