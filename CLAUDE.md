# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The installable package lives under **`src/spectrax/`** (import name `spectrax`).
Install from the repo root with an editable install — do **not** set `PYTHONPATH`.

```
src/spectrax/          # Python package
config/spectrax.yml    # example config (no secrets)
models/                # YOLO weights (gitignored *.pt)
tests/                 # pytest suite
dashboard/             # orphaned static HTML until Phase 4
```

## Environment

A `venv/` (or `.venv/`) at the repo root is the expected environment; activate it
before running anything. `scripts/surveillance.sh` auto-activates it.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"                 # full stack (torch, etc.)
# or, for API tests only (no torch):
pip install -e ".[web-test,dev]"
```

MediaMTX must be on `PATH` (`brew install mediamtx`); the launcher hard-fails without it.
There are no env vars to configure — all config lives in `config/spectrax.yml`.
Credentials are generated at runtime into the OS keychain (service
`video-feed-mediamtx` — name kept for Phase 0 compatibility), never into files;
`spectrax reset` wipes them.

## Running

From the repo root after editable install:

```bash
./scripts/surveillance.sh serve       # start from config/spectrax.yml
spectrax serve --config config/spectrax.yml
spectrax doctor
surveillance serve                    # temporary alias for spectrax
```

The CLI is Typer (`src/spectrax/cli.py`): `serve`, `doctor`, `reset`, `admin`,
`apikey`, `credentials`. Deprecated aliases: `config`, `start`, `quick`.
Removed: `run`, `detect`.

## Testing

Run pytest from the **repo root** (not a nested package dir):

```bash
pytest
pytest tests/test_auth.py::test_name    # single test
pytest -m unit                          # by marker
```

`pyproject.toml` sets `--strict-markers`, so any new marker must be added to
`[tool.pytest.ini_options].markers`
(`unit, integration, db, recording, detection, slow, requires_mediamtx, api`).
CI uses the slim web-test extra (no torch) and runs characterization/auth/layout tests only.

Coverage is sparse and concentrated on DB/recording/storage/auth; many modules
still lack tests. Characterization tests in `tests/test_api_characterization.py`
are the regression net for routes.

## Style

Ruff config lives in `pyproject.toml` (`ruff check .`, `ruff format .`).
The existing code predates it and is not clean — lint the files you touch;
do not mass-reformat the repo as a side effect of another change.

Otherwise follow the conventions of the file you are editing: 4-space indent,
docstrings on public modules and functions, `typing` annotations, `@dataclass`
for config objects, relative or absolute package imports (`from spectrax…`
or `from .constants import …`).

## Git

Branch off `main` with a type prefix (`docs/`, `feat/`, `fix/`) and merge via PR.
Never commit directly to `main`.

## Gotchas

- **No `sys.path` / `PYTHONPATH` hacks** — use `pip install -e .`.
- **Routes use module-level global state, not DI.** `visualizer.py` wires them at
  startup via setters (`video_routes.set_detector_manager`,
  `files_routes.set_recordings_directory`,
  `recordings_routes.set_recordings_api`). Miss one and the route 500s. See
  `src/spectrax/routes/README.md`. New endpoints belong in `routes/`, not
  `visualizer.py`. (DI is Phase 2.)
- **Two class filters that look alike**: `detection.filters.classes` controls
  what is *detected*, `recording.record_objects` controls what is *recorded*.
  Empty list means "all" for both.
- **`recording.codec` must be `avc1`** — `mp4v` produces clips the browser
  player cannot play. Re-verify playback after any OpenCV bump.
- **RTSPS uses a self-signed cert** generated at runtime (`server.crt` /
  `server.key` / `mediamtx.yml` are gitignored); clients will show security
  warnings. API auth is session cookie or bearer API key (Phase 0).
- **Path helpers** for config/models/TLS live in `spectrax.paths` — do not
  reintroduce `Path(__file__).parent.parent / "config"`.
- **Docs are known-stale — trust the code.** Full rewrite is Phase 4.
  `docs/ARCHITECTURE.md` and some README paths still mention the old
  `video-feed/` layout.
