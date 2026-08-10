"""Deprecated shim — use spectrax.detection.config."""
from spectrax.detection.config import *  # noqa: F403
from spectrax.detection.config import AnnotatorConfig, DetectorConfig, TrackingConfig

__all__ = ["AnnotatorConfig", "DetectorConfig", "TrackingConfig"]
