"""MediaMTX process launch and shutdown."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from spectrax.constants import MEDIAMTX_BIN

logger = logging.getLogger("spectrax.mediamtx")


class MediaMTXError(RuntimeError):
    """MediaMTX binary missing or process failed."""


def check_installed(binary_name: str = MEDIAMTX_BIN) -> None:
    if shutil.which(binary_name) is None:
        raise MediaMTXError(
            f"'{binary_name}' not found on PATH. "
            "Install from https://github.com/bluenviron/mediamtx/releases"
        )


def launch(cfg_path: Path, binary_name: str = MEDIAMTX_BIN) -> subprocess.Popen:
    """Start MediaMTX with the given config file."""
    cfg_path = Path(cfg_path)
    if not cfg_path.is_file():
        raise MediaMTXError(f"MediaMTX config not found: {cfg_path}")
    check_installed(binary_name)
    proc = subprocess.Popen(
        [binary_name, str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Brief settle; fail fast if process exits immediately
    time.sleep(0.5)
    if proc.poll() is not None:
        stderr = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
        raise MediaMTXError(f"MediaMTX exited immediately: {stderr[:500]}")
    logger.info("MediaMTX started pid=%s config=%s", proc.pid, cfg_path)
    return proc


def stop(proc: Optional[subprocess.Popen], timeout: float = 5.0) -> None:
    """Terminate MediaMTX process if running."""
    if proc is None:
        return
    if proc.poll() is not None:
        return
    logger.info("Stopping MediaMTX pid=%s", proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("MediaMTX did not exit; killing")
        proc.kill()
        proc.wait(timeout=2)
