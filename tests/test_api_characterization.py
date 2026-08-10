"""API characterization tests (router-only app, no MediaMTX/torch)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_test_app, _reset_route_globals
from spectrax.recording.db import RecordingsAPI


pytestmark = pytest.mark.api


@pytest.fixture
def client_with_files(test_recordings_dir, test_db_path):
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

    # Seed a safe file and a disallowed extension
    rec_dir = Path(test_recordings_dir)
    (rec_dir / "clip.mp4").write_bytes(b"fake-mp4")
    (rec_dir / "notes.txt").write_text("nope")

    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password="test-password-123",
    )
    with TestClient(app) as client:
        # Login for authorized requests
        r = client.post("/auth/login", json={"password": "test-password-123"})
        assert r.status_code == 200
        yield client

    api.close()
    _reset_route_globals()


def test_path_traversal_blocked(client_with_files, test_recordings_dir):
    # URL-encoded traversal stays on the /recordings route (raw ".." is normalized away)
    r = client_with_files.get("/recordings/%2e%2e/%2e%2e/%2e%2e/etc/passwd")
    assert r.status_code in (403, 404)
    # Nested relative escape from a real prefix
    r2 = client_with_files.get("/recordings/subdir/../../clip.mp4")
    # Either denied as traversal or resolved within dir to clip — never leak outside
    assert r2.status_code in (200, 403, 404)


def test_disallowed_extension_blocked(client_with_files):
    r = client_with_files.get("/recordings/notes.txt")
    assert r.status_code == 403


def test_allowed_file_served(client_with_files):
    r = client_with_files.get("/recordings/clip.mp4")
    assert r.status_code == 200


def test_empty_recordings_list(client_with_files):
    r = client_with_files.get("/api/recordings")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["recordings"] == []
    assert "offset" in data and "limit" in data


def test_missing_recording_404(client_with_files):
    r = client_with_files.get("/api/recordings/99999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_delete_missing_recording_404(client_with_files):
    r = client_with_files.delete("/api/recordings/99999")
    assert r.status_code == 404


def test_video_stream_503_without_detector(client_with_files):
    r = client_with_files.get("/video/stream")
    assert r.status_code == 503


def test_pages_render(client_with_files):
    for path in ("/", "/recordings.html", "/login"):
        r = client_with_files.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


def test_error_body_has_no_path_leak(client_with_files, monkeypatch, test_recordings_dir):
    """Forced failure must not return absolute paths or exception strings."""
    from spectrax.recording.db import RecordingsAPI

    def boom(self, **kwargs):
        raise RuntimeError(f"sqlite failed at {test_recordings_dir}/secret.db")

    monkeypatch.setattr(RecordingsAPI, "get_recordings", boom)
    r = client_with_files.get("/api/recordings")
    assert r.status_code == 500
    body = r.text
    assert test_recordings_dir not in body
    assert "secret.db" not in body
    assert "sqlite failed" not in body
    assert "Internal server error" in body


def test_verify_endpoint_gone(client_with_files):
    r = client_with_files.post(
        "/auth/verify",
        json={"username": "viewer", "password": "x"},
    )
    assert r.status_code == 404
