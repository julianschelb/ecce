"""Background processing jobs with status reporting."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from implicit_word_network.extraction import BaseEntityExtractor
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import Settings
from app.models.entities import Corpus, Job
from app.services.extraction import create_extractor, resolve_extractor_name
from app.services.graph import GraphRegistry
from app.services.processing import process_corpus

log = logging.getLogger(__name__)


class JobRunner:
    """Runs corpus processing on a single worker thread and records progress in the DB."""

    def __init__(self, engine: Engine, settings: Settings, graphs: GraphRegistry) -> None:
        self._engine = engine
        self._settings = settings
        self._graphs = graphs
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ecce-job")
        self._extractor_lock = threading.Lock()
        self._extractor: BaseEntityExtractor | None = None
        self._extractor_name = ""

    # ---------- extractor (loaded once, shared by all jobs)

    def extractor(self) -> BaseEntityExtractor:
        with self._extractor_lock:
            if self._extractor is None:
                self._extractor_name = resolve_extractor_name(self._settings)
                self._extractor = create_extractor(self._settings, self._extractor_name)
            return self._extractor

    @property
    def extractor_name(self) -> str:
        if not self._extractor_name:
            self._extractor_name = resolve_extractor_name(self._settings)
        return self._extractor_name

    # ---------- public API

    def submit(self, corpus_id: int) -> Job:
        """Queue processing of a corpus; runs inline when ``JOBS_SYNC`` is set."""
        with Session(self._engine) as session:
            corpus = session.get(Corpus, corpus_id)
            if corpus is None:
                raise ValueError(f"Unknown corpus id {corpus_id}")
            corpus.status = "queued"
            corpus.updated_at = datetime.now(UTC)
            job = Job(corpus_id=corpus_id, status="queued", message="queued")
            session.add(corpus)
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id
        assert job_id is not None
        if self._settings.jobs_sync:
            self._run(job_id)
        else:
            self._executor.submit(self._run, job_id)
        with Session(self._engine) as session:
            return session.get(Job, job_id)  # type: ignore[return-value]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ---------- worker

    def _update(self, job_id: int, **fields) -> None:
        with Session(self._engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(UTC)
            session.add(job)
            session.commit()

    def _run(self, job_id: int) -> None:
        with Session(self._engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            corpus = session.get(Corpus, job.corpus_id)
            if corpus is None:
                self._update(job_id, status="failed", error="corpus vanished")
                return
            corpus_id = corpus.id
        self._update(job_id, status="running", progress=0.0, message="loading extractor")
        try:
            extractor = self.extractor()
            with Session(self._engine) as session:
                corpus = session.get(Corpus, corpus_id)
                assert corpus is not None
                corpus.status = "processing"
                session.add(corpus)
                session.commit()
                process_corpus(
                    session,
                    corpus,
                    extractor,
                    self._settings,
                    extractor_name=self.extractor_name,
                    progress=lambda p, m: self._update(job_id, progress=p, message=m),
                )
            self._graphs.invalidate(corpus_id)
            self._update(job_id, status="done", progress=1.0, message="ready")
        except Exception as error:  # noqa: BLE001
            log.exception("processing job %s failed", job_id)
            with Session(self._engine) as session:
                corpus = session.get(Corpus, corpus_id)
                if corpus is not None:
                    corpus.status = "failed"
                    corpus.error = str(error)[:2000]
                    corpus.updated_at = datetime.now(UTC)
                    session.add(corpus)
                    session.commit()
            self._update(job_id, status="failed", error=str(error)[:2000], message="failed")
