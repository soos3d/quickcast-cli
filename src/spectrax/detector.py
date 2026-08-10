"""Deprecated shim — use spectrax.detection.detector."""
from spectrax.detection.detector import *  # noqa: F403
from spectrax.detection.detector import DetectorManager, RTSPObjectDetector

__all__ = ["DetectorManager", "RTSPObjectDetector"]
