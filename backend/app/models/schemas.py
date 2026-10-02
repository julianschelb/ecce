"""API schemas (Pydantic v2)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------- auth


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class Principal(BaseModel):
    subject: str
    role: str


# ---------------------------------------------------------------- corpora


class CorpusSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    author: str = ""
    year: int | None = None
    description: str = ""
    genre: str = ""
    source: str = ""
    source_url: str = ""
    license: str = ""
    license_url: str = ""
    rights: str = ""
    language: str = "en"
    excerpt: str = ""
    highlights: list[str] = []
    status: str
    visible: bool
    window: int
    extractor: str = ""
    error: str | None = None
    n_documents: int
    n_chunks: int
    n_entities: int
    n_edges: int
    n_mentions: int
    n_pages: int = 0
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None

    @field_validator("highlights", mode="before")
    @classmethod
    def _parse_highlights(cls, value: object) -> list[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value) if value else []
            except ValueError:
                parsed = []
            return [str(v) for v in parsed]
        return list(value) if isinstance(value, list | tuple) else []


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    label: str
    count: int
    degree: int
    strength: float


class CorpusDetail(CorpusSummary):
    label_counts: dict[str, int] = {}
    top_entities: list[EntityOut] = []
    max_weight: float = 0.0
    max_strength: float = 0.0
    suggested_min_weight: float = 0.0  # default edge filter of the graph view


class DocumentOut(BaseModel):
    id: int
    position: int
    title: str
    n_chunks: int
    n_chars: int
    first_page: int = 0


class MentionOut(BaseModel):
    entity_id: int
    label: str
    start: int
    end: int


class ChunkOut(BaseModel):
    id: int
    document_id: int
    document_title: str
    position: int
    page: int = 0
    text: str
    mentions: list[MentionOut] = []


class ChunkPage(BaseModel):
    items: list[ChunkOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------- pages


class PageEntity(EntityOut):
    page_mentions: int


class PageOut(BaseModel):
    """One reading page: its chunks in order and the entities mentioned on it."""

    number: int
    n_pages: int
    document_id: int
    document_title: str
    document_position: int
    opens_document: bool  # the page starts a document (chapter)
    chunks: list[ChunkOut]
    entities: list[PageEntity]


class PageRef(BaseModel):
    number: int
    document_id: int
    document_title: str
    hits: int  # matching passages on the page


class PageRefList(BaseModel):
    items: list[PageRef]
    total: int


class IndexEntry(BaseModel):
    entity: EntityOut
    pages: list[int]


class IndexResponse(BaseModel):
    """Back-of-the-book index: every entity with the pages that mention it."""

    entries: list[IndexEntry]
    total: int
    n_pages: int


# ---------------------------------------------------------------- graph


class GraphNode(BaseModel):
    id: int
    text: str
    label: str
    count: int
    degree: int
    strength: float


class GraphEdge(BaseModel):
    source: int
    target: int
    weight: float
    count: int


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int
    min_weight: float
    max_weight: float
    max_strength: float


class NeighborOut(BaseModel):
    entity: EntityOut
    weight: float
    count: int


class EntityDetail(EntityOut):
    n_chunks: int
    neighbors: list[NeighborOut]


class EdgeDetail(BaseModel):
    source: EntityOut
    target: EntityOut
    weight: float
    count: int
    chunks: list[ChunkOut]


# ---------------------------------------------------------------- search


class SearchHit(BaseModel):
    chunk: ChunkOut
    snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    total: int


# ---------------------------------------------------------------- admin


class CorpusCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    author: str = Field(default="", max_length=200)
    year: int | None = Field(default=None, ge=-3000, le=2100)
    description: str = Field(default="", max_length=2000)
    genre: str = Field(default="", max_length=100)
    source: str = Field(default="", max_length=300)
    language: str = Field(default="en", max_length=10)
    split: Literal["auto", "headings", "none"] = "auto"
    visible: bool = True
    process: bool = True
    window: int | None = Field(default=None, ge=0, le=10)


class CorpusUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=-3000, le=2100)
    description: str | None = Field(default=None, max_length=2000)
    genre: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=500)
    license: str | None = Field(default=None, max_length=100)
    license_url: str | None = Field(default=None, max_length=500)
    rights: str | None = Field(default=None, max_length=4000)
    visible: bool | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corpus_id: int
    corpus_slug: str = ""
    kind: str
    status: str
    progress: float
    message: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class HealthOut(BaseModel):
    status: str
    version: str
    extractor: str
    admin_enabled: bool
    fts: bool


# ---------------------------------------------------------------- contact form


class ContactCreate(BaseModel):
    name: str = Field("", max_length=120)
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    message: str = Field(min_length=10, max_length=5000)
    website: str = ""  # honeypot: left empty by people, filled in by spam bots


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    message: str
    handled: bool
    created_at: datetime


class ContactUpdate(BaseModel):
    handled: bool
