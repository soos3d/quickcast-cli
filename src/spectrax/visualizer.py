"""API server for SpectraX with object detection."""

import logging
import os
import signal
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from spectrax.detector import DetectorManager
from spectrax.recorder import RecordingManager
from spectrax.api import RecordingsAPI
from spectrax.utils import detect_host_ip
from spectrax.auth_gate import (
    AuthMiddleware,
    AuthPrincipal,
    require_read,
)

# Import route modules
from spectrax.routes import (
    video_router,
    pages_router,
    files_router,
    recordings_router,
    statistics_router,
    auth_router
)
import spectrax.routes.video as video_routes
import spectrax.routes.files as files_routes
import spectrax.routes.recordings as recordings_routes
import spectrax.routes.statistics as statistics_routes

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('video-api-server')

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop hook for the FastAPI process (replaces @app.on_event)."""
    yield
    global detector_manager
    logger.info("Server is shutting down, stopping detector...")
    if detector_manager:
        logger.info("Stopping all detectors...")
        detector_manager.stop_all()
        logger.info("All detectors stopped successfully")
    logger.info("Detector stopped successfully")


# Create FastAPI app
app = FastAPI(title="SpectraX API", lifespan=lifespan)

# Phase 0: Secure=False on plain HTTP (trusted LAN). Set True when TLS terminates here.
app.state.secure_cookies = False

# Get host IP for CORS configuration
host_ip = detect_host_ip()

# Configure CORS middleware with restricted origins (same-origin dashboard primary)
allowed_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    f"http://{host_ip}:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
    max_age=3600,
)

# Auth gate (outermost after CORS — added last so it runs first on request)
app.add_middleware(AuthMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces or paths to clients (H2)."""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal", "message": "Internal server error"}},
    )


# Include all route modules
app.include_router(video_router)
app.include_router(pages_router)
app.include_router(files_router)
app.include_router(recordings_router)
app.include_router(statistics_router)
app.include_router(auth_router)
# Global instances
detector_manager = None
recordings_api = None
recordings_directory = None


def set_detector_manager(manager):
    """Set the global detector manager instance.
    
    This function is called by the surveillance system to set the detector manager.
    """
    global detector_manager
    detector_manager = manager
    
    # Also set in route modules that need it
    video_routes.set_detector_manager(manager)
    statistics_routes.set_detector_manager(manager)
    
    # Detector manager set silently
    # logger.info(f"Detector manager set with {len(manager.get_all_detectors())} detectors")
    return detector_manager


@app.get("/status")
async def get_status(
    feed: Optional[str] = None,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get the detector status for one or all feeds."""
    global detector_manager
    if detector_manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")

    return detector_manager.get_detector_status(feed)


@app.get("/feeds")
async def get_feeds(
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get information about all available feeds."""
    global detector_manager
    if detector_manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")

    feeds = {}
    for detector_id, detector in detector_manager.get_all_detectors().items():
        feeds[detector_id] = {
            "id": detector_id,
            "name": detector.get_name(),
            "source": detector._mask_credentials(detector.source_url),
        }

    return {"feeds": feeds, "default": detector_manager.default_detector_id}

# Create a shutdown event to coordinate graceful shutdown
shutdown_requested = threading.Event()


def force_exit():
    """Force exit after a timeout."""
    time.sleep(3)  # Give a few seconds for graceful shutdown
    logger.warning("Forcing exit after timeout")
    os._exit(0)  # Hard exit

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
    codec: str = 'avc1'
):
    """Start the API server with object detection for multiple streams.
    
    Args:
        rtsp_urls: List of RTSP source URLs with credentials
        host: Host to bind the FastAPI server
        port: Port to bind the FastAPI server
        model_path: Path to YOLO model or model name
        confidence: Detection confidence threshold
        resolution: Output resolution (width, height)
        enable_recording: Whether to enable recording of detected objects
        recordings_dir: Directory to store recordings
        min_confidence: Minimum confidence for recording
        pre_detection_buffer: Seconds to buffer before detection
        post_detection_buffer: Seconds to buffer after detection
    """
    global detector_manager, recordings_api, recordings_directory
    
    # Set recordings directory even if recording is not enabled
    # This allows accessing existing recordings even when not recording new ones
    if recordings_dir:
        # Make sure to expand user path (~ or $HOME)
        expanded_path = os.path.expanduser(recordings_dir)
        recordings_directory = expanded_path
        logger.info(f"Using recordings directory: {recordings_directory} (expanded from {recordings_dir})")
    else:
        default_path = os.path.expanduser("~/video-feed-recordings")
        recordings_directory = default_path
        logger.info(f"Using default recordings directory: {recordings_directory}")
        
    # Ensure the directory exists
    os.makedirs(recordings_directory, exist_ok=True)
    
    # Set recordings directory in route modules
    files_routes.set_recordings_directory(recordings_directory)
    recordings_routes.set_recordings_directory(recordings_directory)
    
    # Initialize the recording manager if enabled
    recording_manager = None
    if enable_recording:
        logger.info("Initializing recording manager")
        recording_manager = RecordingManager(
            recordings_dir=recordings_directory,
            min_confidence=min_confidence,
            pre_detection_buffer=pre_detection_buffer,
            post_detection_buffer=post_detection_buffer,
            codec=codec
        )
        recording_manager.start()
        
        # Initialize the recordings API with shared database connection
        logger.info("Initializing recordings API with shared connection")
        recordings_api = RecordingsAPI(db_connection=recording_manager.get_database_connection())
        logger.info(f"Recordings API initialized with database at {recording_manager.get_database_path()}")
        
        # Set recordings API in route modules
        recordings_routes.set_recordings_api(recordings_api)
        statistics_routes.set_recordings_api(recordings_api)
    
    # Initialize the detector manager
    detector_manager = DetectorManager(recording_manager=recording_manager)
    set_detector_manager(detector_manager)
    logger.info(f"Initializing detection for {len(rtsp_urls)} streams")
    
    # Define our own signal handler for graceful shutdown
    def handle_exit(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        shutdown_requested.set()
        
        # Stop all detectors BEFORE shutting down uvicorn
        if detector_manager:
            logger.info("Stopping all detectors...")
            detector_manager.stop_all()
            logger.info("All detectors stopped successfully")
        
        # Start a watchdog thread to force exit if graceful shutdown takes too long
        exit_thread = threading.Thread(target=force_exit, daemon=True)
        exit_thread.start()
    
    # Register our custom signal handlers
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    try:
        # Load model once and add all detectors
        logger.info(f"Loading YOLO model: {model_path}")
        for url in rtsp_urls:
            # Add detector to manager
            logger.info(f"Starting detector for stream: {url.split('@')[-1] if '@' in url else url}")
            detector_manager.add_detector(
                source_url=url,
                model_path=model_path,
                confidence=confidence,
                resolution=resolution
            )
        
        # Config for Uvicorn with shutdown timeout
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
            timeout_keep_alive=2,    # Shorter keep-alive timeout 
            timeout_graceful_shutdown=3  # Shorter graceful shutdown timeout
        )
        
        # Start Uvicorn server
        server = uvicorn.Server(config)
        logger.info(f"Starting API server with {len(rtsp_urls)} streams at http://{host}:{port}")
        logger.info("Press Ctrl+C once to exit cleanly.")
        server.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received directly in start_api_server")
    except Exception as e:
        logger.error(f"Error in API server: {e}")
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
        
        # Make sure all detectors are stopped
        if detector_manager:
            logger.info("Final cleanup of all detectors...")
            detector_manager.stop_all()
            detector_manager = None
        
        # Close the API connection
        if recordings_api:
            logger.info("Closing recordings API connection...")
            recordings_api.close()
            recordings_api = None
            
        logger.info("All API server resources released")