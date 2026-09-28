"""Gallery, admin ingestion (paste + upload), jobs, deletion and seed import."""

from __future__ import annotations

import json

from app.services.seed import export_corpus, import_corpus

from tests.conftest import alice_excerpt


def test_gallery_lists_ready_visible_corpora(client, alice):
    gallery = client.get("/api/corpora").json()
    assert [c["slug"] for c in gallery] == [alice["slug"]]
    detail = client.get(f"/api/corpora/{alice['slug']}").json()
    assert detail["genre"] == "Fiction" and detail["source"] == "Project Gutenberg #11"
    assert detail["label_counts"] == {"Entity": alice["n_entities"]}
    assert detail["top_entities"][0]["text"] == "Alice"
    assert detail["max_weight"] > 0 and detail["max_strength"] > 0
    assert client.get("/api/corpora/missing").status_code == 404


def test_create_without_processing_then_process(client, admin_headers):
    created = client.post(
        "/api/admin/corpora",
        json={
            "title": "Draft",
            "text": "Alice met the Hatter. The Hatter met Alice again.",
            "process": False,
            "split": "none",
        },
        headers=admin_headers,
    ).json()
    assert created["status"] == "empty" and created["n_documents"] == 1
    assert client.get("/api/corpora").json() == []  # not ready -> not public
    job = client.post(f"/api/admin/corpora/{created['slug']}/process", headers=admin_headers)
    assert job.status_code == 202 and job.json()["status"] == "done"
    assert (
        client.get(f"/api/admin/jobs/{job.json()['id']}", headers=admin_headers).json()["progress"]
        == 1.0
    )
    detail = client.get(f"/api/corpora/{created['slug']}").json()
    assert detail["status"] == "ready" and detail["n_entities"] == 2 and detail["n_edges"] == 1
    graph = client.get(f"/api/corpora/{created['slug']}/graph").json()
    assert graph["edges"][0]["count"] == 4  # 2 Alice × 2 Hatter mentions within the window


def test_slugs_are_unique(client, admin_headers):
    a = client.post(
        "/api/admin/corpora",
        json={"title": "Same Title", "text": "Alice.", "process": False},
        headers=admin_headers,
    ).json()
    b = client.post(
        "/api/admin/corpora",
        json={"title": "Same Title", "text": "Alice.", "process": False},
        headers=admin_headers,
    ).json()
    assert a["slug"] == "same-title" and b["slug"] == "same-title-2"


def test_batch_upload(client, admin_headers):
    files = [
        ("files", ("chapter1.txt", alice_excerpt(1).encode("utf-8"), "text/plain")),
        ("files", ("notes.md", b"# Notes\n\nThe Queen shouted at Alice.", "text/markdown")),
        ("files", ("empty.txt", b"   ", "text/plain")),
    ]
    response = client.post(
        "/api/admin/corpora/upload",
        data={"title": "Uploads", "genre": "Test"},
        files=files,
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    corpus = response.json()
    assert corpus["n_documents"] == 2 and corpus["status"] == "ready"
    docs = client.get(f"/api/corpora/{corpus['slug']}/documents").json()
    assert [d["title"] for d in docs] == ["chapter1", "notes"]
    assert (
        client.post(
            "/api/admin/corpora/upload",
            data={"title": "Nothing"},
            files=[("files", ("e.txt", b"", "text/plain"))],
            headers=admin_headers,
        ).status_code
        == 422
    )


def test_delete_removes_everything(client, admin_headers, alice):
    slug = alice["slug"]
    assert client.delete(f"/api/admin/corpora/{slug}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/corpora/{slug}", headers=admin_headers).status_code == 404
    assert client.get("/api/corpora", params={"all": 1}, headers=admin_headers).json() == []
    assert client.delete(f"/api/admin/corpora/{slug}", headers=admin_headers).status_code == 404


def test_seed_export_import_roundtrip(client, admin_headers, alice, tmp_path):
    from app.models.entities import Corpus
    from sqlmodel import Session, select

    engine = client.app.state.engine
    with Session(engine) as session:
        corpus = session.exec(select(Corpus).where(Corpus.slug == alice["slug"])).one()
        payload = export_corpus(session, corpus)
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["corpus"]["slug"] = "alice-copy"
    with Session(engine) as session:
        copy = import_corpus(session, payload)
    assert (
        copy.n_entities == alice["n_entities"]
        and copy.n_edges == alice["n_edges"]
        and copy.n_mentions == alice["n_mentions"]
    )
    original = client.get(f"/api/corpora/{alice['slug']}/graph", params={"max_nodes": 20}).json()
    imported = client.get("/api/corpora/alice-copy/graph", params={"max_nodes": 20}).json()
    assert [n["text"] for n in original["nodes"]] == [n["text"] for n in imported["nodes"]]
    assert [round(e["weight"], 5) for e in original["edges"]] == [
        round(e["weight"], 5) for e in imported["edges"]
    ]
    assert (
        client.get("/api/corpora/alice-copy/search", params={"q": "rabbit"}).json()["total"]
        == client.get(f"/api/corpora/{alice['slug']}/search", params={"q": "rabbit"}).json()[
            "total"
        ]
    )


def test_bundled_seed_loads_on_startup(tmp_path):
    """The shipped Alice in Wonderland seed is imported when the database is empty."""
    from pathlib import Path

    import pytest
    from app.core.config import Settings
    from app.core.database import create_db_engine
    from app.main import create_app
    from fastapi.testclient import TestClient

    seed_dir = Path(__file__).resolve().parents[1] / "data" / "seed"
    if not any(seed_dir.glob("*.json")):
        pytest.skip("seed JSON not built")
    settings = Settings(
        data_dir=seed_dir.parent,
        database_url=f"sqlite:///{(tmp_path / 'seed.db').as_posix()}",
        seed_on_startup=True,
        jobs_sync=True,
        extractor="rule",
    )
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        gallery = client.get("/api/corpora").json()
        assert gallery and gallery[0]["status"] == "ready"
        slug = gallery[0]["slug"]
        graph = client.get(f"/api/corpora/{slug}/graph", params={"max_nodes": 10}).json()
        assert "alice" in {n["text"].lower() for n in graph["nodes"]}
        assert (
            client.get(f"/api/corpora/{slug}/search", params={"q": "cheshire cat"}).json()["total"]
            >= 1
        )
