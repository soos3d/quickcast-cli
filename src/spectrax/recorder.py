"""Deprecated shim — use spectrax.recording.recorder."""
from spectrax.recording.recorder import *  # noqa: F403
from spectrax.recording.recorder import RecordingManager

__all__ = ["RecordingManager"]
