"""File serving routes with security checks."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from spectrax.api.deps import get_recordings_dir
from spectrax.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/recordings", tags=["files"])

logger = logging.getLogger(__name__)


@router.get("/{file_path:path}")
async def serve_recording_file(
    file_path: str,
    recordings_directory: Path = Depends(get_recordings_dir),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Serve a recording file (video or thumbnail) with security checks."""
    try:
        recordings_path = Path(recordings_directory).resolve()
        requested_path = (recordings_path / file_path).resolve()

        if not requested_path.is_relative_to(recordings_path):
            logger.warning("Path traversal attempt blocked: %s", file_path)
            raise HTTPException(status_code=403, detail="Access denied")

        if not requested_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not requested_path.is_file():
            raise HTTPException(status_code=403, detail="Not a file")

        allowed_extensions = {".mp4", ".jpg", ".jpeg", ".png", ".webm"}
        if requested_path.suffix.lower() not in allowed_extensions:
            logger.warning("Unauthorized file type access attempt: %s", requested_path.suffix)
            raise HTTPException(status_code=403, detail="File type not allowed")

        logger.info("File access: %s", file_path)
        return FileResponse(requested_path)

    except ValueError:
        logger.error("Path validation error for %s", file_path)
        raise HTTPException(status_code=403, detail="Invalid path") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error serving file %s: %s", file_path, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
