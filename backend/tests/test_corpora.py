"""Gallery, admin ingestion (paste + upload), jobs, deletion and seed import."""

from __future__ import annotations

import json
import shutil

from app.services.seed import export_corpus, import_corpus, read_seed, write_seed

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
    path = write_seed(tmp_path / "seed.json.gz", payload)
    assert path.stat().st_size < len(json.dumps(payload))  # compressed
    payload = read_seed(path)
    payload["corpus"]["slug"] = "alice-copy"
    with Session(engine) as session:
        copy = import_corpus(session, payload)
    assert (
        copy.n_entities == alice["n_entities"]
        and copy.n_edges == alice["n_edges"]
        and copy.n_mentions == alice["n_mentions"]
        and copy.n_pages == alice["n_pages"] > 0
    )
    assert [c["text"] for c in client.get("/api/corpora/alice-copy/pages/2").json()["chunks"]] == [
        c["text"] for c in client.get(f"/api/corpora/{alice['slug']}/pages/2").json()["chunks"]
    ]
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

    source = Path(__file__).resolve().parents[1] / "data" / "seed" / "alice-in-wonderland.json"
    if not source.exists():
        pytest.skip("seed JSON not built")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    shutil.copy(source, seed_dir / source.name)
    settings = Settings(
        data_dir=tmp_path,
        seed_dir_override=seed_dir,
        database_url=f"sqlite:///{(tmp_path / 'seed.db').as_posix()}",
        seed_on_startup=True,
        jobs_sync=True,
        extractor="rule",
    )
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        gallery = client.get("/api/corpora").json()
        assert [c["slug"] for c in gallery] == ["alice-in-wonderland"]
        assert gallery[0]["status"] == "ready" and gallery[0]["extractor"] == "spacy"
        graph = client.get(
            "/api/corpora/alice-in-wonderland/graph", params={"max_nodes": 10}
        ).json()
        assert "alice" in {n["text"].lower() for n in graph["nodes"]}
        assert (
            client.get(
                "/api/corpora/alice-in-wonderland/search", params={"q": "cheshire cat"}
            ).json()["total"]
            >= 1
        )


def test_author_and_year_metadata(client, admin_headers):
    created = client.post(
        "/api/admin/corpora",
        json={
            "title": "Odyssey excerpt",
            "text": "Tell me, O Muse, of Ulysses.",
            "author": "Homer",
            "year": -700,
            "process": True,
        },
        headers=admin_headers,
    ).json()
    assert created["author"] == "Homer" and created["year"] == -700
    updated = client.patch(
        f"/api/admin/corpora/{created['slug']}",
        json={"year": 1900, "author": "Samuel Butler (tr.)"},
        headers=admin_headers,
    ).json()
    assert updated["year"] == 1900 and updated["author"] == "Samuel Butler (tr.)"
    assert client.get("/api/corpora").json()[0]["author"] == "Samuel Butler (tr.)"


def test_async_seed_import(tmp_path):
    """SEED_ASYNC imports on a background thread after the API is up."""
    from pathlib import Path

    import pytest
    from app.core.config import Settings
    from app.core.database import create_db_engine
    from app.main import create_app
    from fastapi.testclient import TestClient

    bundled = Path(__file__).resolve().parents[1] / "data" / "seed"
    alice_seeds = list(bundled.glob("alice-in-wonderland.json*"))
    if not alice_seeds:
        pytest.skip("seed JSON not built")
    seed_dir = tmp_path / "seed"  # only Alice: importing all bundled corpora would take minutes
    seed_dir.mkdir()
    for path in alice_seeds:
        shutil.copy(path, seed_dir / path.name)
    settings = Settings(
        data_dir=tmp_path,
        seed_dir_override=seed_dir,
        database_url=f"sqlite:///{(tmp_path / 'seed.db').as_posix()}",
        seed_on_startup=True,
        seed_async=True,
        jobs_sync=True,
        extractor="rule",
    )
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        app.state.seed_thread.join(timeout=120)
        slugs = [c["slug"] for c in client.get("/api/corpora").json()]
        assert "alice-in-wonderland" in slugs


def test_additive_migration_and_excerpt_backfill(tmp_path):
    """Databases created by an older release gain new columns, excerpts and pages on startup."""
    from app.core.database import create_db_engine, init_db, migrate_columns
    from app.models.entities import Corpus
    from sqlalchemy import text
    from sqlmodel import Session, select

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as connection:  # an old schema without author/year/excerpt/pages
        connection.execute(
            text(
                "CREATE TABLE corpus (id INTEGER PRIMARY KEY, slug VARCHAR NOT NULL, title VARCHAR NOT NULL, description VARCHAR NOT NULL, genre VARCHAR NOT NULL, source VARCHAR NOT NULL, language VARCHAR NOT NULL, status VARCHAR NOT NULL, visible BOOLEAN NOT NULL, window INTEGER NOT NULL, extractor VARCHAR NOT NULL, error VARCHAR, n_documents INTEGER NOT NULL, n_chunks INTEGER NOT NULL, n_entities INTEGER NOT NULL, n_edges INTEGER NOT NULL, n_mentions INTEGER NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, processed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO corpus (slug, title, description, genre, source, language, status, visible, window, extractor, n_documents, n_chunks, n_entities, n_edges, n_mentions, created_at, updated_at) VALUES ('old', 'Old', '', '', '', 'en', 'ready', 1, 2, 'rule', 1, 1, 0, 0, 0, '2026-01-01', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE document (id INTEGER PRIMARY KEY, corpus_id INTEGER NOT NULL, position INTEGER NOT NULL, title VARCHAR NOT NULL, text VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                'CREATE TABLE chunk (id INTEGER PRIMARY KEY, corpus_id INTEGER NOT NULL, document_id INTEGER NOT NULL, position INTEGER NOT NULL, start INTEGER NOT NULL, "end" INTEGER NOT NULL, text VARCHAR NOT NULL)'
            )
        )
        connection.execute(
            text(
                "INSERT INTO document (corpus_id, position, title, text) VALUES (1, 0, 'Doc', 'First paragraph of the old corpus. More text follows here.')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chunk (corpus_id, document_id, position, start, \"end\", text) VALUES (1, 1, 0, 0, 34, 'First paragraph of the old corpus.'), (1, 1, 1, 35, 58, 'More text follows here.')"
            )
        )
    init_db(engine)
    assert init_db(engine) in (True, False)  # idempotent
    assert migrate_columns(engine) == []
    with Session(engine) as session:
        corpus = session.exec(select(Corpus).where(Corpus.slug == "old")).one()
        assert corpus.author == "" and corpus.year is None
        assert corpus.excerpt.startswith("First paragraph")
        assert corpus.n_pages == 1  # pages assigned by the start-up backfill
    with engine.begin() as connection:
        assert [r[0] for r in connection.execute(text("SELECT page FROM chunk ORDER BY id"))] == [
            1,
            1,
        ]
        assert connection.execute(
            text("SELECT COUNT(*) FROM chunk_fts WHERE chunk_fts MATCH 'paragraph'")
        ).scalar_one() in (0, 1)  # FTS table exists (old rows are indexed only when rebuilt)


def test_top_entity_names_ranks_by_mentions():
    import json

    from app.services.processing import top_entity_names

    entities = [
        ("Hatter", 30, 900.0),  # strongly connected but mentioned less often
        ("Alice", 400, 500.0),
        ("Queen", 60, 100.0),
        ("Rabbit", 60, 120.0),  # same count as Queen -> strength decides
        ("Alice", 400, 500.0),  # duplicate surface form is listed once
    ]
    assert json.loads(top_entity_names(entities)) == ["Alice", "Rabbit", "Queen", "Hatter"]
    assert json.loads(top_entity_names(entities, k=2)) == ["Alice", "Rabbit"]
    assert top_entity_names([]) == "[]"


def test_gallery_exposes_excerpt(client, alice):
    gallery = client.get("/api/corpora").json()
    assert gallery[0]["excerpt"].startswith("Alice was beginning to get very tired")
    assert gallery[0]["highlights"][0] == "Alice" and 1 < len(gallery[0]["highlights"]) <= 6
    assert len(gallery[0]["excerpt"]) <= 720


def test_seed_metadata_sync_for_existing_corpus(client, admin_headers, alice, tmp_path):
    """Re-running the seed import updates metadata/excerpt of corpora that already exist."""
    from app.models.entities import Corpus
    from app.services.seed import export_corpus, import_seed_directory, write_seed
    from sqlmodel import Session, select

    engine = client.app.state.engine
    with Session(engine) as session:
        corpus = session.exec(select(Corpus).where(Corpus.slug == alice["slug"])).one()
        payload = export_corpus(session, corpus)
    payload["corpus"]["author"] = "Lewis Carroll"
    payload["corpus"]["year"] = 1865
    payload["corpus"]["license"] = "Public domain"
    payload["corpus"]["source_url"] = "https://www.gutenberg.org/ebooks/11"
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_seed(seed_dir / "alice.json.gz", payload)
    assert import_seed_directory(engine, seed_dir) == []  # nothing new imported
    detail = client.get(f"/api/corpora/{alice['slug']}").json()
    assert detail["author"] == "Lewis Carroll" and detail["year"] == 1865
    assert detail["license"] == "Public domain"
    assert detail["source_url"] == "https://www.gutenberg.org/ebooks/11"
    assert detail["excerpt"].startswith("Alice was beginning")
    assert detail["highlights"][0] == "Alice" and len(detail["highlights"]) <= 6


def test_newer_seed_revision_replaces_the_corpus(client, admin_headers, alice, tmp_path):
    """A seed with a higher revision (e.g. a cleaned text) replaces the imported corpus."""
    from app.models.entities import Corpus
    from app.services.seed import export_corpus, import_seed_directory, write_seed
    from sqlmodel import Session, select

    engine = client.app.state.engine
    with Session(engine) as session:
        corpus = session.exec(select(Corpus).where(Corpus.slug == alice["slug"])).one()
        payload = export_corpus(session, corpus)
    assert payload["corpus"]["revision"] == 0 and "author" in payload["corpus"]
    assert {"source_url", "license", "license_url", "rights"} <= set(payload["corpus"])
    client.patch(
        f"/api/admin/corpora/{alice['slug']}", json={"visible": False}, headers=admin_headers
    )
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_seed(seed_dir / "alice.json.gz", payload)
    assert import_seed_directory(engine, seed_dir) == []  # same revision: kept

    payload["corpus"]["revision"] = 1
    payload["documents"][-1]["text"] += "\n\nEnd of the cleaned text."
    write_seed(seed_dir / "alice.json.gz", payload)
    client.get(f"/api/corpora/{alice['slug']}")  # caches the old graph
    dropped: list[int] = []
    graphs = client.app.state.graphs
    replaced_slugs = import_seed_directory(
        engine, seed_dir, lambda i: (dropped.append(i), graphs.invalidate(i))
    )
    assert replaced_slugs == [alice["slug"]] and dropped == [corpus.id]
    with Session(engine) as session:
        replaced = session.exec(select(Corpus).where(Corpus.slug == alice["slug"])).one()
        assert replaced.seed_revision == 1
        assert replaced.visible is False  # the admin's choice survives the replacement
        text = export_corpus(session, replaced)["documents"][-1]["text"]
    assert text.endswith("End of the cleaned text.")
    assert import_seed_directory(engine, seed_dir) == []  # only once
