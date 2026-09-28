"""Shared fixtures: an app with a temporary database, synchronous jobs and the rule extractor."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.database import create_db_engine
from app.main import create_app
from fastapi.testclient import TestClient

SEED_TEXT = Path(__file__).resolve().parents[1] / "data" / "seed" / "alice-in-wonderland.txt"
ADMIN_PASSWORD = "correct-horse"


def alice_excerpt(chapters: int = 3) -> str:
    """The first ``chapters`` chapters of the seed text (keeps tests fast)."""
    text = SEED_TEXT.read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer(r"^CHAPTER [IVX]+\.", text, re.M)]
    return text[: starts[chapters]] if len(starts) > chapters else text


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        admin_password=ADMIN_PASSWORD,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        jobs_sync=True,
        extractor="rule",
        seed_on_startup=False,
        secret_key="test-secret",
        login_attempts_per_minute=100,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client: TestClient, admin_headers: dict[str, str]) -> dict:
    """A processed corpus built from the first three chapters of Alice."""
    response = client.post(
        "/api/admin/corpora",
        json={
            "title": "Alice (excerpt)",
            "text": alice_excerpt(3),
            "genre": "Fiction",
            "source": "Project Gutenberg #11",
            "split": "auto",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    corpus = response.json()
    assert corpus["status"] == "ready"
    return corpus
