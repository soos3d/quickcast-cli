"""Detection subsystem."""

from .detector import DetectorManager, RTSPObjectDetector
from .config import DetectorConfig

__all__ = ["DetectorManager", "RTSPObjectDetector", "DetectorConfig"]
