# Route modules

FastAPI routers for the SpectraX dashboard API. Wired by `create_app()` in
`spectrax.app` — **not** by module-level setters.

## Structure

```
routes/
├── __init__.py
├── auth.py          # POST /auth/login, /auth/logout
├── pages.py         # GET /login, /, /recordings.html
├── video.py         # GET /video/stream, /video/jpeg/{id}
├── files.py         # GET /recordings/{path}
├── recordings.py    # /api/recordings CRUD
└── statistics.py    # /api/alerts, stats, streams
```

## Dependency injection

Dependencies come from `spectrax.api.deps` and `request.app.state`:

```python
from fastapi import Depends
from spectrax.api.deps import get_recordings_api, get_detector_manager, get_recordings_dir
from spectrax.auth_gate import require_read, require_admin
```

| Dep | Source |
|-----|--------|
| `get_recordings_api` | `app.state.recordings_api` (503 if missing) |
| `get_recordings_dir` | `app.state.recordings_dir` |
| `get_detector_manager` | `app.state.detector_manager` |
| `require_read` / `require_admin` | Session cookie or Bearer key |

**Do not** reintroduce `set_detector_manager` / `set_recordings_*` globals.

## Auth

All routes except login page + `/auth/login` + `/auth/logout` require auth via
`AuthMiddleware` and/or `Depends(require_*)`.

- DELETE recordings requires **admin** scope.
- MJPEG uses the session cookie (browsers cannot set `Authorization` on `<img>`).

## App factory

```python
from spectrax.app import create_app
from spectrax.config import load_settings

app = create_app(settings=load_settings("config/spectrax.yml"), ...)
```

Production: `spectrax serve` uses `spectrax.runtime.make_production_lifespan` to
populate `app.state` at startup.

## Tests

Use `tests.conftest.create_test_app(...)` — builds a real `create_app` with
in-memory secrets and optional `RecordingsAPI`, no MediaMTX/torch.
