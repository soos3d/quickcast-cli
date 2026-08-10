"""Unified surveillance system launcher."""

import asyncio
import signal
import subprocess
import threading
import time
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict
import typer
import yaml

# Add the parent directory to sys.path to make videofeed importable
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now import from videofeed
from videofeed.credentials import (
    get_credentials,
    load_config_credentials,
    reset_creds,
    set_admin_password,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)
from videofeed.config import write_cfg, load_config_paths, SurveillanceConfig
from videofeed.utils import (
    detect_host_ip,
    check_mediamtx_installed,
    launch_mediamtx,
    print_urls,
    show_stream_credentials,
)
from videofeed.visualizer import start_visualizer
from videofeed.constants import DEFAULT_PATHS

app = typer.Typer(add_completion=False)
admin_app = typer.Typer(help="Admin dashboard password management")
apikey_app = typer.Typer(help="API key management for machine clients")
credentials_app = typer.Typer(help="Reveal stream credentials (TTY)")
app.add_typer(admin_app, name="admin")
app.add_typer(apikey_app, name="apikey")
app.add_typer(credentials_app, name="credentials")


class SurveillanceSystem:
    """Unified surveillance system manager."""
    
    def __init__(self):
        self.mediamtx_process = None
        self.detector_thread = None
        self.running = False
        self.config = {}
        
    def start_streaming_server(
        self,
        paths: List[str],
        bind: str,
        config_path: Optional[Path],
        tls_key: Optional[Path],
        tls_cert: Optional[Path],
    ) -> Dict:
        """Start the MediaMTX streaming server."""
        check_mediamtx_installed("mediamtx")
        
        # Use default TLS paths if not provided
        default_tls_key = Path(__file__).parent.parent / "server.key"
        default_tls_cert = Path(__file__).parent.parent / "server.crt"
        
        if not tls_key and default_tls_key.exists():
            tls_key = default_tls_key
        if not tls_cert and default_tls_cert.exists():
            tls_cert = default_tls_cert
            
        # Create configuration
        if config_path and config_path.exists():
            creds = load_config_credentials(config_path)
            config_paths = load_config_paths(config_path)
        else:
            import tempfile
            self.temp_dir = tempfile.mkdtemp(prefix="surveillance-")
            config_path = Path(self.temp_dir) / "mediamtx.yml"
            creds = get_credentials()
            write_cfg(
                config_path, 
                bind, 
                paths, 
                creds,
                tls_key=str(tls_key) if tls_key else None,
                tls_cert=str(tls_cert) if tls_cert else None
            )
            config_paths = paths
            
        # Launch MediaMTX
        self.mediamtx_process = launch_mediamtx(config_path)
        typer.echo("⏳ Starting streaming server...")
        
        # Wait for server to start
        import time
        time.sleep(1)  # Give it a moment to start
        
        # Check if process is still running
        if self.mediamtx_process.poll() is not None:
            # Process has terminated
            stdout, stderr = self.mediamtx_process.communicate()
            typer.secho("❌ MediaMTX failed to start!", fg=typer.colors.RED, bold=True)
            if stdout:
                typer.echo(f"STDOUT: {stdout.decode()}")
            if stderr:
                typer.echo(f"STDERR: {stderr.decode()}")
            raise typer.Exit(1)
            
        # Store configuration
        self.config = {
            "creds": creds,
            "paths": config_paths,
            "host_ip": detect_host_ip() if bind in ("0.0.0.0", "::") else bind,
            "bind": bind,
            "use_rtsps": tls_key is not None and tls_cert is not None
        }
        
        return self.config
        
    def start_detector(
        self,
        host: str,
        port: int,
        model: str,
        confidence: float,
        resolution: tuple,
        enable_recording: bool = True,
        recording_min_confidence: float = 0.5,
        recording_pre_buffer: int = 10,
        recording_post_buffer: int = 10,
        recordings_dir: Optional[str] = None,
        record_objects: List[str] = [],
        recording_codec: str = 'avc1'
    ):
        """Start the object detection service in a separate thread."""
        # Store recording configuration for status display
        self.recording_enabled = enable_recording
        self.recording_config = {
            'min_confidence': recording_min_confidence,
            'pre_buffer': recording_pre_buffer,
            'post_buffer': recording_post_buffer,
            'recordings_dir': recordings_dir,
            'record_objects': record_objects
        }
        
        def run_detector():
            # Build RTSP URLs from paths
            rtsp_urls = []
            for path in self.config["paths"]:
                if self.config["use_rtsps"]:
                    url = f"rtsps://{self.config['creds']['read_user']}:{self.config['creds']['read_pass']}@{self.config['host_ip']}:8322/{path}"
                else:
                    url = f"rtsp://{self.config['creds']['read_user']}:{self.config['creds']['read_pass']}@{self.config['host_ip']}:8554/{path}"
                rtsp_urls.append(url)
                
            # Silent - will show in final status
            # typer.echo(f"🎯 Starting object detection for {len(rtsp_urls)} streams...")
            
            # Import here to avoid circular imports
            from videofeed.detector import DetectorManager
            from videofeed.detector_config import DetectorConfig
            from videofeed.visualizer import app, set_detector_manager
            from videofeed.recorder import RecordingManager
            import uvicorn
            
            try:
                # Initialize recording manager if enabled
                recording_manager = None
                if enable_recording:
                    # Silent initialization - will show in final status
                    # typer.echo(f"📹 Initializing recording manager...")
                    recording_manager = RecordingManager(
                        recordings_dir=recordings_dir,
                        min_confidence=recording_min_confidence,
                        pre_detection_buffer=recording_pre_buffer,
                        post_detection_buffer=recording_post_buffer,
                        record_objects=record_objects,
                        codec=recording_codec
                    )
                    recording_manager.start()
                    # typer.echo(f"📹 Recording enabled - clips will be saved to {recording_manager.recordings_dir}")
                
                # Initialize detector manager
                detector_manager = DetectorManager(recording_manager=recording_manager)
                
                # Create detector configuration from surveillance config
                # This pulls all settings from config/surveillance.yml including:
                # - Model, confidence, resolution
                # - Stream buffer and reconnect settings
                # - Detection filters (classes, min/max area)
                # - Visual appearance (box color, label style)
                from videofeed.config import SurveillanceConfig
                config_path = Path(__file__).parent.parent / "config" / "surveillance.yml"
                surveillance_cfg = SurveillanceConfig(config_path)
                detector_config = DetectorConfig.from_surveillance_config(surveillance_cfg)
                
                # Add detectors for each URL
                for url in rtsp_urls:
                    detector_manager.add_detector(
                        source_url=url,
                        config=detector_config,
                        enable_recording=enable_recording
                    )
                
                # Set the detector manager in the visualizer module
                set_detector_manager(detector_manager)
                
                # Start FastAPI server without signal handlers
                config = uvicorn.Config(
                    app=app,
                    host=host,
                    port=port,
                    log_level="info"
                )
                
                server = uvicorn.Server(config)
                server.run()
            except Exception as e:
                typer.echo(f"Error in detector: {e}")
            
        self.detector_thread = threading.Thread(target=run_detector, daemon=True)
        self.detector_thread.start()
        
    def print_status(self):
        """Print system status and connection information."""
        typer.echo("\n" + "="*70)
        typer.secho("🎥 SURVEILLANCE SYSTEM READY", fg=typer.colors.GREEN, bold=True)
        typer.echo("="*70 + "\n")
        
        # Print active cameras
        typer.secho("📹 ACTIVE CAMERAS", fg=typer.colors.YELLOW, bold=True)
        for i, path in enumerate(self.config["paths"], 1):
            # Extract friendly name from path (e.g., "video/iphone" -> "iphone")
            camera_name = path.split('/')[-1]
            typer.echo(f"  {i}. {camera_name} ({path})")
        typer.echo()
        
        # Print web dashboard (most important)
        typer.secho("🌐 WEB DASHBOARD", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  → http://{self.config['host_ip']}:8080")
        typer.echo(f"     (Live view with AI detection)")
        typer.echo()
        
        # Print camera publishing info
        typer.secho("📱 PUBLISH FROM CAMERA", fg=typer.colors.CYAN, bold=True)
        typer.echo("  Use these credentials in your camera app (e.g., Larix Broadcaster):")
        typer.echo()
        protocol = "rtsps" if self.config["use_rtsps"] else "rtsp"
        port = "8322" if self.config["use_rtsps"] else "8554"
        typer.echo(f"  Server:   {protocol}://{self.config['host_ip']}:{port}/[your-stream-path]")
        typer.echo(f"  Username: {self.config['creds']['publish_user']}")
        typer.echo(f"  Password: {self.config['creds']['publish_pass']}")
        typer.echo()
        typer.secho(f"  Example: {protocol}://{self.config['host_ip']}:{port}/{self.config['paths'][0]}", 
                   fg=typer.colors.BRIGHT_BLACK)
        typer.echo()
        
        # Print viewer credentials
        typer.secho("👀 VIEW STREAMS (VLC, OBS, etc.)", fg=typer.colors.MAGENTA, bold=True)
        typer.echo("  Use these credentials to view streams:")
        typer.echo()
        typer.echo(f"  Username: {self.config['creds']['read_user']}")
        typer.echo(f"  Password: {self.config['creds']['read_pass']}")
        typer.echo()
        # Show example for first camera (no embedded passwords)
        if self.config["paths"]:
            camera_name = self.config["paths"][0].split('/')[-1]
            if self.config["use_rtsps"]:
                viewer_url = f"rtsps://{self.config['host_ip']}:8322/{self.config['paths'][0]}"
            else:
                viewer_url = f"rtsp://{self.config['host_ip']}:8554/{self.config['paths'][0]}"
            typer.secho(
                f"  Example ({camera_name}): {viewer_url}",
                fg=typer.colors.BRIGHT_BLACK,
            )
            typer.secho(
                "  Passwords: surveillance credentials show-stream",
                fg=typer.colors.BRIGHT_BLACK,
            )
        typer.echo()
        
        # Print recording info if enabled
        if hasattr(self, 'recording_enabled') and self.recording_enabled:
            typer.secho("📹 RECORDING", fg=typer.colors.BLUE, bold=True)
            typer.echo(f"  Status:     ✓ Enabled")
            typer.echo(f"  Directory:  {self.recording_config['recordings_dir']}")
            typer.echo(f"  Buffer:     {self.recording_config['pre_buffer']}s before / {self.recording_config['post_buffer']}s after detection")
            typer.echo(f"  Confidence: {self.recording_config['min_confidence']} minimum")
            
            # Show object filtering
            if self.recording_config['record_objects']:
                objects_str = ', '.join(self.recording_config['record_objects'])
                typer.echo(f"  Objects:    {objects_str}")
            else:
                typer.echo(f"  Objects:    All detected objects")
            typer.echo()
        
        # Advanced URLs (collapsed)
        typer.secho("🔗 ADVANCED", fg=typer.colors.BRIGHT_BLACK, bold=True)
        
        if len(self.config["paths"]) > 1:
            typer.echo("  All stream URLs (no passwords embedded):")
            for path in self.config["paths"]:
                camera_name = path.split('/')[-1]
                if self.config["use_rtsps"]:
                    url = f"rtsps://{self.config['host_ip']}:8322/{path}"
                else:
                    url = f"rtsp://{self.config['host_ip']}:8554/{path}"
                typer.echo(f"    • {camera_name}: {url}")
            typer.echo()
        
        typer.echo(f"  HLS streaming: http://{self.config['host_ip']}:8888/[stream-path]/index.m3u8")
        typer.echo("  Stream passwords: surveillance credentials show-stream")
            
        typer.echo("\n" + "="*70)
        typer.secho("Press Ctrl+C to stop", fg=typer.colors.BRIGHT_BLACK)
        typer.echo("="*70 + "\n")
        
    def shutdown(self):
        """Shutdown all services."""
        typer.echo("\n🛑 Shutting down surveillance system...")
        
        if self.mediamtx_process:
            self.mediamtx_process.terminate()
            self.mediamtx_process.wait()
            typer.echo("  ✓ Streaming server stopped")
            
        # Detector thread will stop automatically as it's daemon
        typer.echo("  ✓ Object detection stopped")
        
        # Clean up temp directory if it exists
        if hasattr(self, 'temp_dir'):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
        typer.echo("👋 Surveillance system stopped\n")


@app.command()
def config(
    config_file: Path = typer.Option(None, "--config", "-c", help="Configuration file path")
):
    """Start surveillance system using a configuration file."""
    
    # Use default config path if not provided
    if config_file is None:
        config_file = Path(__file__).parent.parent / "config" / "surveillance.yml"
    
    # Load configuration using unified config manager
    config = SurveillanceConfig(config_file)
    
    # Get TLS configuration
    tls_key, tls_cert = config.get_tls_config()
    
    # Call start with configuration values
    start(
        paths=config.get_cameras(),
        bind=config.get_bind_address(),
        config=None,  # Don't pass a config file since we're using direct values
        detector=config.is_detection_enabled(),
        detector_port=config.get_detection_port(),
        model=config.get_detection_model(),
        confidence=config.get_detection_confidence(),
        width=config.get_detection_resolution()[0],
        height=config.get_detection_resolution()[1],
        tls_key=tls_key,
        tls_cert=tls_cert,
        recording=config.is_recording_enabled(),
        recording_min_confidence=config.get_recording_min_confidence(),
        recording_pre_buffer=config.get_recording_pre_buffer(),
        recording_post_buffer=config.get_recording_post_buffer(),
        recordings_dir=config.get_recordings_directory(),
        record_objects=config.get_record_objects(),
        recording_codec=config.get_recording_codec(),
    )


@app.command()
def start(
    paths: List[str] = typer.Option(
        [],
        "--path", "-p",
        help="Camera stream paths"
    ),
    bind: str = typer.Option(
        "127.0.0.1",
        help="Bind IP for MediaMTX (default loopback; use 0.0.0.0 for LAN after auth is configured)",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Custom config file"),
    detector: bool = typer.Option(True, "--detector/--no-detector", help="Enable object detection"),
    detector_port: int = typer.Option(8080, "--detector-port", help="Object detection web port"),
    model: str = typer.Option("yolov8n.pt", "--model", "-m", help="YOLO model"),
    confidence: float = typer.Option(0.4, "--confidence", help="Detection confidence"),
    width: int = typer.Option(960, "--width", help="Video width"),
    height: int = typer.Option(540, "--height", help="Video height"),
    tls_key: Optional[Path] = typer.Option(None, help="TLS key path"),
    tls_cert: Optional[Path] = typer.Option(None, help="TLS certificate path"),
    recording: bool = typer.Option(True, "--recording/--no-recording", help="Enable recording"),
    recording_min_confidence: float = typer.Option(0.5, "--recording-confidence", help="Minimum confidence for recording"),
    recording_pre_buffer: int = typer.Option(10, "--pre-buffer", help="Pre-detection buffer seconds"),
    recording_post_buffer: int = typer.Option(10, "--post-buffer", help="Post-detection buffer seconds"),
    recordings_dir: Optional[str] = typer.Option(None, "--recordings-dir", help="Recordings directory"),
    record_objects: List[str] = typer.Option([], "--record-objects", help="List of object classes to record (empty means all)"),
    recording_codec: str = typer.Option("avc1", "--recording-codec", help="Video codec for recordings (avc1=H.264, mp4v=MPEG-4)"),
):
    """Start the unified surveillance system with streaming and object detection."""
    
    # Use default paths if none provided
    if not paths:
        paths = ["video/camera-1"]
    
    system = SurveillanceSystem()
    
    try:
        # Start streaming server
        system.start_streaming_server(
            paths=paths,
            bind=bind,
            config_path=config,
            tls_key=tls_key,
            tls_cert=tls_cert,
        )
        
        # Start detector if enabled
        if detector:
            time.sleep(1)  # Give server a moment to stabilize
            system.start_detector(
                host=bind,
                port=detector_port,
                model=model,
                confidence=confidence,
                resolution=(width, height),
                enable_recording=recording,
                recording_min_confidence=recording_min_confidence,
                recording_pre_buffer=recording_pre_buffer,
                recording_post_buffer=recording_post_buffer,
                recordings_dir=recordings_dir,
                record_objects=record_objects,
                recording_codec=recording_codec
            )
            time.sleep(2)  # Give detector time to initialize
            
        # Print status
        system.print_status()
        
        # Wait for interrupt
        signal.pause()
        
    except KeyboardInterrupt:
        pass
    finally:
        system.shutdown()


@app.command()
def quick(
    cameras: int = typer.Option(1, "--cameras", "-n", help="Number of cameras"),
    detector: bool = typer.Option(True, "--detector/--no-detector", help="Enable object detection"),
):
    """Quick start with default settings for N cameras."""
    
    # Generate camera paths
    paths = [f"video/camera-{i+1}" for i in range(cameras)]
    
    typer.secho(f"🚀 Quick starting surveillance with {cameras} camera(s)...", fg=typer.colors.GREEN, bold=True)
    
    # Call start with defaults (loopback bind; no /paths side-server)
    start(
        paths=paths,
        bind="127.0.0.1",
        detector=detector,
        detector_port=8080,
    )


@app.command()
def run(
    paths: List[str] = typer.Option(DEFAULT_PATHS, "--path", "-p", help="Logical RTSP path(s) to publish/view. Can be specified multiple times."),
    bind: str = typer.Option(
        "127.0.0.1",
        help="Bind IP (default loopback; use 0.0.0.0 for LAN).",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to pre-made mediamtx.yml"),
    tls_key: Optional[Path] = typer.Option(None, help="Path to TLS private key for RTSPS."),
    tls_cert: Optional[Path] = typer.Option(None, help="Path to TLS certificate for RTSPS."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show server configuration details."),
) -> None:
    """Start RTSP/HLS micro-server and display connection info (no object detection)."""
    import contextlib
    import tempfile

    check_mediamtx_installed("mediamtx")

    # Use default TLS paths if not provided
    default_tls_key = Path(__file__).parent.parent / "server.key"
    default_tls_cert = Path(__file__).parent.parent / "server.crt"

    if not tls_key and default_tls_key.exists():
        tls_key = default_tls_key
    if not tls_cert and default_tls_cert.exists():
        tls_cert = default_tls_cert

    tls_key_path = None
    tls_cert_path = None
    use_rtsps = False

    # Validate TLS files
    if tls_key and tls_cert:
        if not tls_key.exists():
            typer.secho(f"TLS key not found: {tls_key}", fg=typer.colors.RED)
            raise typer.Exit(1)
        if not tls_cert.exists():
            typer.secho(f"TLS cert not found: {tls_cert}", fg=typer.colors.RED)
            raise typer.Exit(1)
        tls_key_path = str(tls_key)
        tls_cert_path = str(tls_cert)
        use_rtsps = True
    elif tls_key or tls_cert:
        typer.secho("Error: both --tls-key and --tls-cert must be provided for RTSPS.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Configuration context
    if config:
        cfg_path = config
        creds = load_config_credentials(cfg_path)
        config_paths = load_config_paths(cfg_path)
        temp_context = contextlib.nullcontext()
    else:
        temp_context = tempfile.TemporaryDirectory(prefix="video-feed-")

    with temp_context as tmpdir:
        if not config:
            cfg_path = Path(tmpdir) / "mediamtx.yml"
            creds = get_credentials()
            write_cfg(cfg_path, bind, paths, creds, tls_key=tls_key_path, tls_cert=tls_cert_path)
            config_paths = paths

        if verbose:
            typer.secho("MediaMTX Configuration:", fg=typer.colors.BRIGHT_BLUE, bold=True)
            typer.secho(f"Config file: {cfg_path}", fg=typer.colors.BLUE)
            # Redact passwords from verbose dump
            redacted = cfg_path.read_text()
            for secret in (creds.get("publish_pass"), creds.get("read_pass")):
                if secret:
                    redacted = redacted.replace(secret, "***")
            typer.echo(redacted)

        server = launch_mediamtx(cfg_path)
        typer.echo("⏳ Starting MediaMTX ...")
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass  # Expected: server is running

        host_ip = detect_host_ip() if bind in ("0.0.0.0", "::") else bind
        print_urls(host_ip, config_paths, creds, rtsps=use_rtsps)

        typer.secho("Press Ctrl+C to quit.\n", fg=typer.colors.BRIGHT_BLACK)
        try:
            signal.pause()
        except KeyboardInterrupt:
            typer.echo("\nShutting down ...")
            server.terminate()
            server.wait()


@app.command()
def reset():
    """Clear all stored secrets (stream + admin + API keys + session signing key)."""
    reset_creds()
    typer.echo("🔑 All credentials reset; stream secrets regenerate on next run.")
    typer.echo("   Re-set admin password: surveillance admin set-password")


@admin_app.command("set-password")
def admin_set_password(
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        help="Admin password (prompted if omitted)",
        hide_input=True,
    ),
):
    """Set the dashboard admin password (argon2-hashed in keyring)."""
    if not password:
        password = typer.prompt("Admin password", hide_input=True, confirmation_prompt=True)
    try:
        set_admin_password(password)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("Admin password saved.", fg=typer.colors.GREEN)


@apikey_app.command("create")
def apikey_create(
    name: str = typer.Option(..., "--name", "-n", help="Key name/label"),
    scope: str = typer.Option("read", "--scope", "-s", help="read or admin"),
):
    """Create an API key. Raw key is printed once."""
    try:
        raw = create_api_key(name=name, scope=scope)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("API key created. Store it now — it will not be shown again:", fg=typer.colors.YELLOW)
    typer.echo(raw)


@apikey_app.command("list")
def apikey_list():
    """List API keys (metadata only; no secrets)."""
    keys = list_api_keys(include_revoked=True)
    if not keys:
        typer.echo("No API keys.")
        return
    for k in keys:
        status = "revoked" if k.get("revoked_at") else "active"
        typer.echo(
            f"  {k.get('id')}  name={k.get('name')}  scope={k.get('scope')}  "
            f"status={status}  created={k.get('created_at')}"
        )


@apikey_app.command("revoke")
def apikey_revoke(
    key_id: str = typer.Argument(..., help="Key id or name to revoke"),
):
    """Revoke an API key by id or name."""
    if revoke_api_key(key_id):
        typer.secho(f"Revoked: {key_id}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Key not found: {key_id}", fg=typer.colors.RED)
        raise typer.Exit(1)


@credentials_app.command("show-stream")
def credentials_show_stream(
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow printing secrets when stdout is not a TTY",
    ),
):
    """Print MediaMTX publisher/viewer passwords (TTY only by default)."""
    show_stream_credentials(force=force)


@app.command()
def detect(
    rtsp_urls: List[str] = typer.Option([], "--rtsp-url", "-r", help="RTSP URL with credentials (can be specified multiple times)"),
    paths: List[str] = typer.Option([], "--path", "-p", help="Logical RTSP path to view (can be specified multiple times)"),
    host: str = typer.Option("127.0.0.1", "--host", "--host-ip", help="Host to bind the visualization server"),
    port: int = typer.Option(8000, "--port", help="Port to bind the visualization server"),
    model: str = typer.Option("yolov8n.pt", "--model", "-m", help="YOLO model to use"),
    confidence: float = typer.Option(0.4, "--confidence", "-c", help="Detection confidence threshold"),
    width: int = typer.Option(960, "--width", help="Output video width"),
    height: int = typer.Option(540, "--height", help="Output video height"),
    recording: bool = typer.Option(False, "--record", help="Enable recording of detected objects"),
    recordings_dir: Optional[Path] = typer.Option(None, "--recordings-dir", help="Directory to store recordings (default: ~/video-feed-recordings)"),
    min_confidence: float = typer.Option(0.5, "--min-record-confidence", help="Minimum confidence to trigger recording"),
    pre_buffer: int = typer.Option(5, "--pre-buffer", help="Seconds of video to keep before detection"),
    post_buffer: int = typer.Option(5, "--post-buffer", help="Seconds of video to keep after last detection")
) -> None:
    """Start object detection visualizer with multiple RTSP streams."""
    # Check if either rtsp_urls or paths are provided
    if not rtsp_urls and not paths:
        typer.secho("Error: Either --rtsp-url or --path must be provided at least once.", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    # Get credentials for paths
    if paths:
        creds = get_credentials()
        # Detect host IP
        host_ip = detect_host_ip()
        
    # Collect all URLs to process
    all_urls = list(rtsp_urls)  # Start with explicit URLs
    
    # For each path, construct the RTSPS URL with credentials
    for path in paths:
        # Construct RTSPS URL (encrypted)
        path_url = f"rtsps://{creds['read_user']}:{creds['read_pass']}@{host_ip}:8322/{path}"
        all_urls.append(path_url)
        typer.echo(f"Added RTSPS URL for path '{path}': {path_url.split('@')[0]}@***/{path}")
    
    # Define the resolution
    resolution = (width, height)
    
    try:
        # Start the visualizer
        typer.secho(f"Starting object detection visualizer at http://{host}:{port}", fg=typer.colors.GREEN)
        typer.secho(f"Using model: {model} with confidence: {confidence}", fg=typer.colors.BLUE)
        typer.secho(f"Processing {len(all_urls)} streams", fg=typer.colors.YELLOW)
        
        # Log each stream being processed (with masked credentials)
        for i, url in enumerate(all_urls):
            protocol = url.split('://')[0] if '://' in url else 'rtsp'
            masked = f"{protocol}://***:***@" + (url.split('@')[-1] if '@' in url else url)
            typer.secho(f"  Stream {i+1}: {masked}", fg=typer.colors.BRIGHT_BLACK)
            
        typer.secho("Press Ctrl+C once to exit cleanly.", fg=typer.colors.BRIGHT_BLACK)
        
        # Start the visualizer with all URLs
        start_visualizer(
            rtsp_urls=all_urls,
            host=host,
            port=port,
            model_path=model,
            confidence=confidence,
            resolution=resolution,
            enable_recording=recording,
            recordings_dir=str(recordings_dir) if recordings_dir else None,
            min_confidence=min_confidence,
            pre_detection_buffer=pre_buffer,
            post_detection_buffer=post_buffer
        )
        
        # Display recording info if enabled
        if recording:
            recordings_path = recordings_dir or Path.home() / "video-feed-recordings"
            typer.secho(f"\n📹 Recording enabled - video clips will be saved when objects are detected", fg=typer.colors.GREEN)
            typer.secho(f"   📂 Recordings directory: {recordings_path}", fg=typer.colors.BLUE)
            typer.secho(f"   🎯 Minimum recording confidence: {min_confidence}", fg=typer.colors.BLUE)
            typer.secho(f"   ⏪ Pre-detection buffer: {pre_buffer} seconds", fg=typer.colors.BLUE)
            typer.secho(f"   ⏩ Post-detection buffer: {post_buffer} seconds", fg=typer.colors.BLUE)
            typer.secho(f"   🌐 Recordings API: http://{host}:{port}/recordings", fg=typer.colors.BLUE)
    except KeyboardInterrupt:
        # Let the visualizer handle cleanup, then exit normally
        typer.secho("\nExiting...", fg=typer.colors.YELLOW)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
