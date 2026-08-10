"""Video streaming routes."""

import asyncio
import io
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from spectrax.api.deps import get_detector_manager
from spectrax.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/video", tags=["video"])


@router.get("/stream")
async def video_feed(
    feed: Optional[str] = None,
    detector_manager: Any = Depends(get_detector_manager),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Stream MJPEG video feed with object detection overlay."""
    return StreamingResponse(
        generate_frames(detector_manager, feed),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/jpeg/{detector_id}")
async def video_frame(
    detector_id: str,
    detector_manager: Any = Depends(get_detector_manager),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get a single frame as JPEG from a specific detector."""
    frame_bytes = detector_manager.get_frame_jpeg(detector_id)
    return StreamingResponse(content=io.BytesIO(frame_bytes), media_type="image/jpeg")


async def generate_frames(detector_manager: Any, detector_id: Optional[str] = None):
    """Generate video frames for streaming."""
    while True:
        frame_bytes = detector_manager.get_frame_jpeg(detector_id)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        await asyncio.sleep(0.03)
