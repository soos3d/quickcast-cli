"""Thin Typer CLI: serve, apikey, admin, reset, doctor, credentials.

Deprecated aliases: config, start, quick → serve.
Removed: run, detect (use serve).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import typer

from spectrax.credentials import (
    create_api_key,
    list_api_keys,
    reset_creds,
    revoke_api_key,
    set_admin_password,
)
from spectrax.paths import default_config_path, state_dir
from spectrax.utils import show_stream_credentials

app = typer.Typer(add_completion=False, help="SpectraX surveillance core")
admin_app = typer.Typer(help="Admin dashboard password management")
apikey_app = typer.Typer(help="API key management for machine clients")
credentials_app = typer.Typer(help="Reveal stream credentials (TTY)")
app.add_typer(admin_app, name="admin")
app.add_typer(apikey_app, name="apikey")
app.add_typer(credentials_app, name="credentials")


def _load_settings(config_file: Optional[Path]):
    from spectrax.config import load_settings, load_settings_or_default

    if config_file is not None:
        return load_settings(Path(config_file))
    return load_settings_or_default()


@app.command()
def serve(
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to spectrax.yml"
    ),
    host: Optional[str] = typer.Option(None, "--host", help="Override bind address"),
    port: Optional[int] = typer.Option(None, "--port", help="Override dashboard port"),
    no_mediamtx: bool = typer.Option(
        False, "--no-mediamtx", help="Do not spawn MediaMTX (use external unit)"
    ),
    no_detection: bool = typer.Option(
        False, "--no-detection", help="Skip detector/recording stack (API only)"
    ),
):
    """Start SpectraX (API is the main process; lifespan owns MediaMTX + detectors)."""
    import uvicorn

    from spectrax.app import create_app
    from spectrax.runtime import make_production_lifespan
    from spectrax.utils import print_urls
    from spectrax.credentials import get_credentials
    from spectrax.utils import detect_host_ip

    settings = _load_settings(config_file)
    updates = {}
    if host is not None:
        updates["network"] = settings.network.model_copy(update={"bind": host})
    if port is not None:
        updates["detection"] = settings.detection.model_copy(update={"port": port})
    if updates:
        settings = settings.model_copy(update=updates)

    manage_mediamtx = (not no_mediamtx) and settings.mediamtx.managed
    if manage_mediamtx:
        from spectrax.mediamtx.process import check_installed, MediaMTXError

        try:
            check_installed()
        except MediaMTXError as e:
            typer.secho(str(e), fg=typer.colors.RED)
            raise typer.Exit(1) from e

    lifespan = make_production_lifespan(
        settings,
        manage_mediamtx=manage_mediamtx,
        start_detection=not no_detection,
    )
    application = create_app(
        settings=settings,
        recordings_dir=settings.recording.expanded_recordings_dir(),
        enable_auth=True,
        secure_cookies=False,
        lifespan=lifespan,
    )

    bind = settings.network.bind
    dash_port = settings.detection.port
    display_host = detect_host_ip() if bind in ("0.0.0.0", "::") else bind
    typer.secho(
        f"Starting SpectraX at http://{display_host}:{dash_port}",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(f"  Config cameras: {', '.join(settings.cameras)}")
    typer.echo(f"  MediaMTX managed: {manage_mediamtx}")
    typer.echo(f"  Detection: {settings.detection.enabled and not no_detection}")
    try:
        creds = get_credentials()
        print_urls(display_host, list(settings.cameras), creds, rtsps=settings.security.use_tls)
    except Exception:
        pass
    typer.secho("Press Ctrl+C to stop.\n", fg=typer.colors.BRIGHT_BLACK)

    uvicorn.run(
        application,
        host=bind,
        port=dash_port,
        log_level="info",
        timeout_keep_alive=2,
        timeout_graceful_shutdown=5,
    )


@app.command()
def doctor(
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Check environment, config, and secrets readiness."""
    from spectrax import credentials as creds_mod
    from spectrax.config import load_settings, load_settings_or_default

    ok = True
    if sys.version_info < (3, 11):
        typer.secho("Python ≥3.11 required", fg=typer.colors.RED)
        ok = False
    else:
        typer.secho(f"Python {sys.version.split()[0]} OK", fg=typer.colors.GREEN)

    if shutil.which("mediamtx"):
        typer.secho("mediamtx on PATH OK", fg=typer.colors.GREEN)
    else:
        typer.secho("mediamtx not found on PATH", fg=typer.colors.RED)
        ok = False

    try:
        settings = (
            load_settings(config_file) if config_file else load_settings_or_default()
        )
        typer.secho(
            f"Config OK (bind={settings.network.bind}, port={settings.detection.port}, "
            f"mediamtx.managed={settings.mediamtx.managed})",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(f"Config load failed: {e}", fg=typer.colors.RED)
        ok = False

    sd = state_dir()
    if sd.exists() and os.access(sd, os.W_OK):
        typer.secho(f"State dir writable: {sd}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"State dir not writable: {sd}", fg=typer.colors.RED)
        ok = False

    if creds_mod.get_admin_password_hash():
        typer.secho("Admin password is set", fg=typer.colors.GREEN)
    else:
        typer.secho(
            "Admin password NOT set (run: spectrax admin set-password)",
            fg=typer.colors.YELLOW,
        )

    raise typer.Exit(0 if ok else 1)


@app.command()
def config(
    config_file: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Deprecated alias for ``serve``."""
    typer.secho(
        "Note: 'config' is deprecated; use 'spectrax serve'.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    serve(config_file=config_file or default_config_path())


@app.command()
def start(
    paths: List[str] = typer.Option([], "--path", "-p"),
    bind: str = typer.Option("127.0.0.1", "--bind"),
    detector_port: int = typer.Option(8080, "--detector-port"),
    no_detector: bool = typer.Option(False, "--no-detector"),
):
    """Deprecated alias for ``serve`` (flags mapped best-effort)."""
    typer.secho(
        "Note: 'start' is deprecated; use 'spectrax serve'.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    from spectrax.config import SpectraXSettings

    settings = SpectraXSettings(
        cameras=paths or ["video/camera-1"],
        network={"bind": bind},
        detection={"port": detector_port, "enabled": not no_detector},
    )
    # Write ephemeral? Just call serve with defaults and host override
    serve(host=bind, port=detector_port, no_detection=no_detector)


@app.command()
def quick(
    cameras: int = typer.Option(1, "--cameras", "-n"),
    detector: bool = typer.Option(True, "--detector/--no-detector"),
):
    """Deprecated quick start → ``serve`` with N default camera paths."""
    typer.secho(
        "Note: 'quick' is deprecated; use 'spectrax serve'.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    from spectrax.config import SpectraXSettings
    import tempfile
    import yaml

    paths = [f"video/camera-{i + 1}" for i in range(cameras)]
    data = SpectraXSettings(
        cameras=paths,
        detection={"enabled": detector},
    ).model_dump()
    tmp = Path(tempfile.mkdtemp(prefix="spectrax-quick-")) / "spectrax.yml"
    tmp.write_text(yaml.safe_dump(data), encoding="utf-8")
    serve(config_file=tmp, no_detection=not detector)


@app.command()
def reset():
    """Clear all stored secrets (stream + admin + API keys + session signing key)."""
    reset_creds()
    typer.echo("🔑 All credentials reset; stream secrets regenerate on next run.")
    typer.echo("   Re-set admin password: spectrax admin set-password")


@admin_app.command("set-password")
def admin_set_password(
    password: Optional[str] = typer.Option(
        None, "--password", "-p", help="Admin password (prompted if omitted)", hide_input=True
    ),
):
    """Set the dashboard admin password (argon2-hashed)."""
    if not password:
        password = typer.prompt("Admin password", hide_input=True, confirmation_prompt=True)
    try:
        set_admin_password(password)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1) from e
    typer.secho("Admin password saved.", fg=typer.colors.GREEN)


@apikey_app.command("create")
def apikey_create(
    name: str = typer.Option(..., "--name", "-n"),
    scope: str = typer.Option("read", "--scope", "-s", help="read or admin"),
):
    """Create an API key. Raw key is printed once."""
    try:
        raw = create_api_key(name=name, scope=scope)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1) from e
    typer.secho(
        "API key created. Store it now — it will not be shown again:",
        fg=typer.colors.YELLOW,
    )
    typer.echo(raw)


@apikey_app.command("list")
def apikey_list():
    """List API keys (metadata only)."""
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
def apikey_revoke(key_id: str = typer.Argument(..., help="Key id or name to revoke")):
    """Revoke an API key by id or name."""
    if revoke_api_key(key_id):
        typer.secho(f"Revoked: {key_id}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Key not found: {key_id}", fg=typer.colors.RED)
        raise typer.Exit(1)


@credentials_app.command("show-stream")
def credentials_show_stream(
    force: bool = typer.Option(False, "--force", help="Allow non-TTY print"),
):
    """Print MediaMTX publisher/viewer passwords (TTY only by default)."""
    show_stream_credentials(force=force)


if __name__ == "__main__":
    app()
