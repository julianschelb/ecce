"""Password-protected administration: create, upload, process, hide, delete corpora; jobs."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, col, select

from app.api.deps import get_graphs, get_jobs
from app.core.config import Settings
from app.core.database import get_session
from app.core.security import AdminPrincipal, require_admin, settings_dependency
from app.models.entities import Corpus, Document, Job
from app.models.schemas import CorpusCreate, CorpusSummary, CorpusUpdate, JobOut
from app.services.chunking import slugify, split_documents
from app.services.graph import GraphRegistry
from app.services.jobs import JobRunner

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def unique_slug(session: Session, title: str) -> str:
    base = slugify(title)
    slug, n = base, 2
    while session.exec(select(Corpus).where(Corpus.slug == slug)).first() is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _job_out(session: Session, job: Job) -> JobOut:
    corpus = session.get(Corpus, job.corpus_id)
    out = JobOut.model_validate(job)
    out.corpus_slug = corpus.slug if corpus else ""
    return out


def _admin_corpus(session: Session, slug: str) -> Corpus:
    corpus = session.exec(select(Corpus).where(Corpus.slug == slug)).first()
    if corpus is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Corpus {slug!r} not found")
    return corpus


@router.post("/corpora", response_model=CorpusSummary, status_code=status.HTTP_201_CREATED)
def create_corpus(
    body: CorpusCreate,
    session: Session = Depends(get_session),
    jobs: JobRunner = Depends(get_jobs),
    settings: Settings = Depends(settings_dependency),
) -> Corpus:
    """Create a corpus from pasted text (optionally split at headings) and queue processing."""
    parts = split_documents(body.text, body.split, default_title=body.title)
    if not parts:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The text is empty")
    corpus = Corpus(
        slug=unique_slug(session, body.title),
        title=body.title,
        author=body.author,
        year=body.year,
        description=body.description,
        genre=body.genre,
        source=body.source,
        language=body.language,
        visible=body.visible,
        window=body.window if body.window is not None else settings.window,
        status="empty",
    )
    session.add(corpus)
    session.flush()
    session.add_all(
        Document(corpus_id=corpus.id, position=i, title=p.title, text=p.text)
        for i, p in enumerate(parts)
    )  # type: ignore[arg-type]
    corpus.n_documents = len(parts)
    session.commit()
    session.refresh(corpus)
    if body.process:
        jobs.submit(corpus.id)  # type: ignore[arg-type]
        session.refresh(corpus)
    return corpus


@router.post("/corpora/upload", response_model=CorpusSummary, status_code=status.HTTP_201_CREATED)
async def upload_corpus(
    files: list[UploadFile] = File(
        ..., description="Plain text or Markdown files, one document each"
    ),
    title: str = Form(..., min_length=1, max_length=200),
    author: str = Form(""),
    year: int | None = Form(None),
    description: str = Form(""),
    genre: str = Form(""),
    source: str = Form(""),
    language: str = Form("en"),
    visible: bool = Form(True),
    process: bool = Form(True),
    session: Session = Depends(get_session),
    jobs: JobRunner = Depends(get_jobs),
    settings: Settings = Depends(settings_dependency),
) -> Corpus:
    """Create a corpus from uploaded ``.txt`` / ``.md`` files (batch) and queue processing."""
    limit = settings.max_upload_mb * 1024 * 1024
    documents: list[tuple[str, str]] = []
    for upload in files:
        raw = await upload.read()
        if len(raw) > limit:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"{upload.filename} exceeds {settings.max_upload_mb} MB",
            )
        try:
            text_ = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_ = raw.decode("latin-1")
        text_ = text_.strip()
        if text_:
            name = (upload.filename or "document").rsplit(".", 1)[0]
            documents.append((name, text_))
    if not documents:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No non-empty text files were uploaded"
        )
    corpus = Corpus(
        slug=unique_slug(session, title),
        title=title,
        author=author,
        year=year,
        description=description,
        genre=genre,
        source=source,
        language=language,
        visible=visible,
        window=settings.window,
        status="empty",
    )
    session.add(corpus)
    session.flush()
    session.add_all(
        Document(corpus_id=corpus.id, position=i, title=t, text=x)
        for i, (t, x) in enumerate(documents)
    )  # type: ignore[arg-type]
    corpus.n_documents = len(documents)
    session.commit()
    session.refresh(corpus)
    if process:
        jobs.submit(corpus.id)  # type: ignore[arg-type]
        session.refresh(corpus)
    return corpus


@router.post("/corpora/{slug}/process", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def process(
    slug: str, session: Session = Depends(get_session), jobs: JobRunner = Depends(get_jobs)
) -> JobOut:
    """(Re)run chunking, entity extraction and graph construction in the background."""
    corpus = _admin_corpus(session, slug)
    if corpus.status in ("queued", "processing"):
        raise HTTPException(status.HTTP_409_CONFLICT, "A processing job is already running")
    job = jobs.submit(corpus.id)  # type: ignore[arg-type]
    return _job_out(session, job)


@router.patch("/corpora/{slug}", response_model=CorpusSummary)
def update_corpus(slug: str, body: CorpusUpdate, session: Session = Depends(get_session)) -> Corpus:
    """Edit metadata or hide/show a corpus in the gallery."""
    corpus = _admin_corpus(session, slug)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(corpus, key, value)
    corpus.updated_at = datetime.now(UTC)
    session.add(corpus)
    session.commit()
    session.refresh(corpus)
    return corpus


@router.delete("/corpora/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_corpus(
    slug: str, session: Session = Depends(get_session), graphs: GraphRegistry = Depends(get_graphs)
) -> None:
    """Delete a corpus with all its documents, entities and edges."""
    corpus = _admin_corpus(session, slug)
    corpus_id = corpus.id
    session.delete(corpus)
    session.commit()
    graphs.invalidate(corpus_id)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(session: Session = Depends(get_session), limit: int = 50) -> list[JobOut]:
    jobs = session.exec(select(Job).order_by(col(Job.created_at).desc()).limit(limit)).all()
    return [_job_out(session, j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _job_out(session, job)


@router.get("/extractors")
def extractors(
    jobs: JobRunner = Depends(get_jobs), principal: AdminPrincipal = Depends(require_admin)
) -> dict:
    from app.services.extraction import available_extractors

    return {"active": jobs.extractor_name, "available": available_extractors()}
