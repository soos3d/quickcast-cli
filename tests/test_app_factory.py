"""App factory + DI isolation tests (Phase 2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spectrax.app import create_app
from spectrax.config import SpectraXSettings
from spectrax.recording.db import RecordingsAPI
from spectrax.secrets import MemorySecretsStore
from tests.conftest import create_test_app, _reset_route_globals


pytestmark = [pytest.mark.api, pytest.mark.unit]


def test_create_app_unauthenticated_401(test_recordings_dir, test_db_path):
    _reset_route_globals()
    api = RecordingsAPI(db_path=test_db_path)
    app = create_test_app(
        recordings_dir=test_recordings_dir,
        recordings_api=api,
        with_auth=True,
        admin_password="test-password-123",
    )
    with TestClient(app) as client:
        r = client.get("/api/recordings")
        assert r.status_code == 401
    api.close()
    _reset_route_globals()


def test_two_apps_isolated_state(test_recordings_dir, temp_dir):
    """Two create_app instances must not share route DI state."""
    _reset_route_globals()
    from spectrax import credentials as creds_mod
    from spectrax.auth_gate import set_signing_key_override, set_secure_cookie

    creds_mod.use_memory_store(True)
    set_signing_key_override("test-session-signing-key-32bytes!!")
    set_secure_cookie(False)
    creds_mod.set_admin_password("test-password-123")

    db1 = temp_dir / "a.db"
    db2 = temp_dir / "b.db"
    api1 = RecordingsAPI(db_path=str(db1))
    api2 = RecordingsAPI(db_path=str(db2))
    settings = SpectraXSettings()

    app1 = create_app(
        settings=settings,
        recordings_api=api1,
        recordings_dir=test_recordings_dir,
        enable_auth=True,
    )
    app2 = create_app(
        settings=settings,
        recordings_api=api2,
        recordings_dir=test_recordings_dir,
        enable_auth=True,
    )
    assert app1.state.recordings_api is api1
    assert app2.state.recordings_api is api2
    assert app1 is not app2
    api1.close()
    api2.close()
    _reset_route_globals()


def test_no_set_detector_manager_in_routes():
    import spectrax.routes.video as video
    import spectrax.routes.files as files
    import spectrax.routes.recordings as rec
    import spectrax.routes.statistics as stats

    assert not hasattr(video, "set_detector_manager")
    assert not hasattr(files, "set_recordings_directory")
    assert not hasattr(rec, "set_recordings_api")
    assert not hasattr(stats, "set_recordings_api")
