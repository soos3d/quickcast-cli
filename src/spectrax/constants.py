"""Shared constants for the spectrax package."""

# Application constants.
# APP_NAME stays "video-feed" so KEYCHAIN_SERVICE remains "video-feed-mediamtx"
# and existing Phase 0 keychain secrets keep resolving after the package rename.
APP_NAME = "video-feed"
KEYCHAIN_SERVICE = f"{APP_NAME}-mediamtx"

# Default configuration
DEFAULT_PATHS = ["video/camera-1"]
MEDIAMTX_BIN = "mediamtx"

# Network defaults
DEFAULT_RTSP_PORT = 8554
DEFAULT_RTSPS_PORT = 8322
DEFAULT_HLS_PORT = 8888
DEFAULT_API_PORT = 3333
DEFAULT_DETECTOR_PORT = 8080

# Recording defaults
DEFAULT_CONFIDENCE = 0.4
DEFAULT_RESOLUTION = (960, 540)
DEFAULT_FPS = 30
