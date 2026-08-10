"""Recording management routes."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from spectrax.auth_gate import AuthPrincipal, require_admin, require_read

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

logger = logging.getLogger(__name__)

# Global references (set by visualizer)
recordings_api = None
recordings_directory = None


def set_recordings_api(api):
    """Set the recordings API instance."""
    global recordings_api
    recordings_api = api


def set_recordings_directory(directory: str):
    """Set the recordings directory path."""
    global recordings_directory
    recordings_directory = directory


def reset_recordings_state():
    """Reset module globals (tests)."""
    global recordings_api, recordings_directory
    recordings_api = None
    recordings_directory = None


def initialize_recordings_api():
    """Initialize the recordings API if not already initialized.

    Returns:
        bool: True if initialization was successful, False otherwise
    """
    global recordings_api, recordings_directory

    if recordings_api is not None:
        return True

    try:
        from spectrax.api import RecordingsAPI

        if recordings_directory:
            expanded_dir = os.path.expanduser(recordings_directory)
            db_path = os.path.join(expanded_dir, "recordings.db")
            logger.info(f"Looking for database at: {db_path}")

            if os.path.exists(db_path):
                logger.info(f"Initializing recordings API with database: {db_path}")
                recordings_api = RecordingsAPI(db_path=db_path)
                logger.info("Successfully initialized recordings API")
                return True

        home_db_path = os.path.expanduser("~/video-feed-recordings/recordings.db")
        logger.info(f"Looking for database at home path: {home_db_path}")

        if os.path.exists(home_db_path):
            logger.info(
                f"Initializing recordings API with database from home directory: {home_db_path}"
            )
            recordings_api = RecordingsAPI(db_path=home_db_path)

            if not recordings_directory:
                recordings_directory = os.path.dirname(home_db_path)
                logger.info(f"Setting recordings directory to: {recordings_directory}")

            logger.info("Successfully initialized recordings API from home directory")
            return True

        logger.error("Database file not found in configured directory or home directory")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize recordings API: {e}")
        return False


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
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get list of recordings from the database with filtering and sorting options."""
    global recordings_api, recordings_directory

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

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

        for rec in recordings:
            if rec.get("file_path"):
                try:
                    abs_file_path = os.path.abspath(os.path.expanduser(rec["file_path"]))
                    abs_recordings_dir = os.path.abspath(
                        os.path.expanduser(recordings_directory)
                    )
                    rel_path = os.path.relpath(abs_file_path, abs_recordings_dir)
                    rec["file_url"] = f"/recordings/{rel_path}"
                except Exception as e:
                    logger.error(f"Error creating file URL: {e}")
                    rec["file_url"] = None

            if rec.get("thumbnail_path"):
                try:
                    abs_thumb_path = os.path.abspath(
                        os.path.expanduser(rec["thumbnail_path"])
                    )
                    abs_recordings_dir = os.path.abspath(
                        os.path.expanduser(recordings_directory)
                    )
                    rel_path = os.path.relpath(abs_thumb_path, abs_recordings_dir)
                    rec["thumbnail_url"] = f"/recordings/{rel_path}"
                except Exception as e:
                    logger.error(f"Error creating thumbnail URL: {e}")
                    rec["thumbnail_url"] = None

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "recordings": recordings,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_recording_stats(
    stream_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get comprehensive statistics about recordings."""
    global recordings_api

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

    try:
        stats = recordings_api.get_comprehensive_stats(
            stream_id=stream_id,
            start_date=start_date,
            end_date=end_date,
        )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recording statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{recording_id}")
async def delete_recording(
    recording_id: int,
    _principal: AuthPrincipal = Depends(require_admin),
):
    """Delete a recording by ID. Requires admin scope."""
    global recordings_api

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

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
        logger.error(f"Error deleting recording {recording_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{recording_id}")
async def get_recording_detail(
    recording_id: int,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detailed information about a specific recording."""
    global recordings_api, recordings_directory

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

    try:
        recording = recordings_api.get_recording_by_id(recording_id)
        if not recording:
            raise HTTPException(
                status_code=404, detail=f"Recording {recording_id} not found"
            )

        if recording.get("file_path"):
            try:
                abs_file_path = os.path.abspath(
                    os.path.expanduser(recording["file_path"])
                )
                abs_recordings_dir = os.path.abspath(
                    os.path.expanduser(recordings_directory)
                )
                rel_path = os.path.relpath(abs_file_path, abs_recordings_dir)
                recording["file_url"] = f"/recordings/{rel_path}"
                logger.info(
                    f"Created file URL: {recording['file_url']} from {recording['file_path']}"
                )
            except Exception as e:
                logger.error(f"Error creating file URL: {e}")
                recording["file_url"] = None

        if recording.get("thumbnail_path"):
            try:
                abs_thumb_path = os.path.abspath(
                    os.path.expanduser(recording["thumbnail_path"])
                )
                abs_recordings_dir = os.path.abspath(
                    os.path.expanduser(recordings_directory)
                )
                rel_path = os.path.relpath(abs_thumb_path, abs_recordings_dir)
                recording["thumbnail_url"] = f"/recordings/{rel_path}"
                logger.info(
                    f"Created thumbnail URL: {recording['thumbnail_url']} from {recording['thumbnail_path']}"
                )
            except Exception as e:
                logger.error(f"Error creating thumbnail URL: {e}")
                recording["thumbnail_url"] = None

        return recording
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recording {recording_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
