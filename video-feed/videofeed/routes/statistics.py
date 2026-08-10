"""Statistics and analytics routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from videofeed.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/api", tags=["statistics"])

logger = logging.getLogger(__name__)

# Global references (set by visualizer)
recordings_api = None
detector_manager = None


def set_recordings_api(api):
    """Set the recordings API instance."""
    global recordings_api
    recordings_api = api


def set_detector_manager(manager):
    """Set the detector manager instance."""
    global detector_manager
    detector_manager = manager


def reset_statistics_state():
    """Reset module globals (tests)."""
    global recordings_api, detector_manager
    recordings_api = None
    detector_manager = None


def initialize_recordings_api():
    """Initialize the recordings API if not already initialized."""
    global recordings_api

    if recordings_api is not None:
        return True

    try:
        from videofeed.api import RecordingsAPI
        import os

        home_db_path = os.path.expanduser("~/video-feed-recordings/recordings.db")
        logger.info(f"Looking for database at home path: {home_db_path}")

        if os.path.exists(home_db_path):
            logger.info(
                f"Initializing recordings API with database from home directory: {home_db_path}"
            )
            recordings_api = RecordingsAPI(db_path=home_db_path)
            logger.info("Successfully initialized recordings API from home directory")
            return True

        logger.error("Database file not found in home directory")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize recordings API: {e}")
        return False


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(100, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    object_type: Optional[str] = None,
    min_confidence: float = Query(0.5, ge=0, le=1.0),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detection alerts from recordings, for event monitoring."""
    global recordings_api

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

    try:
        alerts = recordings_api.get_alerts(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            object_type=object_type,
            min_confidence=min_confidence,
        )

        total = recordings_api.get_alerts_count(
            start_date=start_date,
            end_date=end_date,
            object_type=object_type,
            min_confidence=min_confidence,
        )

        import os

        recordings_directory = os.path.expanduser("~/video-feed-recordings")

        for alert in alerts:
            if alert.get("thumbnail_path"):
                try:
                    abs_thumb_path = os.path.abspath(
                        os.path.expanduser(alert["thumbnail_path"])
                    )
                    abs_recordings_dir = os.path.abspath(
                        os.path.expanduser(recordings_directory)
                    )
                    rel_path = os.path.relpath(abs_thumb_path, abs_recordings_dir)
                    alert["thumbnail_url"] = f"/recordings/{rel_path}"
                except Exception as e:
                    logger.error(f"Error creating thumbnail URL for alert: {e}")
                    alert["thumbnail_url"] = None

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "alerts": alerts,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/objects")
async def get_object_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stream_id: Optional[str] = None,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get statistics about detected objects over time."""
    global recordings_api

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

    try:
        stats = recordings_api.get_object_stats(
            start_date=start_date,
            end_date=end_date,
            stream_id=stream_id,
        )
        return {"stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving object statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/times")
async def get_time_stats(
    object_type: Optional[str] = None,
    days: int = Query(7, gt=0, le=90),
    stream_id: Optional[str] = None,
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detection statistics by time of day."""
    global recordings_api

    if not initialize_recordings_api():
        raise HTTPException(status_code=503, detail="Recording API not initialized")

    try:
        stats = recordings_api.get_time_stats(
            object_type=object_type,
            days=days,
            stream_id=stream_id,
        )
        return {"stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving time statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/streams")
async def get_streams(
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get list of all video streams with recording statistics."""
    global detector_manager, recordings_api

    if detector_manager is None:
        raise HTTPException(status_code=503, detail="Detector manager not initialized")

    if not initialize_recordings_api():
        streams = detector_manager.get_detector_status()
        for stream in streams.values():
            stream["recording_stats"] = None
        return {"streams": list(streams.values())}

    try:
        streams = detector_manager.get_detector_status()
        for stream_id, stream in streams.items():
            stats = recordings_api.get_stream_stats(stream_id)
            stream["recording_stats"] = stats

        return {"streams": list(streams.values())}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving streams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
