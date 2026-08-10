# SpectraX Configuration Guide

**Updated:** 2026-08-10 (Phase 0–2)  
**Config file:** `config/spectrax.yml`

Secrets (admin password, API keys, MediaMTX stream passwords, session signing key)
are **never** stored in this file. They live in the secrets store (macOS keychain by
default, or a mode-0600 file under `$SPECTRAX_STATE_DIR` on headless Linux).

---

## Quick start

1. Edit `config/spectrax.yml`
2. `spectrax admin set-password`
3. `spectrax serve --config config/spectrax.yml`

Env overrides: nested keys with `SPECTRAX_` + `__`, e.g.:

```bash
export SPECTRAX_DETECTION__PORT=9090
export SPECTRAX_NETWORK__BIND=127.0.0.1
export SPECTRAX_SECRETS_BACKEND=file   # or keyring | auto
export SPECTRAX_STATE_DIR=~/.local/share/spectrax
```

---

## cameras

```yaml
cameras:
  - video/front-door
  - video/backyard
```

Logical MediaMTX path names. Each becomes an RTSP/RTSPS/HLS path.

---

## network

```yaml
network:
  bind: "127.0.0.1"
```

| Value | Meaning |
|-------|---------|
| `127.0.0.1` | Localhost only (**default**, recommended) |
| `0.0.0.0` | All interfaces — only after admin password + auth are configured |

There is **no** `api_port` / `/paths` server anymore (removed Phase 0).

Dashboard/API port is `detection.port` (default 8080).

---

## detection

```yaml
detection:
  enabled: true
  port: 8080
  model: "yolov8n.pt"
  confidence: 0.4
  resolution:
    width: 960
    height: 540
  stream:
    buffer_size: 10
    reconnect_interval: 5
  filters:
    # null or [] = all classes; list = only those classes
    classes: ["person", "car"]
    min_area: null
    max_area: null
  tracking:
    enabled: true
    track_thresh: 0.25
    track_buffer: 30
    match_thresh: 0.8
    frame_rate: 30
```

| Field | Notes |
|-------|--------|
| `model` | Filename resolved under `models/` or Ultralytics download |
| `confidence` | 0.0–1.0 |
| `filters.classes` | **null/`[]` = detect all**; non-empty = whitelist |
| `tracking` | ByteTrack via supervision |

Models live in repo-root `models/` (see `models/README.md`).

---

## appearance

```yaml
appearance:
  box:
    thickness: 2
    color: "yellow"    # green, red, blue, yellow, white, black, roboflow
  label:
    text_scale: 0.5
    text_thickness: 1
    text_padding: 10
    position: "top_left"
    border_radius: 0
```

Controls on-stream annotators only (not recording filters).

---

## recording

```yaml
recording:
  enabled: true
  min_confidence: 0.5
  pre_buffer_seconds: 10
  post_buffer_seconds: 20
  max_storage_gb: 10.0
  recordings_dir: "~/video-feed-recordings"
  # null or [] = record all detections; list = only those classes
  record_objects: ["person", "car"]
  codec: "avc1"
```

| Field | Notes |
|-------|--------|
| `record_objects` | **Independent of** `detection.filters.classes` |
| `codec` | Must be **`avc1`** for HTML5 browser playback (`mp4v` will not play reliably) |
| `recordings_dir` | `~` is expanded |

---

## security

```yaml
security:
  use_tls: true
  tls_key: ""    # empty → default server.key at project root if present
  tls_cert: ""
```

With TLS enabled and key/cert available, MediaMTX is written with
`rtspEncryption: strict` (RTSPS only for encrypted paths).

---

## mediamtx

```yaml
mediamtx:
  managed: true
```

| Value | Behavior |
|-------|----------|
| `true` (default) | `spectrax serve` lifespan spawns MediaMTX as a child |
| `false` | Expect external MediaMTX (systemd); use `serve --no-mediamtx` |

Generated config when managed: `$SPECTRAX_STATE_DIR/mediamtx.yml`.

---

## Secrets & credentials

| Secret | How to manage |
|--------|----------------|
| Admin dashboard password | `spectrax admin set-password` |
| API keys | `spectrax apikey create\|list\|revoke` |
| MediaMTX publisher/viewer | Auto-generated; reveal with `spectrax credentials show-stream` |
| Session signing key | Auto-generated in secrets store |
| Wipe all | `spectrax reset` |

Backends:

| Backend | When |
|---------|------|
| `keyring` | Default on macOS (`auto`) |
| `file` | Default on Linux headless (`$SPECTRAX_STATE_DIR/secrets.yml`, mode `0600`) |
| `memory` | Tests only |

Keychain **service name** remains `video-feed-mediamtx` for compatibility with Phase 0 secrets.

---

## Validation

Invalid YAML or out-of-range values fail at load time via pydantic (`SpectraXSettings`).
Run `spectrax doctor` to verify Python, MediaMTX, config, state dir, and admin password presence.

---

## Related

- [README](../README.md) — install and CLI overview  
- [API.md](API.md) — HTTP surface  
- [deploy/README.md](../deploy/README.md) — systemd  
- [PLAN.md](PLAN.md) — modernization roadmap  
