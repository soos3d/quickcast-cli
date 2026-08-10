# SpectraX — Unified Surveillance System

SpectraX is a local surveillance core: MediaMTX RTSP/HLS ingest, YOLO object detection,
event-based recording, and an authenticated FastAPI dashboard/API.

> ⚠️ SpectraX uses a self-signed certificate for RTSPS by default, which can trigger
> security warnings in clients. For production, replace it with a CA-signed cert.

## What it does

- **Streaming** — RTSP / RTSPS / HLS via [MediaMTX](https://github.com/bluenviron/mediamtx)
- **Detection** — [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) +
  [Roboflow supervision](https://github.com/roboflow/supervision) (ByteTrack, annotators)
- **Recording** — Event clips with pre/post buffers, SQLite metadata, browser-playable `avc1`
- **API + dashboard** — Session cookie (browser) or bearer API keys (machines)
- **Deploy targets** — macOS and Linux (including headless via file secrets)

## Requirements

- **Python ≥ 3.11**
- **MediaMTX** on `PATH` (`brew install mediamtx`, or [releases](https://github.com/bluenviron/mediamtx/releases))
- 4GB+ RAM (more for multi-camera)

## Quick start

```bash
git clone https://github.com/SpectraCoreX/SpectraX.git
cd SpectraX

python3.12 -m venv venv
source venv/bin/activate   # Windows: .\venv\Scripts\activate

# Full runtime (detection + recording)
pip install -e ".[cv,dev]"

# Edit cameras and options
# config/spectrax.yml

# Set dashboard admin password (fail-closed until this is done)
spectrax admin set-password

# Optional health check
spectrax doctor

# Start (API is the main process; lifespan owns MediaMTX + detectors by default)
spectrax serve --config config/spectrax.yml
# or: ./scripts/surveillance.sh serve
```

Open the dashboard: `http://127.0.0.1:8080/login` (port from `detection.port` in config).

**Stream passwords** (MediaMTX publisher/viewer) are in the OS keychain / secrets store:

```bash
spectrax credentials show-stream   # TTY only
```

## Install options

| Command | Use |
|---------|-----|
| `pip install -e ".[cv,dev]"` | Full stack (torch, OpenCV, YOLO) + tests |
| `pip install -e ".[web-test,dev]"` | API/auth tests only (no torch) — used by CI |
| `pip install -e ".[cv]"` | Runtime without dev tools |

Lockfiles: `requirements.lock.txt` (full), `requirements-web-test.lock.txt` (slim).

## Configuration

Single file: **`config/spectrax.yml`** (no secrets in YAML).

```yaml
cameras:
  - video/front-door

network:
  bind: "127.0.0.1"    # loopback default; 0.0.0.0 only after auth is configured

detection:
  enabled: true
  port: 8080
  model: "yolov8n.pt"
  confidence: 0.4

recording:
  enabled: true
  codec: "avc1"        # required for browser playback
  recordings_dir: "~/video-feed-recordings"

mediamtx:
  managed: true        # false when MediaMTX is a separate systemd unit

security:
  use_tls: true
```

Env overrides use nested `SPECTRAX_*` keys, e.g. `SPECTRAX_DETECTION__PORT=9090`.

See [Configuration Guide](docs/CONFIGURATION_GUIDE.md).

## CLI

```bash
spectrax serve --config config/spectrax.yml   # preferred
spectrax serve --no-mediamtx                  # external MediaMTX unit
spectrax doctor
spectrax admin set-password
spectrax apikey create --name notifier --scope read
spectrax apikey list
spectrax apikey revoke <id>
spectrax credentials show-stream
spectrax reset                                # wipe all secrets
```

Deprecated aliases: `config`, `start`, `quick` → `serve`.  
Removed: `run`, `detect`.

Console scripts: `spectrax` and temporary alias `surveillance`.

## Authentication

| Client | How |
|--------|-----|
| Browser dashboard | `POST /auth/login` with admin password → `HttpOnly` session cookie |
| Scripts / modules | `Authorization: Bearer sx_…` (`read` or `admin` scope) |
| Admin password unset | Login returns **503** (API is not open) |

```bash
# Session (cookie jar)
curl -c jar -b jar -X POST http://127.0.0.1:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"your-admin-password"}'
curl -c jar -b jar http://127.0.0.1:8080/api/recordings

# Bearer
curl -H "Authorization: Bearer sx_…" http://127.0.0.1:8080/status
```

Default bind is **`127.0.0.1`**. Only use `0.0.0.0` after admin password + API keys are set.

## REST API (current)

Base URL: `http://127.0.0.1:8080` (or your `detection.port`).

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/auth/login` | rate-limited | Sets session cookie |
| POST | `/auth/logout` | — | Clears cookie |
| GET | `/login` | public | Login page |
| GET | `/` | read | Viewer |
| GET | `/recordings.html` | read | Recordings UI |
| GET | `/status` | read | Detector status |
| GET | `/feeds` | read | Feed list |
| GET | `/video/stream` | read | MJPEG (cookie works in `<img>`) |
| GET | `/video/jpeg/{id}` | read | Single JPEG |
| GET | `/api/recordings` | read | List/filter |
| GET | `/api/recordings/{id}` | read | Detail |
| DELETE | `/api/recordings/{id}` | **admin** | Delete clip |
| GET | `/api/recordings/stats` | read | Stats |
| GET | `/api/alerts` | read | Alerts |
| GET | `/api/stats/objects` | read | Object stats |
| GET | `/api/stats/times` | read | Time stats |
| GET | `/api/streams` | read | Streams + recording stats |
| GET | `/recordings/{path}` | read | File/thumbnail (path-safe) |

`/paths` was removed in Phase 0. Versioned `/api/v1` + SSE is **Phase 3** (not shipped yet).

Full reference: [docs/API.md](docs/API.md).

## Layout (after Phase 1–2)

```
SpectraX/
├── pyproject.toml
├── config/spectrax.yml
├── models/                 # YOLO weights (*.pt gitignored)
├── src/spectrax/
│   ├── cli.py              # Typer entry
│   ├── app.py              # create_app()
│   ├── runtime.py          # lifespan: MediaMTX + detection
│   ├── config.py           # SpectraXSettings
│   ├── secrets.py          # File / keyring / memory stores
│   ├── auth_gate.py
│   ├── api/deps.py         # FastAPI Depends
│   ├── routes/
│   ├── detection/
│   ├── recording/
│   ├── mediamtx/
│   └── templates/
├── tests/
├── deploy/systemd/         # spectrax.service + mediamtx.service
└── scripts/surveillance.sh
```

## Production (Linux)

See [deploy/README.md](deploy/README.md):

- `mediamtx.managed: false` + dual systemd units
- `SPECTRAX_SECRETS_BACKEND=file` and `SPECTRAX_STATE_DIR=/var/lib/spectrax`

## Development & tests

```bash
pip install -e ".[web-test,dev]"
pytest tests/test_api_characterization.py tests/test_auth.py \
  tests/test_config_model.py tests/test_secrets_store.py \
  tests/test_app_factory.py tests/test_runtime.py tests/test_package_layout.py
```

CI runs that suite on Ubuntu × Python 3.11/3.12 (no torch).

## Documentation

| Doc | Audience |
|-----|----------|
| [Configuration Guide](docs/CONFIGURATION_GUIDE.md) | Operators |
| [API Documentation](docs/API.md) | Integrators |
| [Architecture](docs/ARCHITECTURE.md) | Contributors |
| [Tracking guide](docs/tracking_usage_guide.md) | Tracking feature |
| [Modernization plan](docs/PLAN.md) | Roadmap (Phase 0–2 done; 3–4 next) |
| [Deploy](deploy/README.md) | systemd / headless |

## License

See [LICENSE](LICENSE).

## Acknowledgments

- [MediaMTX](https://github.com/bluenviron/mediamtx)
- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)
- [Roboflow Supervision](https://github.com/roboflow/supervision)
- [ByteTrack](https://github.com/ifzhang/ByteTrack)
- [FastAPI](https://fastapi.tiangolo.com/)
