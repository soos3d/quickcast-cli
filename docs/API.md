# SpectraX API Reference

**Base URL:** `http://127.0.0.1:8080` (or host/port from `network.bind` + `detection.port`).

**Auth required** on almost all routes (Phase 0). Versioned `/api/v1` is **not** shipped yet (Phase 3).

## Authentication

### Session cookie (browser)

```http
POST /auth/login
Content-Type: application/json

{"password":"<admin password>"}
```

- Success: `200` + `Set-Cookie` session (`HttpOnly`, `SameSite=Strict`; `Secure` only if configured).
- Wrong password: `401`.
- Admin password not set: `503` (fail-closed).
- Rate limited: `429` after repeated failures.

```http
POST /auth/logout
```

Clears the session cookie.

### Bearer API key (machines)

```http
Authorization: Bearer sx_<secret>
```

Keys are created with:

```bash
spectrax apikey create --name my-client --scope read   # or admin
```

Only the raw key is shown once; storage is SHA-256 hashed.

| Scope | Capabilities |
|-------|----------------|
| `read` | GET endpoints, streams, files |
| `admin` | Everything `read` does + `DELETE /api/recordings/{id}` |

### Public routes (no auth)

- `GET /login` — login HTML page
- `POST /auth/login`, `POST /auth/logout`

All other routes return **401** without a valid session or bearer key.

### Examples

```bash
# Cookie session
curl -c jar -b jar -X POST http://127.0.0.1:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"…"}'
curl -c jar -b jar http://127.0.0.1:8080/api/recordings

# Bearer
export KEY=sx_…
curl -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/status
```

## Error format

Unhandled errors:

```json
{"error": {"code": "internal", "message": "Internal server error"}}
```

HTTPException routes typically return FastAPI-style `{"detail": "…"}` without stack traces or filesystem paths.

---

## Pages

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/login` | public | Login form |
| GET | `/` | read | Live viewer |
| GET | `/recordings.html` | read | Recordings UI |

---

## System

### GET /status

Detector status for one feed (`?feed=`) or all.

**Auth:** read  
**503** if detector manager not started.

### GET /feeds

```json
{
  "feeds": {
    "<id>": {"id": "…", "name": "…", "source": "rtsp://***@…"}
  },
  "default": "<id>"
}
```

**Auth:** read

---

## Video

### GET /video/stream

MJPEG stream with detection overlay.

**Query:** `feed` (optional detector id)  
**Auth:** read (cookie required for `<img src>` in browser)  
**503** if no detector.

### GET /video/jpeg/{detector_id}

Single JPEG frame. **Auth:** read.

---

## Recordings API

### GET /api/recordings

List recordings with filters.

**Query parameters (common):**

| Param | Notes |
|-------|--------|
| `stream_id` | Filter by stream |
| `limit` / `offset` | Pagination |
| `start_date` / `end_date` | Time range |
| `object_type` | Class name |
| `min_confidence` | Float |
| `sort_by` | `timestamp` \| `confidence` \| `duration` |
| `sort_order` | `asc` \| `desc` |

**Auth:** read

### GET /api/recordings/{id}

Recording detail (includes relative `file_url` / `thumbnail_url` when possible).  
**Auth:** read · **404** if missing.

### DELETE /api/recordings/{id}

Delete recording row and files. **Auth:** **admin** only · **404** if missing.

### GET /api/recordings/stats

Aggregate recording statistics. **Auth:** read.

---

## Statistics

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/alerts` | read |
| GET | `/api/stats/objects` | read |
| GET | `/api/stats/times` | read |
| GET | `/api/streams` | read (needs detector; recording stats optional) |

---

## Files

### GET /recordings/{file_path:path}

Serve a file under the configured recordings directory.

**Auth:** read  
**Security:** path traversal blocked; allowlist `.mp4`, `.jpg`, `.jpeg`, `.png`, `.webm`.

---

## Removed / not present

| Endpoint | Status |
|----------|--------|
| `GET /paths` | **Removed** (Phase 0) — was unauthenticated side-server |
| `POST /auth/verify` | **Removed** — MediaMTX stream verify, not API auth |
| `/api/v1/*` | **Phase 3** — not implemented |
| SSE `/api/v1/events/stream` | **Phase 3** |

---

## CORS

CORS allows same-host dashboard origins derived from bind/port (not open `*`). Prefer same-origin dashboard at the detection port.

## OpenAPI

While the app is running, interactive docs (if enabled by FastAPI defaults):

- `http://127.0.0.1:8080/docs`
- `http://127.0.0.1:8080/openapi.json`

Frozen published OpenAPI for external modules is planned for Phase 3.
