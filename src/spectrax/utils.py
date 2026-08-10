"""Utility functions for video-feed."""

import socket
import sys
import typer
from pathlib import Path
from typing import Dict, List, Optional

from .constants import MEDIAMTX_BIN
from .paths import models_dir


def resolve_model_path(model_name: str) -> str:
    """Resolve YOLO model path to use package models directory.

    Args:
        model_name: Model filename (e.g., 'yolov8n.pt') or full path

    Returns:
        Full path to model file, or original if it's already a full path
    """
    model_path = Path(model_name)

    if model_path.is_absolute() or model_path.exists():
        return str(model_path)

    package_model_path = models_dir() / model_name

    if package_model_path.exists():
        return str(package_model_path)

    return model_name


def launch_mediamtx(cfg_path: Path) -> subprocess.Popen:
    """Launch the MediaMTX server with the given configuration."""
    from spectrax.mediamtx.process import MediaMTXError, launch

    try:
        return launch(Path(cfg_path))
    except MediaMTXError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from e


def detect_host_ip(prefer_iface: Optional[str] = None) -> str:
    """Return best-guess LAN IP, fallback to localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def check_mediamtx_installed(binary_name: str = MEDIAMTX_BIN) -> None:
    """Check if mediamtx binary is available and exit if not."""
    from spectrax.mediamtx.process import MediaMTXError, check_installed

    try:
        check_installed(binary_name)
    except MediaMTXError as e:
        typer.secho(str(e), fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from e


def print_urls(
    host: str, paths: List[str], creds: Dict[str, str], rtsps: bool = False
) -> None:
    """Print connection URLs for RTSP/HLS streams without embedding passwords.

    Passwords are never printed here. Operators retrieve them via:
    `surveillance credentials show-stream`
    """
    for i, path in enumerate(paths):
        if i > 0:
            typer.echo("\n" + "-" * 50 + "\n")

        typer.secho(f"\n📹 Stream Path: {path}", fg=typer.colors.YELLOW, bold=True)
        base_url = f"rtsp://{host}:8554/{path}"

        if rtsps:
            publish_url = f"rtsps://{host}:8322/{path}"
            typer.secho(
                "\n📲 Encrypted RTSPS Publishing:", fg=typer.colors.CYAN, bold=True
            )
            typer.echo(f"  URL: {publish_url}")
            typer.echo(f"  User: {creds['publish_user']}")
            typer.echo("  Pass: (use: surveillance credentials show-stream)")
        else:
            typer.secho("\n📲 RTSP Publishing:", fg=typer.colors.CYAN, bold=True)
            typer.echo(f"  URL: {base_url}")
            typer.echo(f"  User: {creds['publish_user']}")
            typer.echo("  Pass: (use: surveillance credentials show-stream)")

        typer.secho("\n📺 Encrypted RTSPS Viewing:", fg=typer.colors.GREEN, bold=True)
        view_url = f"rtsps://{host}:8322/{path}"
        typer.echo(f"  URL: {view_url}")
        typer.echo(f"  User: {creds['read_user']}")
        typer.echo("  Pass: (use: surveillance credentials show-stream)")
        typer.echo(f"  • VLC: File > Open Network > {view_url}")
        typer.echo(
            "  • OBS: Sources > + > Media Source > uncheck local file > paste URL"
        )

        typer.secho("\n🌐 HLS Viewing (browser):", fg=typer.colors.MAGENTA, bold=True)
        hls_url = f"http://{host}:8888/{path}/index.m3u8"
        typer.echo(f"  URL: {hls_url}")
        typer.echo(f"  Auth user: {creds['read_user']}")
        typer.echo("  Auth pass: (use: surveillance credentials show-stream)")

        typer.secho(
            "\n🎥 Unencrypted RTSP Connection Settings:",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"   URL: {base_url}")
        typer.echo(f"   Username: {creds['publish_user']}")
        typer.echo("   Password: (use: surveillance credentials show-stream)")


def show_stream_credentials(force: bool = False) -> None:
    """Print publisher/viewer stream passwords once (TTY only unless --force)."""
    from .credentials import get_credentials

    if not force and not sys.stdout.isatty():
        typer.secho(
            "Refusing to print secrets to a non-TTY. Pass --force to override.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    creds = get_credentials()
    typer.secho("Stream credentials (MediaMTX) — treat as secrets", fg=typer.colors.YELLOW)
    typer.echo(f"  Publisher user: {creds['publish_user']}")
    typer.echo(f"  Publisher pass: {creds['publish_pass']}")
    typer.echo(f"  Viewer user:    {creds['read_user']}")
    typer.echo(f"  Viewer pass:    {creds['read_pass']}")
