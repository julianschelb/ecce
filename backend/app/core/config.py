"""Application settings (environment variables, ``.env``)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be set through an environment variable of the same name
    (upper-case), e.g. ``ADMIN_PASSWORD``, ``DATABASE_URL``, ``EXTRACTOR``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "ECCE"
    environment: str = "development"
    log_level: str = "INFO"

    # storage
    data_dir: Path = Path("data")
    database_url: str | None = None  # defaults to sqlite:///<data_dir>/ecce.db

    # admin access
    admin_password: str | None = None
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    token_ttl_minutes: int = 12 * 60
    login_attempts_per_minute: int = 10

    # web
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    frontend_dist: Path | None = None  # serve a built SPA from this directory
    max_upload_mb: int = 25

    # processing
    extractor: str = "auto"  # auto | rule | spacy | gliner
    spacy_model: str = "en_core_web_sm"
    spacy_labels: list[str] = [
        "PERSON",
        "ORG",
        "GPE",
        "LOC",
        "NORP",
        "FAC",
        "EVENT",
        "WORK_OF_ART",
        "PRODUCT",
    ]
    gliner_model: str = "gliner-community/gliner_small-v2.5"
    gliner_labels: list[str] = ["person", "organization", "location", "event", "work of art"]
    window: int = 2
    max_chunk_words: int = 180
    jobs_sync: bool = False  # run processing jobs inline (tests / CLI)
    seed_on_startup: bool = True

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ecce.db').as_posix()}"

    @property
    def seed_dir(self) -> Path:
        return self.data_dir / "seed"

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (cleared in tests)."""
    return Settings()
