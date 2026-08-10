"""Configuration management for video-feed."""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
import typer

from .constants import DEFAULT_PATHS


def create_config(
    bind_ip: str,
    paths: List[str],
    creds: Dict[str, str],
    tls_key: Optional[str] = None,
    tls_cert: Optional[str] = None
) -> Dict:
    """Create a MediaMTX configuration dictionary with optional TLS."""
    # Create paths configuration
    paths_config = {}
    for path in paths:
        paths_config[path] = {
            "source": creds["publish_user"]
        }
    
    # Create publisher permissions
    publisher_permissions = []
    for path in paths:
        publisher_permissions.append({"action": "publish", "path": path})
    
    # Create viewer permissions
    viewer_permissions = []
    for path in paths:
        viewer_permissions.append({"action": "read", "path": path})
        viewer_permissions.append({"action": "playback", "path": path})
    
    config = {
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
                "permissions": publisher_permissions
            },
            {
                "user": creds["read_user"],
                "pass": creds["read_pass"],
                "ips": [],
                "permissions": viewer_permissions
            }
        ],
    }

    if tls_key and tls_cert:
        # Phase 0: strict RTSPS only — clients must use rtsps://:8322
        config["rtspEncryption"] = "strict"
        config["rtspServerKey"] = tls_key
        config["rtspServerCert"] = tls_cert

    return config


def write_cfg(cfg_path: Path, bind_ip: str, paths: List[str], creds: Dict[str, str], 
             tls_key: Optional[str] = None, tls_cert: Optional[str] = None) -> None:
    """Generate mediamtx.yml at cfg_path."""
    config = create_config(bind_ip, paths, creds, tls_key, tls_cert)
    
    yaml_text = yaml.safe_dump(config)
    cfg_path.write_text(yaml_text)
    os.chmod(cfg_path, 0o600)


def load_config_paths(config_path: Path) -> List[str]:
    """Load paths from an existing mediamtx.yml file.
    
    Args:
        config_path: Path to existing mediamtx.yml file
        
    Returns:
        List of RTSP path strings
        
    Raises:
        typer.Exit: If paths cannot be loaded
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            
        paths_config = config.get("paths", {})
        if not paths_config:
            typer.secho("No paths found in configuration", fg=typer.colors.RED)
            raise typer.Exit(1)
            
        return list(paths_config.keys())
    except Exception as e:
        typer.secho(f"Failed to load paths: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


class SurveillanceConfig:
    """Unified configuration management for surveillance system."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration.
        
        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.config_data = {}
        
        if config_file and config_file.exists():
            self.load_from_file(config_file)
        else:
            self.load_defaults()
    
    def load_from_file(self, config_file: Path):
        """Load configuration from YAML file.
        
        Args:
            config_file: Path to YAML configuration file
        """
        try:
            with open(config_file, 'r') as f:
                self.config_data = yaml.safe_load(f) or {}
        except Exception as e:
            typer.secho(f"Error loading configuration: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
    
    def load_defaults(self):
        """Load default configuration values."""
        self.config_data = {
            'cameras': DEFAULT_PATHS,
            'network': {
                'bind': '127.0.0.1',
                # api_port removed: unauthenticated /paths side-server deleted (Phase 0)
            },
            'detection': {
                'enabled': True,
                'port': 8080,
                'model': 'yolov8n.pt',
                'confidence': 0.4,
                'resolution': {
                    'width': 960,
                    'height': 540
                }
            },
            'security': {
                'use_tls': True,
                'tls_key': '',
                'tls_cert': ''
            },
            'recording': {
                'enabled': True,
                'min_confidence': 0.5,
                'pre_buffer_seconds': 10,
                'post_buffer_seconds': 10,
                'max_storage_gb': 10.0,
                'recordings_dir': '~/video-feed-recordings',
                'record_objects': [],
                'codec': 'avc1'
            }
        }
    
    def get_cameras(self) -> List[str]:
        """Get camera stream paths."""
        return self.config_data.get('cameras', DEFAULT_PATHS)
    
    def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration."""
        return self.config_data.get('network', {})
    
    def get_detection_config(self) -> Dict[str, Any]:
        """Get detection configuration."""
        return self.config_data.get('detection', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return self.config_data.get('security', {})
    
    def get_recording_config(self) -> Dict[str, Any]:
        """Get recording configuration."""
        return self.config_data.get('recording', {})
    
    def get_bind_address(self) -> str:
        """Get bind address (default loopback until explicitly opened)."""
        return self.get_network_config().get('bind', '127.0.0.1')
    
    def get_api_port(self) -> Optional[int]:
        """Legacy paths API port — always None after Phase 0 removal of /paths."""
        return self.get_network_config().get('api_port')
    
    def is_detection_enabled(self) -> bool:
        """Check if detection is enabled."""
        return self.get_detection_config().get('enabled', True)
    
    def get_detection_port(self) -> int:
        """Get detection port."""
        return self.get_detection_config().get('port', 8080)
    
    def get_detection_model(self) -> str:
        """Get detection model."""
        return self.get_detection_config().get('model', 'yolov8n.pt')
    
    def get_detection_confidence(self) -> float:
        """Get detection confidence."""
        return self.get_detection_config().get('confidence', 0.4)
    
    def get_detection_resolution(self) -> tuple:
        """Get detection resolution."""
        res = self.get_detection_config().get('resolution', {})
        return (res.get('width', 960), res.get('height', 540))
    
    def get_tls_config(self) -> tuple:
        """Get TLS configuration.
        
        Returns:
            Tuple of (tls_key_path, tls_cert_path) or (None, None)
        """
        security = self.get_security_config()
        if not security.get('use_tls', False):
            return None, None
            
        tls_key = security.get('tls_key', '')
        tls_cert = security.get('tls_cert', '')
        
        if tls_key and tls_cert:
            return Path(tls_key), Path(tls_cert)
        
        return None, None
    
    def is_recording_enabled(self) -> bool:
        """Check if recording is enabled."""
        return self.get_recording_config().get('enabled', True)
    
    def get_recording_min_confidence(self) -> float:
        """Get minimum confidence for recording."""
        return self.get_recording_config().get('min_confidence', 0.5)
    
    def get_recording_pre_buffer(self) -> int:
        """Get pre-detection buffer seconds."""
        return self.get_recording_config().get('pre_buffer_seconds', 10)
    
    def get_recording_post_buffer(self) -> int:
        """Get post-detection buffer seconds."""
        return self.get_recording_config().get('post_buffer_seconds', 10)
    
    def get_recording_max_storage(self) -> float:
        """Get maximum storage in GB."""
        return self.get_recording_config().get('max_storage_gb', 10.0)
    
    def get_recordings_directory(self) -> str:
        """Get recordings directory.
        
        Returns:
            str: Path to recordings directory, with ~ expanded to user's home directory
        """
        path = self.get_recording_config().get('recordings_dir', '~/video-feed-recordings')
        # Ensure the path is expanded
        return os.path.expanduser(path)
    
    def get_record_objects(self) -> list:
        """Get list of objects to record.
        
        Returns:
            List of object classes to record. Empty list means record all objects.
        """
        return self.get_recording_config().get('record_objects', [])
    
    def get_recording_codec(self) -> str:
        """Get video codec for recordings.
        
        Returns:
            str: Video codec (e.g., 'avc1' for H.264, 'mp4v' for MPEG-4)
        """
        return self.get_recording_config().get('codec', 'avc1')
