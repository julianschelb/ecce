"""Database tables (SQLModel)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Corpus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    title: str
    author: str = ""
    year: int | None = None
    description: str = ""
    genre: str = ""
    source: str = ""
    language: str = "en"
    excerpt: str = ""  # opening lines, shown in the gallery
    highlights: str = ""  # JSON list of the most connected entity names
    status: str = Field(default="empty", index=True)  # empty|queued|processing|ready|failed
    visible: bool = Field(default=True, index=True)
    window: int = 2
    extractor: str = ""
    error: str | None = None
    n_documents: int = 0
    n_chunks: int = 0
    n_entities: int = 0
    n_edges: int = 0
    n_mentions: int = 0
    n_pages: int = 0  # reading pages (see services.pagination)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    processed_at: datetime | None = None
    seed_revision: int = 0  # revision of the bundled seed this corpus was imported from


class Document(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    position: int = 0
    title: str = ""
    text: str


class Chunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    document_id: int = Field(foreign_key="document.id", index=True, ondelete="CASCADE")
    position: int = 0  # position inside the document
    start: int = 0  # character offsets inside the document text
    end: int = 0
    page: int = Field(  # 1-based reading page inside the corpus
        default=0, index=True, sa_column_kwargs={"server_default": "0"}
    )
    text: str


class Entity(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    text: str
    norm: str = Field(index=True)
    label: str = Field(index=True)
    count: int = 0  # mentions
    degree: int = 0  # number of neighbours
    strength: float = 0.0  # sum of incident edge weights


class Mention(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    entity_id: int = Field(foreign_key="entity.id", index=True, ondelete="CASCADE")
    document_id: int = Field(foreign_key="document.id", index=True, ondelete="CASCADE")
    chunk_id: int = Field(foreign_key="chunk.id", index=True, ondelete="CASCADE")
    start: int = 0  # character offsets inside the chunk text
    end: int = 0
    score: float = 1.0


class Edge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    source_id: int = Field(foreign_key="entity.id", index=True, ondelete="CASCADE")
    target_id: int = Field(foreign_key="entity.id", index=True, ondelete="CASCADE")
    weight: float = 0.0
    count: int = 0


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    kind: str = "process"
    status: str = Field(default="queued", index=True)  # queued|running|done|failed
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
