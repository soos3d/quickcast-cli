"""Auth gate tests: session cookie, bearer keys, rate limit, scopes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_test_app, _reset_route_globals
from spectrax import credentials as creds_mod
from spectrax.api import RecordingsAPI
from spectrax.auth_gate import (
    COOKIE_NAME,
    LOGIN_RATE_LIMIT,
    hash_api_key,
)


pytestmark = [pytest.mark.api, pytest.mark.unit]


@pytest.fixture
def auth_env(test_recordings_dir, test_db_path):
    _reset_route_globals()
    api = RecordingsAPI(db_path=test_db_path)
    if api.db_conn is not None:
        api.db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_id TEXT,
                stream_name TEXT,
                timestamp TEXT,
                duration REAL,
                confidence REAL,
                objects_detected TEXT,
                file_path TEXT,
                thumbnail_path TEXT
            )
            """
        )
        api.db_conn.commit()

    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password="correct-horse-battery",
    )
    with TestClient(app) as client:
        yield client, api

    api.close()
    _reset_route_globals()


def test_unauthenticated_api_returns_401(auth_env):
    client, _ = auth_env
    for path in (
        "/api/recordings",
        "/video/stream",
        "/video/jpeg/cam1",
    ):
        r = client.get(path)
        assert r.status_code == 401, path


def test_login_success_sets_httponly_cookie(auth_env):
    client, _ = auth_env
    r = client.post("/auth/login", json={"password": "correct-horse-battery"})
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    cookie = r.cookies.get(COOKIE_NAME)
    assert cookie
    # Subsequent request works
    r2 = client.get("/api/recordings")
    assert r2.status_code == 200


def test_login_wrong_password(auth_env):
    client, _ = auth_env
    r = client.post("/auth/login", json={"password": "wrong-password"})
    assert r.status_code == 401


def test_login_503_when_admin_unset(test_recordings_dir, test_db_path):
    _reset_route_globals()
    api = RecordingsAPI(db_path=test_db_path)
    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password=None,
    )
    with TestClient(app) as client:
        r = client.post("/auth/login", json={"password": "anything-long"})
        assert r.status_code == 503
    api.close()
    _reset_route_globals()


def test_login_rate_limit(auth_env):
    client, _ = auth_env
    for _ in range(LOGIN_RATE_LIMIT):
        r = client.post("/auth/login", json={"password": "wrong-password-xx"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"password": "wrong-password-xx"})
    assert r.status_code == 429


def test_logout_clears_session(auth_env):
    client, _ = auth_env
    assert client.post("/auth/login", json={"password": "correct-horse-battery"}).status_code == 200
    assert client.get("/api/recordings").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/api/recordings").status_code == 401


def test_bearer_read_key(auth_env):
    client, _ = auth_env
    raw = creds_mod.create_api_key("reader", scope="read")
    r = client.get(
        "/api/recordings",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200


def test_bearer_read_cannot_delete(auth_env):
    client, _ = auth_env
    raw = creds_mod.create_api_key("reader", scope="read")
    r = client.delete(
        "/api/recordings/1",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403


def test_bearer_admin_can_delete_missing(auth_env):
    client, _ = auth_env
    raw = creds_mod.create_api_key("admin-key", scope="admin")
    r = client.delete(
        "/api/recordings/99999",
        headers={"Authorization": f"Bearer {raw}"},
    )
    # Admin authenticated; missing id → 404
    assert r.status_code == 404


def test_revoked_key_rejected(auth_env):
    client, _ = auth_env
    raw = creds_mod.create_api_key("temp", scope="read")
    keys = creds_mod.list_api_keys(include_revoked=True)
    kid = keys[-1]["id"]
    assert creds_mod.revoke_api_key(kid)
    r = client.get(
        "/api/recordings",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 401


def test_tampered_cookie_rejected(auth_env):
    client, _ = auth_env
    client.cookies.set(COOKIE_NAME, "not-a-valid-signature")
    r = client.get("/api/recordings")
    assert r.status_code == 401


def test_login_page_public(auth_env):
    client, _ = auth_env
    r = client.get("/login")
    assert r.status_code == 200


def test_password_hash_not_plaintext(memory_secrets):
    creds_mod.set_admin_password("super-secret-password")
    stored = creds_mod.get_admin_password_hash()
    assert stored
    assert "super-secret-password" not in stored
    assert stored.startswith("$argon2")


def test_api_key_hash_storage(memory_secrets):
    raw = creds_mod.create_api_key("x", scope="read")
    entries = creds_mod.list_api_keys()
    assert len(entries) == 1
    assert entries[0]["hash"] == hash_api_key(raw)
    assert raw not in str(entries)
