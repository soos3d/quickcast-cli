"""Runtime wiring for detection + API server (Phase 2 bridge).

Uses :func:`spectrax.app.create_app` and ``app.state`` DI. Prefer
``spectrax serve`` / lifespan ownership; this module remains for the
legacy ``detect`` / ``start`` CLI paths until fully collapsed.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import uvicorn

from spectrax.app import create_app
from spectrax.config import SpectraXSettings
from spectrax.detection.detector import DetectorManager
from spectrax.recording.db import RecordingsAPI
from spectrax.recording.recorder import RecordingManager

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
    """Start the API server with object detection for multiple streams."""
    if recordings_dir:
        recordings_directory = os.path.expanduser(recordings_dir)
    else:
        recordings_directory = os.path.expanduser("~/video-feed-recordings")
    os.makedirs(recordings_directory, exist_ok=True)
    logger.info("Using recordings directory: %s", recordings_directory)

    recording_manager = None
    recordings_api = None
    if enable_recording:
        logger.info("Initializing recording manager")
        recording_manager = RecordingManager(
            recordings_dir=recordings_directory,
            min_confidence=min_confidence,
            pre_detection_buffer=pre_detection_buffer,
            post_detection_buffer=post_detection_buffer,
            codec=codec,
        )
        recording_manager.start()
        recordings_api = RecordingsAPI(
            db_connection=recording_manager.get_database_connection()
        )

    detector_manager = DetectorManager(recording_manager=recording_manager)
    logger.info("Initializing detection for %s streams", len(rtsp_urls))
    for url in rtsp_urls:
        logger.info(
            "Starting detector for stream: %s",
            url.split("@")[-1] if "@" in url else url,
        )
        detector_manager.add_detector(
            source_url=url,
            model_path=model_path,
            confidence=confidence,
            resolution=resolution,
        )

    settings = SpectraXSettings(
        network={"bind": host},
        detection={"port": port},
    )
    app = create_app(
        settings=settings,
        recordings_api=recordings_api,
        recordings_dir=recordings_directory,
        detector_manager=detector_manager,
        enable_auth=True,
        secure_cookies=False,
    )

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        timeout_keep_alive=2,
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    logger.info(
        "Starting API server with %s streams at http://%s:%s",
        len(rtsp_urls),
        host,
        port,
    )
    logger.info("Press Ctrl+C once to exit cleanly.")
    try:
        server.run()
    finally:
        logger.info("Final cleanup of all detectors...")
        detector_manager.stop_all()
        if recordings_api is not None:
            recordings_api.close()
        logger.info("All API server resources released")


# Back-compat: some code imported set_detector_manager / app from here
def set_detector_manager(manager):
    """Deprecated no-op kept for surveillance.start_detector mid-refactor."""
    logger.warning("set_detector_manager is deprecated; use create_app app.state")
    return manager
