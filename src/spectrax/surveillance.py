"""Deprecated module path — use ``spectrax.cli`` / ``spectrax serve``.

Re-exports the Typer app for ``python -m spectrax.surveillance`` compatibility.
"""

from spectrax.cli import app

__all__ = ["app"]

if __name__ == "__main__":
    app()
