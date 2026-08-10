"""Deprecated: detection + API wiring lives in ``spectrax.runtime`` + ``serve``.

Kept as a thin wrapper for any external callers of ``start_visualizer``.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import uvicorn

from spectrax.app import create_app
from spectrax.config import SpectraXSettings
from spectrax.runtime import start_detection_stack

logger = logging.getLogger("video-api-server")


def start_visualizer(
    rtsp_urls: List[str],
    host: str = "127.0.0.1",
    port: int = 8000,
    model_path: str = "yolov8n.pt",
    confidence: float = 0.4,
    resolution: tuple = (960, 540),
    enable_recording: bool = False,
    recordings_dir: Optional[str] = None,
    min_confidence: float = 0.5,
    pre_detection_buffer: int = 5,
    post_detection_buffer: int = 5,
    codec: str = "avc1",
):
    """Start API + detectors (legacy entry; prefer ``spectrax serve``)."""
    settings = SpectraXSettings(
        network={"bind": host},
        detection={
            "port": port,
            "enabled": True,
            "model": model_path,
            "confidence": confidence,
            "resolution": {"width": resolution[0], "height": resolution[1]},
        },
        recording={
            "enabled": enable_recording,
            "min_confidence": min_confidence,
            "pre_buffer_seconds": pre_detection_buffer,
            "post_buffer_seconds": post_detection_buffer,
            "recordings_dir": recordings_dir or "~/video-feed-recordings",
            "codec": codec,
        },
    )
    recording_manager, recordings_api, detector_manager = start_detection_stack(
        settings, rtsp_urls=rtsp_urls
    )
    app = create_app(
        settings=settings,
        recordings_api=recordings_api,
        recordings_dir=settings.recording.expanded_recordings_dir(),
        detector_manager=detector_manager,
        enable_auth=True,
    )
    logger.info("Starting API at http://%s:%s (legacy start_visualizer)", host, port)
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        if detector_manager is not None:
            detector_manager.stop_all()
        if recordings_api is not None:
            recordings_api.close()
