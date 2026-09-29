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

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, populate_by_name=True
    )

    app_name: str = "ECCE"
    environment: str = "development"
    log_level: str = "INFO"

    # storage
    data_dir: Path = Path("data")
    database_url: str | None = None  # defaults to sqlite:///<data_dir>/ecce.db
    seed_dir_override: Path | None = Field(
        default=None, alias="SEED_DIR"
    )  # defaults to <data_dir>/seed

    # admin access
    admin_password: str | None = None
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    token_ttl_minutes: int = 12 * 60
    login_attempts_per_minute: int = 10

    # web
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    frontend_dist: Path | None = None  # serve a built SPA from this directory
    # canonical origin of the public site, e.g. https://www.example.org: used for canonical
    # links and the sitemap; requests for other hosts are redirected there (301)
    public_url: str | None = None

    # operator shown in the legal notice (Impressum) and privacy policy; LEGAL_ADDRESS may
    # separate lines with newlines or "|"
    legal_name: str | None = None
    legal_address: str | None = None
    legal_email: str | None = None
    railway_project_id: str | None = None  # injected by Railway; names it as the host
    log_retention_days: int = 7  # how long the host keeps access logs (Railway Hobby: 7 days)

    # contact form: messages are kept in the database and deleted after this many days; with
    # SMTP_HOST set, each message is also e-mailed to LEGAL_EMAIL
    contact_retention_days: int = 180
    contact_messages_per_hour: int = 5
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None  # defaults to SMTP_USERNAME
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
    page_words: int = 300  # word budget of one reading page
    jobs_sync: bool = False  # run processing jobs inline (tests / CLI)
    seed_on_startup: bool = True
    seed_async: bool = False  # import seeds on a background thread (large seed sets)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ecce.db').as_posix()}"

    @property
    def seed_dir(self) -> Path:
        return self.seed_dir_override or (self.data_dir / "seed")

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (cleared in tests)."""
    return Settings()
