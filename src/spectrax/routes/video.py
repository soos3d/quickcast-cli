"""Video streaming routes."""

import asyncio
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from spectrax.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/video", tags=["video"])

# Global detector manager reference (set by visualizer)
detector_manager = None


def set_detector_manager(manager):
    """Set the detector manager instance."""
    global detector_manager
    detector_manager = manager


def reset_video_state():
    """Reset module globals (tests)."""
    global detector_manager
    detector_manager = None


@router.get("/stream")
async def video_feed(
    feed: Optional[str] = None,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Stream MJPEG video feed with object detection overlay."""
    global detector_manager
    if detector_manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")

    return StreamingResponse(
        generate_frames(feed),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/jpeg/{detector_id}")
async def video_frame(
    detector_id: str,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get a single frame as JPEG from a specific detector."""
    global detector_manager
    if detector_manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")

    frame_bytes = detector_manager.get_frame_jpeg(detector_id)
    return StreamingResponse(content=io.BytesIO(frame_bytes), media_type="image/jpeg")


async def generate_frames(detector_id: Optional[str] = None):
    """Generate video frames for streaming."""
    global detector_manager
    
    if detector_manager is None:
        return
    
    while True:
        # Get the latest processed frame as JPEG
        frame_bytes = detector_manager.get_frame_jpeg(detector_id)
        
        # Yield the frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Control the frame rate of the stream
        await asyncio.sleep(0.03)  # ~30 FPS
