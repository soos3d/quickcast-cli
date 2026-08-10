"""Statistics and analytics routes."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from spectrax.api.deps import get_detector_manager, get_recordings_api, get_recordings_dir
from spectrax.auth_gate import AuthPrincipal, require_read

router = APIRouter(prefix="/api", tags=["statistics"])

logger = logging.getLogger(__name__)


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(100, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    object_type: Optional[str] = None,
    min_confidence: float = Query(0.5, ge=0, le=1.0),
    recordings_api: Any = Depends(get_recordings_api),
    recordings_directory: Path = Depends(get_recordings_dir),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detection alerts from recordings, for event monitoring."""
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
        rec_dir = str(recordings_directory)
        for alert in alerts:
            if alert.get("thumbnail_path"):
                try:
                    abs_thumb_path = os.path.abspath(
                        os.path.expanduser(alert["thumbnail_path"])
                    )
                    abs_recordings_dir = os.path.abspath(os.path.expanduser(rec_dir))
                    rel_path = os.path.relpath(abs_thumb_path, abs_recordings_dir)
                    alert["thumbnail_url"] = f"/recordings/{rel_path}"
                except Exception as e:
                    logger.error("Error creating thumbnail URL for alert: %s", e)
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
        logger.error("Error retrieving alerts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/stats/objects")
async def get_object_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stream_id: Optional[str] = None,
    recordings_api: Any = Depends(get_recordings_api),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get statistics about detected objects over time."""
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
        logger.error("Error retrieving object statistics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/stats/times")
async def get_time_stats(
    object_type: Optional[str] = None,
    days: int = Query(7, gt=0, le=90),
    stream_id: Optional[str] = None,
    recordings_api: Any = Depends(get_recordings_api),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get detection statistics by time of day."""
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
        logger.error("Error retrieving time statistics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/streams")
async def get_streams(
    request: Request,
    detector_manager: Any = Depends(get_detector_manager),
    _principal: AuthPrincipal = Depends(require_read),
):
    """Get list of all video streams with recording statistics."""
    try:
        streams = detector_manager.get_detector_status()
        recordings_api = getattr(request.app.state, "recordings_api", None)
        if recordings_api is None:
            for stream in streams.values():
                stream["recording_stats"] = None
            return {"streams": list(streams.values())}

        for stream_id, stream in streams.items():
            stream["recording_stats"] = recordings_api.get_stream_stats(stream_id)
        return {"streams": list(streams.values())}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving streams: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
