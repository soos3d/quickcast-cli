"""FastAPI dependencies — replace module-level set_* setters (Phase 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, Request


def get_settings(request: Request) -> Any:
    return getattr(request.app.state, "settings", None)


def get_secrets(request: Request) -> Any:
    return getattr(request.app.state, "secrets", None)


def get_recordings_api(request: Request) -> Any:
    api = getattr(request.app.state, "recordings_api", None)
    if api is None:
        raise HTTPException(status_code=503, detail="Recordings API not initialized")
    return api


def get_recordings_dir(request: Request) -> Path:
    directory = getattr(request.app.state, "recordings_dir", None)
    if not directory:
        raise HTTPException(status_code=503, detail="Recording directory not configured")
    return Path(directory)


def get_detector_manager(request: Request) -> Any:
    manager = getattr(request.app.state, "detector_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")
    return manager


def get_detector_manager_optional(request: Request) -> Optional[Any]:
    return getattr(request.app.state, "detector_manager", None)
