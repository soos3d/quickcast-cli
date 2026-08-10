"""Project path resolution for package, config, models, and TLS material.

After the ``src/spectrax`` layout, data files live at the repository root
(``config/``, ``models/``, ``server.key``), not next to the Python package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple


def project_root() -> Path:
    """Return the repository / install project root.

    Walks up from this file looking for ``pyproject.toml`` (name spectrax when
    present). Falls back to two parents above the package directory
    (``src/spectrax`` → repo root in a normal checkout).
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            return candidate
        # Prefer the spectrax project file if several pyproject.toml exist.
        if 'name = "spectrax"' in text or "name = 'spectrax'" in text:
            return candidate
        return candidate
    # src/spectrax → repo root
    return here.parent.parent


def default_config_path() -> Path:
    """Path to the example/default YAML config.

    Prefers ``config/spectrax.yml``; falls back to ``config/surveillance.yml``
    for one release of compatibility after the rename.
    """
    root = project_root()
    preferred = root / "config" / "spectrax.yml"
    if preferred.is_file():
        return preferred
    legacy = root / "config" / "surveillance.yml"
    if legacy.is_file():
        return legacy
    return preferred


def default_tls_paths() -> Tuple[Path, Path]:
    """Default MediaMTX TLS key/cert paths at the project root."""
    root = project_root()
    return root / "server.key", root / "server.crt"


def models_dir() -> Path:
    """Directory used for packaged / checked-in YOLO model weights."""
    return project_root() / "models"
