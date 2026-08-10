# SpectraX Architecture

**Status:** reflects **Phase 0–2** (security, repackage, DI + process inversion).  
`/api/v1` + EventBus/SSE are **Phase 3** (not yet implemented).

## Overview

SpectraX is a **modular monolith**:

1. **MediaMTX** — RTSP/RTSPS/HLS ingest (child process by default, or external unit).
2. **Python core** — one process: FastAPI (uvicorn) + detector threads + recording manager.
3. **Clients** — browser dashboard (session cookie) or machine clients (bearer API keys).

```
cameras ──rtsps──▶ MediaMTX
                     │
                     ▼ pull
              spectrax serve (uvicorn main process)
              ┌─────────────────────────────────────┐
              │ lifespan: secrets, MediaMTX?, DB,   │
              │           DetectorManager           │
              │ FastAPI create_app + app.state DI    │
              │ routes → Depends(get_*)             │
              └─────────────────────────────────────┘
                    │ cookie / Bearer
                    ▼
              browser · future modules
```

## Repository layout

```
SpectraX/
├── pyproject.toml              # package metadata, ruff, pytest, entry points
├── config/spectrax.yml         # example config (no secrets)
├── models/                     # YOLO weights (gitignored *.pt)
├── src/spectrax/
│   ├── cli.py                  # Typer: serve, doctor, admin, apikey, reset, credentials
│   ├── app.py                  # create_app() factory
│   ├── runtime.py              # production lifespan (MediaMTX + detection stack)
│   ├── config.py               # SpectraXSettings (pydantic-settings) + MediaMTX YAML helpers
│   ├── secrets.py              # SecretsStore: file / keyring / memory
│   ├── credentials.py          # domain API over SecretsStore
│   ├── auth_gate.py            # middleware, session, bearer, rate limit
│   ├── paths.py                # project_root, state_dir, default config/TLS/models
│   ├── api/deps.py             # get_recordings_api, get_detector_manager, …
│   ├── routes/                 # FastAPI routers (unchanged URL prefixes)
│   ├── detection/              # detector + DetectorConfig + backends/ seam
│   ├── recording/              # RecordingsAPI (db) + RecordingManager
│   ├── mediamtx/               # process launch/stop + config re-exports
│   ├── visualizer.py           # legacy start_visualizer bridge
│   ├── surveillance.py         # re-export cli.app
│   └── templates/              # login, viewer, recordings
├── tests/                      # pytest (web-test CI suite + full-stack locals)
├── deploy/systemd/             # spectrax.service, mediamtx.service
├── dashboard/                  # orphaned static HTML (unsupported until Phase 4)
└── scripts/surveillance.sh     # thin launcher → spectrax serve
```

## Process topology

### Development / default (`mediamtx.managed: true`)

```bash
spectrax serve --config config/spectrax.yml
```

- **Main process:** uvicorn + FastAPI.
- **Lifespan startup:** secrets/settings → optional MediaMTX child → recording DB → detectors.
- **Lifespan shutdown:** stop detectors → close DB → terminate MediaMTX.
- No daemon-thread API server; no `os._exit` watchdog.

### Production Linux (`mediamtx.managed: false`)

- systemd `mediamtx.service` + `spectrax.service` (`After=mediamtx.service`).
- `spectrax serve --no-mediamtx` or config `mediamtx.managed: false`.
- Secrets: `SPECTRAX_SECRETS_BACKEND=file`, `SPECTRAX_STATE_DIR=/var/lib/spectrax`.

See `deploy/README.md`.

## Core modules

| Module | Role |
|--------|------|
| `cli.py` | Operator interface |
| `app.py` | App factory, middleware, exception handler, `/status` `/feeds` |
| `runtime.py` | Production lifespan wiring |
| `config.py` | `SpectraXSettings`, `load_settings`, MediaMTX `write_cfg` |
| `secrets.py` / `credentials.py` | Secrets backends + admin/API-key/stream secrets |
| `auth_gate.py` | Auth middleware (cookie or Bearer) |
| `api/deps.py` | DI accessors on `request.app.state` |
| `detection/` | YOLO + supervision pipeline |
| `recording/` | SQLite + clip buffering |
| `mediamtx/` | Subprocess control |
| `routes/*` | HTTP surface (no module-level setters) |

## Dependency injection

Routes **must not** use module globals / `set_*` setters.

```python
# app.state populated by create_app / lifespan
app.state.settings
app.state.recordings_api
app.state.recordings_dir
app.state.detector_manager
app.state.secrets

# routes
from spectrax.api.deps import get_recordings_api, get_detector_manager
```

Tests use `create_app(...)` / `tests.conftest.create_test_app` without MediaMTX or torch.

## Configuration

- **File:** `config/spectrax.yml` → `SpectraXSettings`.
- **Env:** `SPECTRAX_` + nested `__` (e.g. `SPECTRAX_NETWORK__BIND=0.0.0.0`).
- **Secrets never in YAML** — `SecretsStore` only.
- Class filters: `null` or `[]` → “all” (`list[str] | None`).

Legacy `SurveillanceConfig` is a deprecated adapter for a few call sites.

## Auth model (Phase 0)

| Mechanism | Use |
|-----------|-----|
| Admin password (argon2) | Dashboard login → signed session cookie (`HttpOnly`, `SameSite=Strict`) |
| API keys (`sx_…`, SHA-256 hashed) | Machine clients; scopes `read` / `admin` |
| Fail-closed | No admin hash → login **503** |
| Keychain service name | Still `video-feed-mediamtx` (compat) |

## Data flow

1. Cameras publish RTSPS to MediaMTX.
2. Detectors pull RTSP(S) with viewer credentials.
3. YOLO + ByteTrack → overlays (MJPEG) and recording triggers.
4. Clips + metadata → SQLite under `recordings_dir`.
5. Dashboard/API serve JSON, files, and streams behind auth.

## Testing

| Suite | Command |
|-------|---------|
| CI (slim) | `pip install -e ".[web-test,dev]"` + characterization/auth/config/secrets/app/runtime/layout tests |
| Full stack | `pip install -e ".[cv,dev]"` + recording/db/supervision tests |

Markers: `unit`, `api`, `db`, `recording`, `detection`, `slow`, `requires_mediamtx`, `integration`.

## Roadmap (see docs/PLAN.md)

| Phase | Status |
|-------|--------|
| 0 Security | Done |
| 1 Repackage (`src/spectrax`) | Done |
| 2 DI + lifespan + CLI | Done |
| 3 `/api/v1` + SSE EventBus | Next |
| 4 Docs polish + first external module | Partial (this doc set updated early) |

## Contributing

1. Branch off `main` with type prefix (`feat/`, `fix/`, `docs/`).
2. Prefer TDD for new behavior; keep Phase 0 characterization green.
3. Lint only files you touch (`ruff check --select E,F,B`); no mass reformat.
4. Never commit secrets or `*.pt` weights.
