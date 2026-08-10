"""FastAPI application factory (Phase 2).

``create_app`` is the only construction path for production and tests.
Heavy CV imports stay out of this module so web-test CI stays torch-free.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from spectrax.auth_gate import AuthMiddleware, AuthPrincipal, require_read
from spectrax.config import SpectraXSettings, load_settings
from spectrax.routes import (
    auth_router,
    files_router,
    pages_router,
    recordings_router,
    statistics_router,
    video_router,
)
from spectrax.utils import detect_host_ip

logger = logging.getLogger("spectrax.app")


@asynccontextmanager
async def _default_lifespan(app: FastAPI):
    """Minimal lifespan: stop detector_manager if present."""
    yield
    manager = getattr(app.state, "detector_manager", None)
    if manager is not None:
        logger.info("Stopping detectors on shutdown...")
        stop = getattr(manager, "stop_all", None)
        if callable(stop):
            stop()
    api = getattr(app.state, "recordings_api", None)
    if api is not None:
        close = getattr(api, "close", None)
        if callable(close):
            close()


def create_app(
    *,
    settings: Optional[SpectraXSettings] = None,
    secrets: Any = None,
    recordings_api: Any = None,
    recordings_dir: Optional[str | Path] = None,
    detector_manager: Any = None,
    enable_auth: bool = True,
    secure_cookies: bool = False,
    lifespan: Any = None,
    title: str = "SpectraX API",
) -> FastAPI:
    """Build a FastAPI app with DI via ``app.state``.

    Does not import torch/opencv. Callers that need detection wire
    ``detector_manager`` after construction or via a custom lifespan.
    """
    if settings is None:
        settings = load_settings(None)

    app = FastAPI(title=title, lifespan=lifespan or _default_lifespan)

    app.state.settings = settings
    app.state.secrets = secrets
    app.state.recordings_api = recordings_api
    app.state.recordings_dir = str(recordings_dir) if recordings_dir else None
    app.state.detector_manager = detector_manager
    app.state.secure_cookies = secure_cookies

    bind = settings.network.bind
    port = settings.detection.port
    host_ip = detect_host_ip()
    allowed_origins = [
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
        f"http://{host_ip}:{port}",
        f"http://{bind}:{port}",
    ]
    # Dedupe while preserving order
    seen: set[str] = set()
    origins = []
    for o in allowed_origins:
        if o not in seen:
            seen.add(o)
            origins.append(o)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PUT"],
        allow_headers=["Content-Type", "Authorization", "Cookie"],
        max_age=3600,
    )
    if enable_auth:
        app.add_middleware(AuthMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
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

    @app.get("/status")
    async def get_status(
        feed: Optional[str] = None,
        _principal: AuthPrincipal = Depends(require_read),
    ):
        manager = app.state.detector_manager
        if manager is None:
            raise HTTPException(status_code=503, detail="Detector manager not initialized")
        return manager.get_detector_status(feed)

    @app.get("/feeds")
    async def get_feeds(
        _principal: AuthPrincipal = Depends(require_read),
    ):
        manager = app.state.detector_manager
        if manager is None:
            raise HTTPException(status_code=503, detail="Detector manager not initialized")
        feeds = {}
        for detector_id, detector in manager.get_all_detectors().items():
            feeds[detector_id] = {
                "id": detector_id,
                "name": detector.get_name(),
                "source": detector._mask_credentials(detector.source_url),
            }
        return {"feeds": feeds, "default": manager.default_detector_id}

    return app
