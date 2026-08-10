"""Recording management routes."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from spectrax.api.deps import get_recordings_api, get_recordings_dir
from spectrax.auth_gate import AuthPrincipal, require_admin, require_read

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

logger = logging.getLogger(__name__)


def _file_url(file_path: str, recordings_directory: str) -> Optional[str]:
    try:
        abs_file_path = os.path.abspath(os.path.expanduser(file_path))
        abs_recordings_dir = os.path.abspath(os.path.expanduser(recordings_directory))
        rel_path = os.path.relpath(abs_file_path, abs_recordings_dir)
        return f"/recordings/{rel_path}"
    except Exception as e:
        logger.error("Error creating file URL: %s", e)
        return None


@router.get("")
async def get_recordings(
    stream_id: Optional[str] = None,
    limit: int = Query(100, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    object_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    sort_by: str = Query("timestamp", regex=r"^(timestamp|confidence|duration)$"),
    sort_order: str = Query("desc", regex=r"^(asc|desc)$"),
    recordings_api: Any = Depends(get_recordings_api),
    recordings_directory: Path = Depends(get_recordings_dir),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get list of recordings from the database with filtering and sorting options."""
    try:
        recordings = recordings_api.get_recordings(
            stream_id=stream_id,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            object_type=object_type,
            min_confidence=min_confidence,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = recordings_api.get_recordings_count(
            stream_id=stream_id,
            start_date=start_date,
            end_date=end_date,
            object_type=object_type,
            min_confidence=min_confidence,
        )
        rec_dir = str(recordings_directory)
        for rec in recordings:
            if rec.get("file_path"):
                rec["file_url"] = _file_url(rec["file_path"], rec_dir)
            if rec.get("thumbnail_path"):
                rec["thumbnail_url"] = _file_url(rec["thumbnail_path"], rec_dir)
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "recordings": recordings,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving recordings: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/stats")
async def get_recording_stats(
    stream_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recordings_api: Any = Depends(get_recordings_api),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get comprehensive statistics about recordings."""
    try:
        return recordings_api.get_comprehensive_stats(
            stream_id=stream_id,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving recording statistics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/{recording_id}")
async def delete_recording(
    recording_id: int,
    recordings_api: Any = Depends(get_recordings_api),
    _principal: AuthPrincipal = Depends(require_admin),
):
    """Delete a recording by ID. Requires admin scope."""
    try:
        success = recordings_api.delete_recording(recording_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Recording {recording_id} not found"
            )
        return {"success": True, "message": f"Recording {recording_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting recording %s: %s", recording_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{recording_id}")
async def get_recording_detail(
    recording_id: int,
    recordings_api: Any = Depends(get_recordings_api),
    recordings_directory: Path = Depends(get_recordings_dir),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detailed information about a specific recording."""
    try:
        recording = recordings_api.get_recording_by_id(recording_id)
        if not recording:
            raise HTTPException(
                status_code=404, detail=f"Recording {recording_id} not found"
            )
        rec_dir = str(recordings_directory)
        if recording.get("file_path"):
            recording["file_url"] = _file_url(recording["file_path"], rec_dir)
        if recording.get("thumbnail_path"):
            recording["thumbnail_url"] = _file_url(recording["thumbnail_path"], rec_dir)
        return recording
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error retrieving recording %s: %s", recording_id, e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e
