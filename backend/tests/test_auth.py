"""Admin authentication and authorisation guardrails."""

from __future__ import annotations

import jwt
from app.core.config import Settings
from app.core.database import create_db_engine
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD


def test_login_issues_bearer_token(client):
    response = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {"subject": "admin", "role": "admin"}


def test_wrong_password_is_rejected(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"password": ""}).status_code == 422


def test_write_endpoints_require_token(client):
    assert client.post("/api/admin/corpora", json={"title": "x", "text": "y"}).status_code == 401
    assert client.get("/api/admin/jobs").status_code == 401
    assert client.delete("/api/admin/corpora/anything").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/auth/me", headers=bad).status_code == 401


def test_forged_and_expired_tokens_are_rejected(client, settings):
    forged = jwt.encode({"sub": "admin", "role": "admin"}, "other-secret", algorithm="HS256")
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    )
    expired = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": 1}, settings.secret_key, algorithm="HS256"
    )
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code
        == 401
    )
    reader = jwt.encode({"sub": "guest", "role": "reader"}, settings.secret_key, algorithm="HS256")
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {reader}"}).status_code == 403
    )


def test_admin_disabled_without_password(tmp_path):
    settings = Settings(
        admin_password=None,
        database_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}",
        data_dir=tmp_path,
        seed_on_startup=False,
        jobs_sync=True,
        extractor="rule",
    )
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        assert client.get("/api/health").json()["admin_enabled"] is False
        assert client.post("/api/auth/login", json={"password": "x"}).status_code == 503
        assert (
            client.post("/api/admin/corpora", json={"title": "x", "text": "y"}).status_code == 503
        )


def test_login_rate_limit(tmp_path):
    settings = Settings(
        admin_password="pw",
        login_attempts_per_minute=3,
        database_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}",
        data_dir=tmp_path,
        seed_on_startup=False,
        jobs_sync=True,
        extractor="rule",
    )
    app = create_app(settings, create_db_engine(settings.resolved_database_url))
    with TestClient(app) as client:
        codes = [
            client.post("/api/auth/login", json={"password": "wrong"}).status_code for _ in range(4)
        ]
        assert codes == [401, 401, 401, 429]


def test_hidden_corpora_are_invisible_to_the_public(client, admin_headers, alice):
    slug = alice["slug"]
    assert (
        client.patch(
            f"/api/admin/corpora/{slug}", json={"visible": False}, headers=admin_headers
        ).json()["visible"]
        is False
    )
    assert client.get("/api/corpora").json() == []
    assert client.get(f"/api/corpora/{slug}").status_code == 404
    assert client.get(f"/api/corpora/{slug}/graph").status_code == 404
    # admins still see it
    assert client.get(f"/api/corpora/{slug}", headers=admin_headers).status_code == 200
    assert [
        c["slug"]
        for c in client.get("/api/corpora", params={"all": 1}, headers=admin_headers).json()
    ] == [slug]
