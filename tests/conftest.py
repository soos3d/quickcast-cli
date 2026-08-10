"""Pytest configuration and shared fixtures for tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator, Optional

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db_path(temp_dir):
    """Provide a temporary database path for testing."""
    return str(temp_dir / "test_recordings.db")


@pytest.fixture
def test_recordings_dir(temp_dir):
    """Provide a temporary recordings directory for testing."""
    recordings_dir = temp_dir / "recordings"
    recordings_dir.mkdir(exist_ok=True)
    return str(recordings_dir)


def _reset_auth_and_secrets() -> None:
    from spectrax import credentials as creds_mod
    from spectrax.auth_gate import reset_auth_state, set_secure_cookie, set_signing_key_override

    creds_mod.reset_memory_store()
    reset_auth_state()
    set_signing_key_override(None)
    set_secure_cookie(None)


# Back-compat name used by older tests
def _reset_route_globals() -> None:
    _reset_auth_and_secrets()


def create_test_app(
    *,
    recordings_dir: Optional[str] = None,
    recordings_api=None,
    with_auth: bool = True,
    admin_password: Optional[str] = "test-password-123",
):
    """Build a FastAPI app via create_app (no visualizer/torch)."""
    from spectrax import credentials as creds_mod
    from spectrax.app import create_app
    from spectrax.auth_gate import set_secure_cookie, set_signing_key_override
    from spectrax.config import SpectraXSettings

    creds_mod.use_memory_store(True)
    set_signing_key_override("test-session-signing-key-32bytes!!")
    set_secure_cookie(False)

    if admin_password:
        creds_mod.set_admin_password(admin_password)

    settings = SpectraXSettings()
    app = create_app(
        settings=settings,
        secrets=creds_mod.get_store(),
        recordings_api=recordings_api,
        recordings_dir=recordings_dir,
        detector_manager=None,
        enable_auth=with_auth,
        secure_cookies=False,
        title="SpectraX API Test",
    )
    return app


@pytest.fixture
def memory_secrets():
    """Enable in-memory keyring for a test, then reset."""
    from spectrax import credentials as creds_mod
    from spectrax.auth_gate import reset_auth_state, set_signing_key_override

    store = creds_mod.use_memory_store(True)
    set_signing_key_override("test-session-signing-key-32bytes!!")
    yield store
    _reset_auth_and_secrets()


@pytest.fixture
def api_client(test_recordings_dir, test_db_path) -> Generator:
    """Authenticated TestClient with empty recordings DB."""
    from fastapi.testclient import TestClient
    from spectrax.recording.db import RecordingsAPI

    _reset_auth_and_secrets()

    api = RecordingsAPI(db_path=test_db_path)
    # Ensure schema exists for empty DB paths used by characterization
    if hasattr(api, "db_conn") and api.db_conn:
        api.db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                stream_name TEXT,
                duration REAL,
                confidence REAL,
                tracker_ids TEXT,
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
        admin_password="test-password-123",
    )
    with TestClient(app) as client:
        r = client.post("/auth/login", json={"password": "test-password-123"})
        assert r.status_code == 200
        yield client

    api.close()
    _reset_auth_and_secrets()


@pytest.fixture
def unauthenticated_client(test_recordings_dir, test_db_path) -> Generator:
    from fastapi.testclient import TestClient
    from spectrax.recording.db import RecordingsAPI

    _reset_auth_and_secrets()
    api = RecordingsAPI(db_path=test_db_path)
    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password="test-password-123",
    )
    with TestClient(app) as client:
        yield client
    api.close()
    _reset_auth_and_secrets()
