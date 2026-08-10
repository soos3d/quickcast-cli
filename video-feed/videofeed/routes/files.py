"""File serving routes with security checks."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from videofeed.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/recordings", tags=["files"])

logger = logging.getLogger(__name__)

# Global recordings directory reference (set by visualizer)
recordings_directory = None


def set_recordings_directory(directory: str):
    """Set the recordings directory path."""
    global recordings_directory
    recordings_directory = directory


def reset_files_state():
    """Reset module globals (tests)."""
    global recordings_directory
    recordings_directory = None


@router.get("/{file_path:path}")
async def serve_recording_file(
    file_path: str,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Serve a recording file (video or thumbnail) with security checks."""
    global recordings_directory

    if not recordings_directory:
        default_path = os.path.expanduser("~/video-feed-recordings")
        if os.path.exists(default_path):
            recordings_directory = default_path
            logger.info(f"Auto-initialized recordings directory to: {recordings_directory}")
        else:
            raise HTTPException(status_code=404, detail="Recording directory not configured")

    try:
        recordings_path = Path(recordings_directory).resolve()
        requested_path = (recordings_path / file_path).resolve()

        if not requested_path.is_relative_to(recordings_path):
            logger.warning(f"Path traversal attempt blocked: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")

        if not requested_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not requested_path.is_file():
            raise HTTPException(status_code=403, detail="Not a file")

        allowed_extensions = {".mp4", ".jpg", ".jpeg", ".png", ".webm", ".enc"}
        if requested_path.suffix.lower() not in allowed_extensions:
            logger.warning(f"Unauthorized file type access attempt: {requested_path.suffix}")
            raise HTTPException(status_code=403, detail="File type not allowed")

        logger.info(f"File access: {file_path}")

        return FileResponse(requested_path)

    except ValueError as e:
        logger.error(f"Path validation error: {e}")
        raise HTTPException(status_code=403, detail="Invalid path")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
