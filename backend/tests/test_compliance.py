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
        assert "Data Privacy Framework" in privacy and "after 7 days" in privacy
        assert "Right to object (Art. 21 GDPR)" in privacy and "Lautenschlagerstraße 20" in privacy
        assert 'href="/contact"' in notice.text  # second contact channel next to e-mail


def test_legal_notice_without_address(settings):
    with make_client(
        settings, legal_name="Erika Mustermann", legal_email="erika@example.org"
    ) as client:
        notice = client.get("/legal").text
        assert "Erika Mustermann<br>E-mail:" in notice and 'href="/contact"' in notice
        assert "has not published contact details" not in notice


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
    assert meta.get("source_url", "").startswith("https://"), "link to the original source"
    assert meta.get("license") and meta.get("license_url", "").startswith("https://")
    assert meta.get("rights"), "rights statement shown in the reader's Details tab"
    if meta["source"].startswith("Project Gutenberg #"):
        number = meta["source"].removeprefix("Project Gutenberg #")
        assert meta["source_url"] == f"https://www.gutenberg.org/ebooks/{number}"
        assert meta["license"] == "Public domain"
    if meta["slug"] == "vergil-opera":
        assert "CC BY-SA 4.0" in meta["source"]  # the licence must be named where it is shown
        assert meta["license"] == "CC BY-SA 4.0" and "Perseus" in meta["rights"]
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


def test_contact_form_stores_messages_for_the_admin(client, admin_headers):
    message = {"name": "Ada", "email": "ada@example.org", "message": "A question about the corpus."}
    assert client.post("/api/contact", json=message).status_code == 202
    # spam bots fill the honeypot: accepted silently, not stored
    assert client.post("/api/contact", json={**message, "website": "spam"}).status_code == 202
    assert client.post("/api/contact", json={**message, "email": "no-address"}).status_code == 422
    assert client.get("/api/admin/messages").status_code == 401
    inbox = client.get("/api/admin/messages", headers=admin_headers).json()
    assert [(m["name"], m["email"], m["handled"]) for m in inbox] == [
        ("Ada", "ada@example.org", False)
    ]
    first = inbox[0]["id"]
    patched = client.patch(
        f"/api/admin/messages/{first}", json={"handled": True}, headers=admin_headers
    )
    assert patched.json()["handled"] is True
    assert client.delete(f"/api/admin/messages/{first}", headers=admin_headers).status_code == 204
    assert client.get("/api/admin/messages", headers=admin_headers).json() == []


def test_contact_form_is_rate_limited_and_expires(client, admin_headers, settings):
    from datetime import UTC, datetime, timedelta

    from app.models.entities import ContactMessage
    from sqlmodel import Session

    with Session(client.app.state.engine) as session:
        old = datetime.now(UTC) - timedelta(days=settings.contact_retention_days + 1)
        session.add(ContactMessage(email="old@example.org", message="Old message.", created_at=old))
        session.commit()
    assert client.get("/api/admin/messages", headers=admin_headers).json() == []  # purged
    body = {"email": "a@example.org", "message": "Ten characters at least."}
    limit = settings.contact_messages_per_hour
    codes = [client.post("/api/contact", json=body).status_code for _ in range(limit + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {202}


def test_withdrawn_seeds_are_removed(client, alice, tmp_path):
    from app.services.seed import import_seed_directory

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    withdrawn = f"# rights not cleared\n{alice['slug']}\n"
    (seed_dir / "withdrawn.txt").write_text(withdrawn, encoding="utf-8")
    dropped: list[int] = []
    assert import_seed_directory(client.app.state.engine, seed_dir, dropped.append) == []
    assert client.get(f"/api/corpora/{alice['slug']}").status_code == 404 and len(dropped) == 1
