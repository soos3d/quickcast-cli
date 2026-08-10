"""Configuration: MediaMTX helpers + pydantic-settings SpectraXSettings."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer
import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .constants import DEFAULT_PATHS
from .paths import default_config_path


# ---------------------------------------------------------------------------
# MediaMTX config generation (unchanged behavior)
# ---------------------------------------------------------------------------


def create_config(
    bind_ip: str,
    paths: List[str],
    creds: Dict[str, str],
    tls_key: Optional[str] = None,
    tls_cert: Optional[str] = None,
) -> Dict:
    """Create a MediaMTX configuration dictionary with optional TLS."""
    paths_config = {path: {"source": creds["publish_user"]} for path in paths}
    publisher_permissions = [{"action": "publish", "path": path} for path in paths]
    viewer_permissions = []
    for path in paths:
        viewer_permissions.append({"action": "read", "path": path})
        viewer_permissions.append({"action": "playback", "path": path})

    config: Dict[str, Any] = {
        "paths": paths_config,
        "rtspAddress": f"{bind_ip}:8554",
        "rtsp": True,
        "hls": True,
        "rtspTransports": ["tcp"],
        "authInternalUsers": [
            {
                "user": creds["publish_user"],
                "pass": creds["publish_pass"],
                "ips": [],
                "permissions": publisher_permissions,
            },
            {
                "user": creds["read_user"],
                "pass": creds["read_pass"],
                "ips": [],
                "permissions": viewer_permissions,
            },
        ],
    }

    if tls_key and tls_cert:
        config["rtspEncryption"] = "strict"
        config["rtspServerKey"] = tls_key
        config["rtspServerCert"] = tls_cert

    return config


def write_cfg(
    cfg_path: Path,
    bind_ip: str,
    paths: List[str],
    creds: Dict[str, str],
    tls_key: Optional[str] = None,
    tls_cert: Optional[str] = None,
) -> None:
    """Generate mediamtx.yml at cfg_path."""
    config = create_config(bind_ip, paths, creds, tls_key, tls_cert)
    cfg_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    os.chmod(cfg_path, 0o600)


def load_config_paths(config_path: Path) -> List[str]:
    """Load path names from an existing mediamtx.yml file."""
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        paths_config = config.get("paths", {})
        if not paths_config:
            typer.secho("No paths found in configuration", fg=typer.colors.RED)
            raise typer.Exit(1)
        return list(paths_config.keys())
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"Failed to load paths: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# pydantic-settings model
# ---------------------------------------------------------------------------


def _empty_list_to_none(v: Any) -> Any:
    """Treat [] as None ("all") for class-filter fields."""
    if v is None:
        return None
    if isinstance(v, list) and len(v) == 0:
        return None
    return v


class NetworkConfig(BaseModel):
    bind: str = "127.0.0.1"


class DetectionResolution(BaseModel):
    width: int = 960
    height: int = 540


class DetectionStreamConfig(BaseModel):
    buffer_size: int = 10
    reconnect_interval: int = 5


class DetectionFilters(BaseModel):
    classes: Optional[List[str]] = None
    min_area: Optional[int] = None
    max_area: Optional[int] = None

    @field_validator("classes", mode="before")
    @classmethod
    def classes_empty_to_none(cls, v: Any) -> Any:
        return _empty_list_to_none(v)


class DetectionTrackingConfig(BaseModel):
    enabled: bool = True
    track_thresh: float = 0.25
    track_buffer: int = 30
    match_thresh: float = 0.8
    frame_rate: int = 30


class DetectionConfig(BaseModel):
    enabled: bool = True
    port: int = 8080
    model: str = "yolov8n.pt"
    confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    resolution: DetectionResolution = Field(default_factory=DetectionResolution)
    stream: DetectionStreamConfig = Field(default_factory=DetectionStreamConfig)
    filters: DetectionFilters = Field(default_factory=DetectionFilters)
    tracking: DetectionTrackingConfig = Field(default_factory=DetectionTrackingConfig)


class AppearanceBox(BaseModel):
    thickness: int = 2
    color: str = "green"


class AppearanceLabel(BaseModel):
    text_scale: float = 0.5
    text_thickness: int = 1
    text_padding: int = 10
    position: str = "top_left"
    border_radius: int = 0


class AppearanceConfig(BaseModel):
    box: AppearanceBox = Field(default_factory=AppearanceBox)
    label: AppearanceLabel = Field(default_factory=AppearanceLabel)


class RecordingConfig(BaseModel):
    enabled: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    pre_buffer_seconds: int = 10
    post_buffer_seconds: int = 10
    max_storage_gb: float = 10.0
    recordings_dir: str = "~/video-feed-recordings"
    record_objects: Optional[List[str]] = None
    codec: str = "avc1"

    @field_validator("record_objects", mode="before")
    @classmethod
    def record_objects_empty_to_none(cls, v: Any) -> Any:
        return _empty_list_to_none(v)

    def expanded_recordings_dir(self) -> str:
        return os.path.expanduser(self.recordings_dir)


class SecurityConfig(BaseModel):
    use_tls: bool = True
    tls_key: str = ""
    tls_cert: str = ""


class MediamtxConfig(BaseModel):
    """Process ownership for MediaMTX."""

    managed: bool = True  # True: lifespan/CLI spawns child; False: external unit


class SpectraXSettings(BaseSettings):
    """Validated application settings (YAML + SPECTRAX_* env overrides)."""

    model_config = SettingsConfigDict(
        env_prefix="SPECTRAX_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    cameras: List[str] = Field(default_factory=lambda: list(DEFAULT_PATHS))
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
    recording: RecordingConfig = Field(default_factory=RecordingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    mediamtx: MediamtxConfig = Field(default_factory=MediamtxConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # First source wins: env overrides YAML/init kwargs.
        return env_settings, init_settings, dotenv_settings, file_secret_settings


def load_settings(path: Path | None = None) -> SpectraXSettings:
    """Load settings from YAML (optional) with env overrides.

    Args:
        path: Config file path. ``None`` uses defaults only (+ env).
              Explicit missing path raises ``FileNotFoundError``.
    """
    data: Dict[str, Any] = {}
    if path is not None:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config root must be a mapping: {path}")
        data = loaded
    return SpectraXSettings(**data)


def load_settings_or_default(path: Path | None = None) -> SpectraXSettings:
    """Load settings; if path is None, try default_config_path() when present."""
    if path is not None:
        return load_settings(path)
    default = default_config_path()
    if default.is_file():
        return load_settings(default)
    return load_settings(None)


# ---------------------------------------------------------------------------
# Legacy adapter (deprecated — delete after CLI fully on SpectraXSettings)
# ---------------------------------------------------------------------------


class SurveillanceConfig:
    """Deprecated adapter over SpectraXSettings for pre-Phase-2 callers."""

    def __init__(self, config_file: Optional[Path] = None):
        warnings.warn(
            "SurveillanceConfig is deprecated; use load_settings() / SpectraXSettings",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config_file = config_file
        try:
            if config_file is not None and Path(config_file).is_file():
                self.settings = load_settings(Path(config_file))
            elif config_file is None:
                self.settings = load_settings(None)
            else:
                # Missing explicit path: fall back to defaults (old behavior)
                self.settings = load_settings(None)
        except Exception as e:
            typer.secho(f"Error loading configuration: {e}", fg=typer.colors.RED)
            raise typer.Exit(1) from e
        self.config_data = self.settings.model_dump()

    def load_from_file(self, config_file: Path) -> None:
        self.settings = load_settings(Path(config_file))
        self.config_data = self.settings.model_dump()
        self.config_file = config_file

    def load_defaults(self) -> None:
        self.settings = load_settings(None)
        self.config_data = self.settings.model_dump()

    def get_cameras(self) -> List[str]:
        return list(self.settings.cameras)

    def get_network_config(self) -> Dict[str, Any]:
        return self.settings.network.model_dump()

    def get_detection_config(self) -> Dict[str, Any]:
        return self.settings.detection.model_dump()

    def get_security_config(self) -> Dict[str, Any]:
        return self.settings.security.model_dump()

    def get_recording_config(self) -> Dict[str, Any]:
        return self.settings.recording.model_dump()

    def get_bind_address(self) -> str:
        return self.settings.network.bind

    def get_api_port(self) -> Optional[int]:
        return None

    def is_detection_enabled(self) -> bool:
        return self.settings.detection.enabled

    def get_detection_port(self) -> int:
        return self.settings.detection.port

    def get_detection_model(self) -> str:
        return self.settings.detection.model

    def get_detection_confidence(self) -> float:
        return self.settings.detection.confidence

    def get_detection_resolution(self) -> tuple:
        r = self.settings.detection.resolution
        return (r.width, r.height)

    def get_tls_config(self) -> Tuple[Optional[Path], Optional[Path]]:
        sec = self.settings.security
        if not sec.use_tls:
            return None, None
        if sec.tls_key and sec.tls_cert:
            return Path(sec.tls_key), Path(sec.tls_cert)
        return None, None

    def is_recording_enabled(self) -> bool:
        return self.settings.recording.enabled

    def get_recording_min_confidence(self) -> float:
        return self.settings.recording.min_confidence

    def get_recording_pre_buffer(self) -> int:
        return self.settings.recording.pre_buffer_seconds

    def get_recording_post_buffer(self) -> int:
        return self.settings.recording.post_buffer_seconds

    def get_recording_max_storage(self) -> float:
        return self.settings.recording.max_storage_gb

    def get_recordings_directory(self) -> str:
        return self.settings.recording.expanded_recordings_dir()

    def get_record_objects(self) -> list:
        """Empty list means record all (legacy). Settings None → []."""
        objs = self.settings.recording.record_objects
        return list(objs) if objs is not None else []

    def get_recording_codec(self) -> str:
        return self.settings.recording.codec
