"""Runtime lifespan and MediaMTX process unit tests (no torch/MediaMTX binary)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spectrax.app import create_app
from spectrax.config import SpectraXSettings
from spectrax.runtime import build_viewer_rtsp_urls, make_production_lifespan


pytestmark = pytest.mark.unit


def test_build_viewer_rtsp_urls_rtsps():
    settings = SpectraXSettings(
        cameras=["video/cam1"],
        network={"bind": "127.0.0.1"},
        security={"use_tls": True},
    )
    creds = {
        "read_user": "viewer",
        "read_pass": "secret",
        "publish_user": "publisher",
        "publish_pass": "pub",
    }
    urls = build_viewer_rtsp_urls(settings, creds)
    assert len(urls) == 1
    assert urls[0].startswith("rtsps://viewer:secret@127.0.0.1:8322/video/cam1")


def test_build_viewer_rtsp_urls_plain():
    settings = SpectraXSettings(
        cameras=["video/a", "video/b"],
        network={"bind": "127.0.0.1"},
        security={"use_tls": False},
    )
    creds = {
        "read_user": "viewer",
        "read_pass": "x",
        "publish_user": "publisher",
        "publish_pass": "y",
    }
    urls = build_viewer_rtsp_urls(settings, creds)
    assert all(u.startswith("rtsp://") for u in urls)
    assert len(urls) == 2


def test_lifespan_skips_mediamtx_and_detection():
    settings = SpectraXSettings(
        mediamtx={"managed": False},
        detection={"enabled": False},
        recording={"enabled": False},
    )
    lifespan = make_production_lifespan(
        settings, manage_mediamtx=False, start_detection=False
    )
    app = create_app(settings=settings, lifespan=lifespan, enable_auth=False)
    with TestClient(app) as client:
        # login page public
        r = client.get("/login")
        assert r.status_code == 200
    assert app.state.detector_manager is None


def test_mediamtx_launch_stop_mocked(tmp_path):
    from spectrax.mediamtx import process as mtx

    cfg = tmp_path / "mediamtx.yml"
    cfg.write_text("paths: {}\n")
    fake = MagicMock()
    fake.poll.return_value = None
    fake.pid = 12345
    with patch("spectrax.mediamtx.process.subprocess.Popen", return_value=fake) as popen:
        with patch("spectrax.mediamtx.process.check_installed"):
            with patch("spectrax.mediamtx.process.time.sleep"):
                proc = mtx.launch(cfg)
    assert proc is fake
    popen.assert_called_once()
    fake.poll.return_value = None
    mtx.stop(fake)
    fake.terminate.assert_called_once()


def test_cli_help_has_serve_not_run_detect():
    from typer.testing import CliRunner

    from spectrax.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output
    assert "doctor" in result.output
    # Hard-deleted
    assert " run " not in f" {result.output} " or "Commands" in result.output
    # More reliable: try invoke
    r2 = runner.invoke(app, ["run", "--help"])
    assert r2.exit_code != 0
    r3 = runner.invoke(app, ["detect", "--help"])
    assert r3.exit_code != 0


def test_cli_doctor_runs():
    from typer.testing import CliRunner

    from spectrax.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    # may exit 1 if mediamtx missing — still should print Python OK
    assert "Python" in result.output
