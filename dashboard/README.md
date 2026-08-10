# Basic UI - Standalone Dashboard

This directory contains a standalone HTML dashboard for quick access to surveillance feeds.

## Status (Phase 0/1)

**Unsupported for production use.** The unauthenticated `/paths` discovery server
(`localhost:3333`) was removed in Phase 0. Opening `dashboard.html` via `file://` or
cross-origin auto-discovery no longer works.

Use the **integrated dashboard** served by the FastAPI app (same origin, session cookie):

```bash
# After: spectrax admin set-password
./scripts/surveillance.sh config
# Open http://127.0.0.1:8080/login
```

A same-origin rewrite of this standalone UI is deferred to Phase 4.

## Historical notes

Previously this dashboard used:

- **Paths API**: `http://localhost:3333/paths` (removed)
- **Video streams**: `http://localhost:8080/video/stream?feed={id}` (now requires auth)

Do not point tools at `GET /api/streams` as a drop-in for `/paths` — the response shape differs
and the endpoint requires authentication.
