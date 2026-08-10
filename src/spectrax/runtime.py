"""Production runtime: MediaMTX + detection + recording owned by FastAPI lifespan.

Heavy CV imports are lazy so ``create_app`` stays importable without torch.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, List, Optional

from fastapi import FastAPI

from spectrax.config import SpectraXSettings, write_cfg
from spectrax.credentials import get_credentials
from spectrax.paths import default_tls_paths, state_dir
from spectrax.utils import detect_host_ip

logger = logging.getLogger("spectrax.runtime")


def build_viewer_rtsp_urls(settings: SpectraXSettings, creds: dict) -> List[str]:
    """Build RTSP(S) viewer URLs for each configured camera path."""
    bind = settings.network.bind
    host = detect_host_ip() if bind in ("0.0.0.0", "::") else bind
    use_tls = settings.security.use_tls
    user = creds["read_user"]
    password = creds["read_pass"]
    urls: List[str] = []
    for path in settings.cameras:
        if use_tls:
            urls.append(f"rtsps://{user}:{password}@{host}:8322/{path}")
        else:
            urls.append(f"rtsp://{user}:{password}@{host}:8554/{path}")
    return urls


def _resolve_tls_paths(settings: SpectraXSettings) -> tuple[Optional[str], Optional[str]]:
    sec = settings.security
    if not sec.use_tls:
        return None, None
    if sec.tls_key and sec.tls_cert:
        return sec.tls_key, sec.tls_cert
    key, cert = default_tls_paths()
    if key.is_file() and cert.is_file():
        return str(key), str(cert)
    return None, None


def start_mediamtx_for_settings(settings: SpectraXSettings) -> Any:
    """Write mediamtx.yml under state_dir and launch the process."""
    from spectrax.mediamtx import process as mtx

    creds = get_credentials()
    tls_key, tls_cert = _resolve_tls_paths(settings)
    cfg_path = state_dir() / "mediamtx.yml"
    write_cfg(
        cfg_path,
        settings.network.bind,
        list(settings.cameras),
        creds,
        tls_key=tls_key,
        tls_cert=tls_cert,
    )
    return mtx.launch(cfg_path)


def start_detection_stack(
    settings: SpectraXSettings,
    *,
    rtsp_urls: Optional[List[str]] = None,
) -> tuple[Any, Any, Any]:
    """Start recording manager (optional), RecordingsAPI, DetectorManager.

    Returns (recording_manager, recordings_api, detector_manager).
    """
    # Lazy: pulls opencv/torch
    from spectrax.detection.config import DetectorConfig
    from spectrax.detection.detector import DetectorManager
    from spectrax.recording.db import RecordingsAPI
    from spectrax.recording.recorder import RecordingManager

    recordings_dir = settings.recording.expanded_recordings_dir()
    os.makedirs(recordings_dir, exist_ok=True)

    recording_manager = None
    recordings_api = None
    if settings.recording.enabled:
        record_objects = settings.recording.record_objects
        recording_manager = RecordingManager(
            recordings_dir=recordings_dir,
            min_confidence=settings.recording.min_confidence,
            pre_detection_buffer=settings.recording.pre_buffer_seconds,
            post_detection_buffer=settings.recording.post_buffer_seconds,
            record_objects=list(record_objects) if record_objects else [],
            codec=settings.recording.codec,
        )
        recording_manager.start()
        recordings_api = RecordingsAPI(
            db_connection=recording_manager.get_database_connection()
        )

    detector_manager = None
    if settings.detection.enabled:
        detector_manager = DetectorManager(recording_manager=recording_manager)
        detector_config = DetectorConfig.from_settings(settings)

        if rtsp_urls is None:
            rtsp_urls = build_viewer_rtsp_urls(settings, get_credentials())
        for url in rtsp_urls:
            detector_manager.add_detector(
                source_url=url,
                config=detector_config,
                enable_recording=settings.recording.enabled,
            )

    # If recording without detection, still expose API for existing files
    if recordings_api is None and Path(recordings_dir).exists():
        db_path = Path(recordings_dir) / "recordings.db"
        if db_path.is_file():
            recordings_api = RecordingsAPI(db_path=str(db_path))

    return recording_manager, recordings_api, detector_manager


def make_production_lifespan(
    settings: SpectraXSettings,
    *,
    manage_mediamtx: bool = True,
    start_detection: bool = True,
) -> Callable[[FastAPI], AsyncIterator[None]]:
    """Return a FastAPI lifespan that owns MediaMTX + detection + DB."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        mediamtx_proc = None
        recording_manager = None
        recordings_api = None
        detector_manager = None

        app.state.settings = settings
        app.state.recordings_dir = settings.recording.expanded_recordings_dir()

        try:
            if manage_mediamtx and settings.mediamtx.managed:
                logger.info("Starting managed MediaMTX...")
                mediamtx_proc = start_mediamtx_for_settings(settings)
                app.state.mediamtx_process = mediamtx_proc
                time.sleep(1.0)  # stabilize before detectors connect

            if start_detection and (settings.detection.enabled or settings.recording.enabled):
                logger.info("Starting detection/recording stack...")
                recording_manager, recordings_api, detector_manager = start_detection_stack(
                    settings
                )
                app.state.recordings_api = recordings_api
                app.state.detector_manager = detector_manager
                app.state.recording_manager = recording_manager

            yield
        finally:
            logger.info("Shutting down runtime...")
            if detector_manager is not None:
                try:
                    detector_manager.stop_all()
                except Exception:
                    logger.exception("Error stopping detectors")
            if recording_manager is not None:
                stop = getattr(recording_manager, "stop", None)
                if callable(stop):
                    try:
                        stop()
                    except Exception:
                        logger.exception("Error stopping recording manager")
            if recordings_api is not None:
                try:
                    recordings_api.close()
                except Exception:
                    logger.exception("Error closing recordings API")
            if mediamtx_proc is not None:
                from spectrax.mediamtx import process as mtx

                mtx.stop(mediamtx_proc)
            app.state.detector_manager = None
            app.state.recordings_api = None
            app.state.mediamtx_process = None

    return lifespan
