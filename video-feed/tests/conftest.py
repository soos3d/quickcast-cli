"""Pytest configuration and shared fixtures for tests."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator, Optional

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


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


@pytest.fixture
def sample_config():
    """Provide sample configuration for testing."""
    return {
        "cameras": ["video/test-camera"],
        "network": {
            "bind": "127.0.0.1",
        },
        "detection": {
            "enabled": True,
            "port": 8080,
            "model": "yolov8n.pt",
            "confidence": 0.4,
            "resolution": {
                "width": 960,
                "height": 540,
            },
        },
        "recording": {
            "enabled": True,
            "min_confidence": 0.5,
            "pre_buffer_seconds": 5,
            "post_buffer_seconds": 5,
            "max_storage_gb": 1.0,
            "recordings_dir": "~/test-recordings",
            "record_objects": [],
        },
        "security": {
            "use_tls": False,
            "tls_key": "",
            "tls_cert": "",
        },
    }


def _reset_route_globals() -> None:
    """Clear module-level set_* globals used by routers."""
    import videofeed.routes.files as files_routes
    import videofeed.routes.recordings as recordings_routes
    import videofeed.routes.statistics as statistics_routes
    import videofeed.routes.video as video_routes
    from videofeed import credentials as creds_mod
    from videofeed.auth_gate import reset_auth_state, set_secure_cookie, set_signing_key_override

    if hasattr(files_routes, "reset_files_state"):
        files_routes.reset_files_state()
    else:
        files_routes.recordings_directory = None

    if hasattr(recordings_routes, "reset_recordings_state"):
        recordings_routes.reset_recordings_state()
    else:
        recordings_routes.recordings_api = None
        recordings_routes.recordings_directory = None

    if hasattr(statistics_routes, "reset_statistics_state"):
        statistics_routes.reset_statistics_state()
    else:
        statistics_routes.recordings_api = None
        statistics_routes.detector_manager = None

    if hasattr(video_routes, "reset_video_state"):
        video_routes.reset_video_state()
    else:
        video_routes.detector_manager = None

    creds_mod.reset_memory_store()
    reset_auth_state()
    set_signing_key_override(None)
    set_secure_cookie(None)


def create_test_app(
    *,
    recordings_dir: Optional[str] = None,
    recordings_api=None,
    with_auth: bool = True,
    admin_password: Optional[str] = "test-password-123",
):
    """Build a FastAPI app with routers only (no visualizer/torch).

    Args:
        recordings_dir: Path for file serving and DB.
        recordings_api: Optional RecordingsAPI instance.
        with_auth: Install AuthMiddleware.
        admin_password: If set, store admin hash in memory secrets store.
    """
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    from videofeed.auth_gate import AuthMiddleware, set_secure_cookie, set_signing_key_override
    from videofeed import credentials as creds_mod
    from videofeed.routes import (
        auth_router,
        files_router,
        pages_router,
        recordings_router,
        statistics_router,
        video_router,
    )
    import videofeed.routes.files as files_routes
    import videofeed.routes.recordings as recordings_routes
    import videofeed.routes.statistics as statistics_routes

    # In-memory secrets for CI (no OS keyring)
    creds_mod.use_memory_store(True)
    set_signing_key_override("test-session-signing-key-32bytes!!")
    set_secure_cookie(False)

    if admin_password:
        creds_mod.set_admin_password(admin_password)

    app = FastAPI(title="Video Feed API Test")
    app.state.secure_cookies = False

    if with_auth:
        app.add_middleware(AuthMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": "Internal server error"}},
        )

    app.include_router(video_router)
    app.include_router(pages_router)
    app.include_router(files_router)
    app.include_router(recordings_router)
    app.include_router(statistics_router)
    app.include_router(auth_router)

    if recordings_dir:
        files_routes.set_recordings_directory(recordings_dir)
        recordings_routes.set_recordings_directory(recordings_dir)

    if recordings_api is not None:
        recordings_routes.set_recordings_api(recordings_api)
        statistics_routes.set_recordings_api(recordings_api)

    return app


@pytest.fixture
def memory_secrets():
    """Enable in-memory keyring for a test, then reset."""
    from videofeed import credentials as creds_mod
    from videofeed.auth_gate import reset_auth_state, set_signing_key_override

    store = creds_mod.use_memory_store(True)
    set_signing_key_override("test-session-signing-key-32bytes!!")
    yield store
    _reset_route_globals()


@pytest.fixture
def api_client(test_recordings_dir, test_db_path) -> Generator:
    """Authenticated TestClient with empty recordings DB."""
    from fastapi.testclient import TestClient
    from videofeed.api import RecordingsAPI

    _reset_route_globals()

    # Create empty DB schema via RecordingsAPI if it has init; otherwise empty file
    api = RecordingsAPI(db_path=test_db_path)
    # Ensure tables if API exposes init — many code paths expect a real schema
    if hasattr(api, "db_conn") and api.db_conn is not None:
        try:
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
        except Exception:
            pass

    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password="test-password-123",
    )
    with TestClient(app) as client:
        yield client

    api.close()
    _reset_route_globals()


@pytest.fixture
def api_client_no_auth(test_recordings_dir, test_db_path) -> Generator:
    """TestClient without auth middleware (characterization of route bodies)."""
    from fastapi.testclient import TestClient
    from videofeed.api import RecordingsAPI

    _reset_route_globals()
    api = RecordingsAPI(db_path=test_db_path)
    if hasattr(api, "db_conn") and api.db_conn is not None:
        try:
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
        except Exception:
            pass

    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=False,
        admin_password=None,
    )
    with TestClient(app) as client:
        yield client

    api.close()
    _reset_route_globals()
