"""Unit tests for pydantic-settings SpectraXSettings (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from spectrax.config import (
    SpectraXSettings,
    SurveillanceConfig,
    load_settings,
)
from spectrax.paths import default_config_path


pytestmark = pytest.mark.unit


def test_load_settings_from_repo_example():
    path = default_config_path()
    settings = load_settings(path)
    assert settings.network.bind == "127.0.0.1"
    assert settings.detection.port == 8080
    assert 0.0 <= settings.detection.confidence <= 1.0
    assert settings.recording.codec == "avc1"


def test_defaults_without_file():
    settings = load_settings(None)
    assert settings.network.bind == "127.0.0.1"
    assert settings.detection.enabled is True
    assert settings.mediamtx.managed is True
    assert settings.recording.record_objects is None  # all
    assert settings.detection.filters.classes is None  # all when default


def test_empty_list_classes_become_none(tmp_path: Path):
    cfg = tmp_path / "spectrax.yml"
    cfg.write_text(
        """
cameras: [video/cam]
detection:
  filters:
    classes: []
recording:
  record_objects: []
""",
        encoding="utf-8",
    )
    settings = load_settings(cfg)
    assert settings.detection.filters.classes is None
    assert settings.recording.record_objects is None


def test_invalid_confidence_rejected(tmp_path: Path):
    cfg = tmp_path / "bad.yml"
    cfg.write_text(
        """
detection:
  confidence: 1.5
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_settings(cfg)


def test_env_override_api_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = tmp_path / "spectrax.yml"
    cfg.write_text("detection:\n  port: 8080\n", encoding="utf-8")
    monkeypatch.setenv("SPECTRAX_DETECTION__PORT", "9090")
    settings = load_settings(cfg)
    assert settings.detection.port == 9090
    monkeypatch.delenv("SPECTRAX_DETECTION__PORT", raising=False)


def test_recordings_dir_expands_home():
    settings = SpectraXSettings()
    path = settings.recording.expanded_recordings_dir()
    assert "~" not in path
    assert path.endswith("video-feed-recordings") or "video-feed-recordings" in path


def test_surveillance_config_adapter_bind():
    sc = SurveillanceConfig()
    assert sc.get_bind_address() == "127.0.0.1"
    assert sc.get_detection_port() == 8080


def test_surveillance_config_adapter_from_file():
    path = default_config_path()
    sc = SurveillanceConfig(path)
    assert sc.get_bind_address() == "127.0.0.1"
    # Adapter maps None → [] for "record all" legacy callers
    objects = sc.get_record_objects()
    assert isinstance(objects, list)
