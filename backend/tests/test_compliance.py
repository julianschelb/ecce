"""Legal pages, third-party requests and the rights/cleanliness of the bundled corpora."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.database import create_db_engine
from app.core.security import LoginRateLimiter
from app.main import create_app
from app.services.seed import read_seed
from fastapi.testclient import TestClient

DATA = Path(__file__).resolve().parents[1] / "data"
SEEDS = sorted((DATA / "seed").glob("*.json*"))
BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "build_gutenberg_seeds.py"
# anything Project Gutenberg or its volunteers added to a work, and e-mail addresses
BOILERPLATE = re.compile(
    r"Project Gutenberg|\be-?texts?\b|pgdp\.net|Distributed Proofread|Transcriber['’]s note|"
    r"^\W*(?:Produced|Transcribed) by\b|[\w.+-]+@[\w-]+\.[a-z]{2,}",
    re.I | re.M,
)


def make_client(settings: Settings, **update) -> TestClient:
    settings = settings.model_copy(update=update)
    return TestClient(create_app(settings, create_db_engine(settings.resolved_database_url)))


def test_legal_pages_name_the_configured_operator(settings):
    with make_client(
        settings,
        legal_name="Erika Mustermann",
        legal_address="Musterstraße 1 | 78462 Konstanz | Germany",
        legal_email="erika@example.org",
        railway_project_id="project-id",
    ) as client:
        notice = client.get("/legal")
        assert notice.status_code == 200 and "§ 5 DDG" in notice.text
        assert "Erika Mustermann<br>Musterstraße 1<br>78462 Konstanz<br>Germany" in notice.text
        assert 'href="mailto:erika@example.org"' in notice.text
        privacy = client.get("/privacy").text
        assert "Erika Mustermann" in privacy and "Railway Corporation" in privacy
        assert "Standard Contractual Clauses" in privacy and "no cookies" in privacy.lower()


def test_legal_pages_without_configuration(settings):
    with make_client(settings, legal_name="<script>", legal_address=None) as client:
        for path in ("/legal", "/privacy"):
            text = client.get(path).text
            assert "has not published contact details" in text and "<script>" not in text
        assert "Railway" not in client.get("/privacy").text


def test_api_docs_use_bundled_assets(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "swagger").mkdir(parents=True)
    (dist / "assets").mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "swagger" / "swagger-ui-bundle.js").write_text("", encoding="utf-8")
    with make_client(settings, frontend_dist=dist) as client:
        html = client.get("/api/docs").text
        assert "/swagger/swagger-ui-bundle.js" in html and "/swagger/swagger-ui.css" in html
        assert "cdn.jsdelivr.net" not in html and "tiangolo.com" not in html


def test_login_limiter_forgets_addresses():
    limiter = LoginRateLimiter(5)
    limiter.check("198.51.100.7")
    limiter._hits["198.51.100.7"][0] -= 120  # an attempt two minutes ago
    limiter.check("203.0.113.9")
    assert list(limiter._hits) == ["203.0.113.9"]


def test_strip_production_notes():
    spec = importlib.util.spec_from_file_location("builder", BUILDER)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    text = "\n\n".join(
        [
            "Produced by Jane Doe and the Online Distributed Proofreading Team",
            "[Transcriber's Note: spelling retained",
            "as in the original.]",
            "CHAPTER I.",
            "It was a dark night [Transcriber's Note: sic] and cold.",
            "The notebook lay on the desk; no pretext was needed.",
            "THE END",
            "End of Project Gutenberg's A Book, by An Author",
            "*** licence text ***",
        ]
    )
    assert builder.strip_production_notes(text).split("\n\n") == [
        "CHAPTER I.",
        "It was a dark night and cold.",
        "The notebook lay on the desk; no pretext was needed.",
        "THE END",
    ]


@pytest.mark.parametrize("path", SEEDS, ids=[p.name for p in SEEDS])
def test_bundled_corpora_are_clean_and_attributed(path):
    corpus = read_seed(path)
    meta = corpus["corpus"]
    assert meta.get("author") and meta.get("year") is not None, "author and year are required"
    assert meta.get("source"), "every corpus names its source"
    if meta["slug"] == "vergil-opera":
        assert "CC BY-SA 4.0" in meta["source"]  # the licence must be named where it is shown
    for document in corpus["documents"]:
        match = BOILERPLATE.search(document["text"])
        assert match is None, (
            f"{meta['slug']}: {document['text'][match.start() - 40 : match.end() + 40]!r}"
        )


def test_catalogue_passes_the_rights_check():
    catalogue = json.loads((DATA / "catalogue" / "gutenberg.json").read_text(encoding="utf-8"))
    for entry in catalogue:
        assert entry.get("verified") is True, entry["slug"]
        assert entry["year"] < 1931, entry["slug"]  # first published before 1931 (US)
        for person in entry["people"]:
            assert person["died"] is not None and person["died"] <= 1955, (entry["slug"], person)
