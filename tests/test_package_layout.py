"""Layout / packaging smoke tests (Phase 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrax import __version__
from spectrax.paths import (
    default_config_path,
    default_tls_paths,
    models_dir,
    project_root,
)


@pytest.mark.unit
def test_package_version():
    assert __version__ == "0.2.0"


@pytest.mark.unit
def test_templates_packaged():
    import spectrax

    templates = Path(spectrax.__file__).resolve().parent / "templates"
    assert templates.is_dir()
    for name in ("login.html", "viewer.html", "recordings.html"):
        assert (templates / name).is_file(), f"missing template {name}"


@pytest.mark.unit
def test_project_root_finds_pyproject():
    root = project_root()
    assert (root / "pyproject.toml").is_file()
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "spectrax"' in text


@pytest.mark.unit
def test_default_config_path_prefers_spectrax_yml():
    path = default_config_path()
    assert path.name in {"spectrax.yml", "surveillance.yml"}
    # In a normal checkout the renamed file exists
    if path.name == "spectrax.yml":
        assert path.is_file()


@pytest.mark.unit
def test_models_dir_under_project_root():
    assert models_dir() == project_root() / "models"


@pytest.mark.unit
def test_default_tls_paths_under_project_root():
    key, cert = default_tls_paths()
    root = project_root()
    assert key == root / "server.key"
    assert cert == root / "server.crt"


@pytest.mark.unit
def test_keychain_service_unchanged():
    """Renaming the package must not invalidate existing keychain secrets."""
    from spectrax.constants import KEYCHAIN_SERVICE

    assert KEYCHAIN_SERVICE == "video-feed-mediamtx"


@pytest.mark.unit
def test_resolve_model_path_uses_models_dir(tmp_path, monkeypatch):
    from spectrax import utils as utils_mod

    fake_root = tmp_path / "repo"
    models = fake_root / "models"
    models.mkdir(parents=True)
    weight = models / "yolov8n.pt"
    weight.write_bytes(b"fake")

    monkeypatch.setattr(utils_mod, "models_dir", lambda: models)
    assert utils_mod.resolve_model_path("yolov8n.pt") == str(weight)
    assert utils_mod.resolve_model_path("missing.pt") == "missing.pt"
