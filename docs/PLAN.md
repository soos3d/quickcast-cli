# SpectraX Modernization & Re-architecture Plan

> Status: **Phase 0 on `main`** · **Phase 1 on `feat/phase-1-repackage` (merge pending)** ·
> Written 2026-08-09 · Phase 0 confirmed 2026-08-10 · Phase 1 implemented 2026-08-10
>
> Sources: full-codebase survey, security audit, and architecture design produced 2026-08-09;
> Phase 0 PR DAG refined by `plan-next-phase` workflow 2026-08-10.

## 1. Vision

SpectraX becomes the **core service** of a local surveillance system:

- Camera ingest (MediaMTX/RTSP), YOLO detection, recording, and storage in one service.
- **Modular by design**: future modules (notifiers, analytics, integrations — any language)
  are separate processes that consume the core's data through a **secure, versioned API**.
- The dashboard is "module #1" — a client of that same API, secured behind login.
- Deployment targets: **macOS and Linux** (including headless Linux servers).
  Raspberry Pi / ARM is explicitly **out of scope** (dropped 2026-08-09); it survives only
  as a cheap extension point (see §4.5).

## 2. Current state (survey findings, verified against code)

### Structure
- One process, three servers: `surveillance.py` (Typer CLI, 717 lines, `sys.path` hack)
  spawns MediaMTX as a subprocess, runs the FastAPI dashboard (`visualizer.py` + `routes/`)
  in a **daemon thread**, plus a second raw `http.server` `/paths` endpoint (port 3333,
  unauthenticated, CORS `*`). Shutdown relies on daemon-thread death and an `os._exit(0)`
  watchdog.
- Routes are wired by **module-level globals via setters** (`set_detector_manager(...)` etc.)
  — miss one and the route 500s. This is the main structural liability.
- Clean, reusable cores worth keeping: `api.py` (RecordingsAPI — parameterized SQLite),
  `recorder.py` (buffering, cooldown, thumbnails, cleanup), `detector.py`
  (supervision-based detection), `detector_config.py`, path-traversal-safe `routes/files.py`.
- `cli.py` is a deprecated shim. `setup.py` claims Python ≥3.8 (EOL, fiction).
  Deps pinned ~Apr 2025 (fastapi 0.115.12, torch 2.7.0, etc.). Deprecated
  `@app.on_event("shutdown")`. Tests cover only DB/recording/storage. No CI.

### Security audit — prioritized findings

| ID | Sev | Finding | Where |
|----|-----|---------|-------|
| C1 | CRITICAL | Entire API unauthenticated, binds `0.0.0.0`; `/auth/verify` exists but nothing enforces it | `visualizer.py:39-71`, `surveillance.py` |
| C2 | CRITICAL | Unauthenticated `DELETE /api/recordings/{id}` → `os.remove()`; LAN attacker can wipe all recordings | `routes/recordings.py:183-200`, `api.py:221-254` |
| H1 | HIGH | `/auth/verify` brute-force oracle: plaintext `==` compare, no rate limit, fixed usernames | `routes/auth.py:17-42`, `credentials.py:27-30` |
| H2 | HIGH | `detail=str(e)` leaks DB errors / absolute paths to clients | `routes/recordings.py`, `routes/statistics.py` |
| H3 | HIGH | `rtspEncryption: "optional"` → creds negotiable to cleartext; HLS URLs embed `user:pass` over HTTP | `config.py:61`, `utils.py:116-120` |
| M1 | MEDIUM | Stored XSS: stream names interpolated into `innerHTML` | `templates/recordings.html`, `viewer.html` |
| M2 | MEDIUM | `/paths` mini-server: unauthenticated, `0.0.0.0`, CORS `*` | `surveillance.py:147,600-606` |
| M3 | MEDIUM | Self-signed RTSPS cert, no client verification — LAN MITM possible; document as threat | `surveillance.py:77-83` |
| L1–L4 | LOW | Creds printed to terminal; fixed usernames; CORS `allow_credentials` pre-auth; YOLO pickle load (keep config-only) | various |

**Checked and clean** (do not re-litigate): no SQL injection (parameterized + whitelisted sort),
no command injection (arg-list `Popen`, no shell), path traversal defense in `files.py` is solid,
`yaml.safe_load` everywhere, no secrets in code or git history, dep pins have no known high CVEs.

## 3. Target architecture

**Modular monolith core + out-of-process modules.**

```
 cameras ──rtsps──▶ MediaMTX ◀── auth callback (authMethod: http) ──┐
                    (systemd / launchd or CLI-spawned in dev)       │
                        │ rtsp(s) pull                              │
                        ▼                                           │
                spectrax service (one Python process)               │
                ┌─────────────────────────────────────────────┐     │
                │ DetectionEngine (threads per stream)        │     │
                │   backend: ultralytics (default)            │     │
                │      │ sv.Detections                        │     │
                │      ├──▶ RecordingManager ──▶ mp4/thumbs   │     │
                │      ▼                                      │     │
                │   EventBus ──▶ SQLite (recordings, events,  │     │
                │      │          api_keys)                   │     │
                │      ▼                                      │     │
                │ FastAPI /api/v1 (bearer key | session) ─────┼─────┘
                │   streams · recordings · events(SSE) ·      │
                │   stats · system · dashboard                │
                └──────┬──────────────────┬───────────────────┘
                  browser (cookie)   modules (API key, any language)
```

### 3.1 Module contract (the one hard-to-reverse decision)

- **REST under `/api/v1`** + **SSE at `/api/v1/events/stream`** is the *only* module contract.
  No in-process plugin API, ever — modules are separate processes; a bad module cannot take
  down the core, and modules can be written in any language.
- SSE over WebSocket (one-directional suffices, plain HTTP, `curl`-debuggable, and
  `Last-Event-ID` + the SQLite events table gives replay-after-disconnect nearly free).
  MQTT rejected (broker + second auth system for zero current benefit; a bridge module can
  republish later if needed).
- OpenAPI spec (FastAPI-generated) **is** the documented contract. Additive changes free;
  breaking changes → `/api/v2` alongside `/api/v1` with a deprecation window. Event payloads
  carry `"v": 1`. Pydantic response models on every endpoint — schema enforced, not aspirational.

**Endpoint groups**

| Group | Endpoints | Auth |
|---|---|---|
| auth | `POST /auth/login`, `POST /auth/logout` | rate-limited |
| streams | `GET /streams`, `/streams/{id}`, `/streams/{id}/live.mjpeg`, `/streams/{id}/snapshot.jpg` | read |
| recordings | `GET /recordings` (filter/page), `/recordings/{id}`, `/{id}/video`, `/{id}/thumbnail`, `DELETE /recordings/{id}` | read; **admin** for DELETE |
| events | `GET /events` (history), `GET /events/stream` (SSE, `Last-Event-ID` replay) | read |
| stats | `GET /stats/objects`, `/stats/time`, `/stats/streams/{id}`, `/stats/summary` | read |
| system | `GET /system/health`, `/system/status`, `/system/config` (redacted) | read |
| internal | `POST /internal/mediamtx-auth` (MediaMTX HTTP auth callback) | localhost-only |

Event envelope:
`{"v":1, "id":"<monotonic>", "type":"detection.started|detection.updated|recording.completed|stream.online|stream.offline", "ts":…, "stream_id":…, "data":{…}}` —
persisted to an `events` table (retention cleanup alongside existing storage cleanup) so SSE
replay and `GET /events` share one source.

### 3.2 Auth design

- **Machine clients (modules)**: per-module bearer API keys (`Authorization: Bearer sx_<random>`),
  stored **SHA-256-hashed** (fine for 32-byte random secrets) in an `api_keys` table
  (name, created_at, revoked_at, scopes). Managed via CLI:
  `spectrax apikey create|list|revoke`. Constant-time compare. Two scopes only:
  `read` (default) and `admin` (delete recordings, config changes). No OAuth/JWT ceremony.
- **Browser dashboard**: one admin password (`spectrax admin set-password`, argon2/bcrypt hash)
  → rate-limited login (in-memory token bucket or `slowapi`) → signed session cookie
  (`HttpOnly`, `SameSite=Strict`, `Secure` when TLS). `itsdangerous`-style signing; no
  server-side session store. Delete `routes/auth.py` `/verify` entirely (it verified MediaMTX
  stream creds, not API access).
- **Secrets on headless Linux** (keychain unavailable): `SecretsStore` protocol with two impls —
  `FileSecretsStore` (default: `$SPECTRAX_STATE_DIR/secrets.yml`, mode `0600`, fail fast if
  wider) and `KeyringSecretsStore` (macOS/desktop dev). Env vars rejected (leak into `/proc`
  and the MediaMTX child process); systemd `LoadCredential` deferred as optional third impl.
- **MediaMTX**: switch stream auth to its native HTTP callback (`authMethod: http` → core's
  `/internal/mediamtx-auth`); `rtspEncryption: strict`; stop embedding `user:pass` in HLS URLs
  (serve HLS through the authenticated core or via the callback).
- API may bind `0.0.0.0` **only with auth in place**; until then default `127.0.0.1`.

### 3.3 Process topology

- Two services: `mediamtx` + `spectrax` (one Python process: uvicorn + detector threads +
  recording manager). Threads are fine — OpenCV/torch release the GIL; frame-sharing between
  detector and recorder makes a process split pure cost. The `DetectionEngine` interface is the
  pre-cut seam if a split is ever needed.
- **Inversion vs today**: the API server becomes the main process (FastAPI lifespan owns
  startup/shutdown of detector threads and the MediaMTX child); the CLI becomes a thin client
  (`spectrax serve` in dev; systemd/launchd in production). Delete the `os._exit(0)` watchdog
  and the `/paths` http.server; `run`/`detect`/`quick` collapse into `serve`.
- systemd unit for Linux (`Restart=on-failure`, `After=mediamtx.service`, journald);
  running `spectrax serve` in a terminal remains the macOS/dev path.

### 3.4 Repo structure

```
spectrax/
├── pyproject.toml            # replaces setup.py; requires-python >=3.11; ruff config moves here
├── config/spectrax.yml       # was surveillance.yml (example, committed; no secrets)
├── src/spectrax/
│   ├── cli.py                # thin Typer app: serve, apikey, admin, reset, doctor
│   ├── app.py                # FastAPI factory + lifespan (owns startup wiring)
│   ├── config.py             # pydantic-settings model (validated, env-overridable)
│   ├── secrets.py            # SecretsStore protocol + File/Keyring impls
│   ├── auth.py               # api-key + session dependencies, key hashing
│   ├── events.py             # EventBus + events table + SSE plumbing
│   ├── mediamtx/             # config writer, launcher/health, auth callback handler
│   ├── detection/            # engine.py, backends/ (extension point), config.py, stream.py
│   ├── recording/            # recorder.py, storage.py, db.py (was api.py)
│   └── api/                  # routers: streams, recordings, events, stats, system, dashboard
│       └── deps.py           # real FastAPI Depends() — replaces all set_* setters
├── dashboard/                # templates + static; talks only to /api/v1 (module #1)
└── tests/
```

- Kills the `sys.path` hack and `PYTHONPATH=video-feed` gotcha permanently
  (editable install via pyproject).
- Future modules: **separate repos** consuming the versioned API — not namespace packages
  (those would couple modules to the core's Python env, contradicting the contract).

### 3.5 Config

- Single `spectrax.yml` → nested **pydantic-settings** model (`CamerasConfig`,
  `DetectionConfig`, `RecordingConfig`, `ApiConfig`, `MediamtxConfig`). Invalid config fails
  at startup with field-level errors. Env overrides native (`SPECTRAX_API__PORT=8080`).
- Secrets never in the config file — only in the `SecretsStore`.
- Fix the lookalike-filter ambiguity: type `detection.filters.classes` and
  `recording.record_objects` as `list[str] | None` where `None` = "all" — the ambiguous `[]`
  state becomes unrepresentable.
- Fixes the hidden re-load of a hardcoded detector-config path inside `start_detector`:
  config loads once in `app.py` and is passed down.

### 3.6 Cross-cutting

- **Errors**: one hierarchy (`SpectraxError` → `NotFound`, `AuthError`, `ConfigError`,
  `BackendError`) mapped by a single exception handler to `{"error": {"code", "message"}}` —
  no stack traces or paths to clients (closes H2); internals logged server-side at ERROR.
  Detector threads report into `/system/health` instead of dying silently.
- **SQLite**: WAL mode + single writer connection owned by the core (pattern already exists in
  `recorder.get_database_connection`) to avoid contention between recorder, events, and API.
- **Testing**: the DI move is what makes the untested surface testable —
  `create_app(config, fake_engine, tmp_db)` fixtures + httpx TestClient, no MediaMTX needed.
  Auth unit tests first (hashing, revocation, cookie tamper); events integration test
  (detection → row → SSE). Existing DB/recording tests carry over nearly unchanged.
  Coverage ratchet to 80% as surface becomes testable. TDD for all new code.
- **CI**: GitHub Actions — ruff check + pytest on Python 3.11 and 3.12, macOS + Ubuntu runners.

## 4. Phases (each independently shippable, one PR-branch per phase off `main`)

### Phase 0 — Stop the bleeding (security, on the CURRENT layout) — 4–7 days

**Status: merged to `main` (PR #9).**

Fixes both CRITICALs and the HIGHs before any restructuring, so security never waits on
architecture. Work stays on `video-feed/videofeed/` — **no** `create_app`, `src/spectrax/`,
or `/api/v1` in this phase.

#### Phase 0 decisions (locked 2026-08-10)

| Decision | Choice |
|---|---|
| Dashboard TLS / cookie `Secure` | Plain HTTP on trusted LAN; `Secure=False` by default. Always `HttpOnly` + `SameSite=Strict`. `Secure=True` only with explicit TLS/config flag. |
| Admin / API key storage | OS keyring only (`KEYCHAIN_SERVICE`). Labels: `admin_password_hash`, `session_signing_key`, `api_keys` (JSON blob). No mode-0600 file store (Phase 2). Never reuse MediaMTX stream secrets for API login. |
| Fail-closed bootstrap | No admin hash → login returns **503**; API is not open. Operator runs `surveillance admin set-password` first. |
| `/paths` removal | Delete unauthenticated side-server. Standalone `ui/dashboard.html` discovery is **unsupported** until same-origin dashboard (Phase 4). Do **not** treat `GET /api/streams` as a drop-in. |
| Bind default | `127.0.0.1`; explicit `0.0.0.0` only after auth lands. |
| CI bootstrap | Ubuntu + Python 3.11/3.12 required; macOS matrix deferred. Ruff scoped to new/touched paths. |
| Stream password reveal | After CLI redaction, `surveillance credentials show-stream` (TTY-only) prints publisher/viewer secrets once. |

#### PR DAG

```
p0-ci  ──┬──► p0-errors  ──┐
         └──► p0-network ──┴──► p0-auth
```

1. **p0-ci** — `requirements-dev.txt` + slim `requirements-web-test.txt` (no torch); router-only
   TestClient harness; characterization tests; `.github/workflows/ci.yml`.
2. **p0-errors** — global exception handler; kill `detail=str(e)`; XSS-safe templates;
   fix recordings UI to call `/api/recordings`.
3. **p0-network** — bind `127.0.0.1`; delete `/paths` HTTPServer; `rtspEncryption: strict`;
   redact CLI secrets; `credentials show-stream`.
4. **p0-auth** — session cookie + bearer `sx_` keys; rate-limited login/logout; admin DELETE;
   gate all media paths; fail-closed if admin unset.

Checklist (maps to original items):

1. Bearer-key + session auth over the whole existing app; admin scope on
   `DELETE /api/recordings/{id}` (C1, C2, H1) — **p0-auth**.
2. Delete `routes/auth.py` `/verify`; `secrets.compare_digest`; rate-limit login (H1) — **p0-auth**.
3. Global exception handler; kill every `detail=str(e)` (H2) — **p0-errors**.
4. Escape template interpolation — `textContent`/`createElement` (M1) — **p0-errors**.
5. `rtspEncryption: strict`; stop printing/embedding plaintext creds (H3, L1) — **p0-network**.
6. Delete the `/paths` `http.server` side-door (M2) — **p0-network**.
7. Default bind `127.0.0.1`; `0.0.0.0` only after auth — **p0-network** + **p0-auth**.
8. Characterization tests + auth tests + CI + `requirements-dev.txt` — **p0-ci** + **p0-auth**.

*Ships: today's app, secured and under CI.*

### Phase 1 — Repackage — days
Mechanical only, no logic changes.

**Status: implemented on branch `feat/phase-1-repackage` (merge pending).**

1. `pyproject.toml` (setuptools backend, `requires-python >= 3.11`, console scripts
   `spectrax` + `surveillance` alias); delete `setup.py`, `cli.py` shim, and the
   `sys.path` hack. Core deps exclude torch; full stack is `pip install -e ".[cv]"`. — **done**
2. `git mv` to `src/spectrax/` layout; package rename `videofeed` → `spectrax`; path
   helpers in `spectrax.paths`; ruff/pytest config in pyproject; config at
   `config/spectrax.yml`; keychain service string kept as `video-feed-mediamtx`. — **done**
3. Compiled lockfiles via `uv pip compile` (`requirements.lock.txt`,
   `requirements-web-test.lock.txt`). Direct pin bumps (OpenCV/`avc1` gate) deferred to a
   follow-up so this PR stays mechanical. — **done (structure); version bumps deferred**
4. `@app.on_event` → lifespan context. — **done**

*Ships: identical behavior, proper installable package, current deps.*

### Phase 2 — Invert the process + DI — 1–2 weeks
The core re-architecture. Riskiest phase; mitigations: DI router-by-router behind unchanged
URLs, Phase 0 tests as the regression net.

1. `create_app()` factory + lifespan owns startup (detector engine, MediaMTX child, DB);
   routers take `Depends()` from `api/deps.py`; delete every `set_*` setter and `visualizer.py`
   (logic splits into `app.py` + `detection/engine.py`).
2. CLI collapses to `serve` / `apikey` / `admin` / `reset` / `doctor`.
3. pydantic-settings config model (§3.5).
4. `SecretsStore` protocol: `FileSecretsStore` (Linux default) + `KeyringSecretsStore` (macOS);
   migration path from existing keychain entries.
5. systemd unit files (replacing the stale `scripts/surveillance.service`); doc for launchd/dev
   on macOS.
6. **Refactor-and-move** (keep): `api.py`→`recording/db.py`, `recorder.py`, `detector.py`
   internals, `routes/files.py`. **Rewrite** (encode old topology): `surveillance.py`,
   `visualizer.py`, `config.py`, `credentials.py`.
7. Route/config/credentials/detector-manager/CLI tests as each piece lands (TDD);
   raise coverage ratchet toward 80%.

*Ships: the headless-Linux-deployable core; macOS dev flow intact.*

### Phase 3 — Module contract — 1 week
1. `/api/v1` prefix; pydantic response models on every endpoint.
2. `events` table + `EventBus` + SSE endpoint with `Last-Event-ID` replay; retention cleanup.
3. MediaMTX auth callback (`authMethod: http`); HLS creds-in-URL removed.
4. Publish the OpenAPI spec as the documented, frozen v1 contract.
5. Integration test: detection → event row → SSE delivery.

*Ships: the first version modules can build against — freeze here.*

### Phase 4 — Docs & first module — 1 week
1. Rewrite `docs/ARCHITECTURE.md` against the new reality; fix `README.md` (dead
   `RECORDING_SETUP.md` link, auth setup, install flow, Python floor); regenerate
   `docs/API.md` from OpenAPI with per-route auth requirements; verify
   `CONFIGURATION_GUIDE.md`; update `routes/README.md` (or delete — DI makes it moot).
2. First real external module — e.g. a notifier consuming SSE — as the contract's
   proof-of-life, in its own repo.
3. Dashboard incrementally rewritten to consume only `/api/v1`.

*Ships: docs that match the code; a working example module.*

### Deferred / extension points (explicitly NOT planned)
- **ARM/Pi support & `DetectionBackend` abstraction** (ONNX Runtime/NCNN backends,
  lazy MJPEG encoding): dropped with the Pi requirement 2026-08-09. The
  `detection/backends/` directory is kept as the seam; build it only if the target returns
  or someone wants a lighter-than-torch install.
- Coral/Hailo accelerators, MQTT bridge, systemd `LoadCredential` secrets impl,
  Playwright E2E for the dashboard (two templates today; revisit if the UI grows).

## 5. Risks

| Risk | Sev | Mitigation |
|---|---|---|
| Auth breaks MJPEG/dashboard (`<img>` can't send headers) | HIGH | Cookie sessions from the start; browser-test before merging Phase 0 |
| CV-stack upgrade silently breaks detection/recording | HIGH | Tiered upgrades; `test_supervision_integration.py` gate; manual `quick` smoke; re-verify `avc1` playback |
| Phase 2 big-bang regressions in untested code | MED | Characterization tests first (Phase 0); DI router-by-router; one router per PR |
| SQLite write contention (recorder + events + API) | MED | WAL mode; single writer connection owned by core |
| Solo-maintainer stall | MED | Every phase independently shippable; Phase 0 alone materially improves security posture |
| Keyring→file secrets migration loses existing creds | LOW | `spectrax reset` regenerates; document migration in Phase 2 |

## 6. Success criteria

- [ ] Every endpoint requires auth (bearer key or session) except login; login rate-limited;
      all secret comparisons constant-time; DELETE requires admin scope.
- [ ] No error response leaks internals; no XSS via stream names; `rtspEncryption: strict`;
      no plaintext creds in URLs; `/paths` side-server gone.
- [ ] `pip install -e .` works from repo root; no `sys.path`/`PYTHONPATH` hacks;
      Python ≥3.11; deps current with lockfile; CI green on macOS + Ubuntu.
- [ ] Zero mutable module globals in routers; `create_app()` factory; config validated at
      startup; secrets work on headless Linux via `FileSecretsStore`.
- [ ] `/api/v1` versioned contract published (OpenAPI); SSE events with replay;
      one external module consuming it.
- [ ] `pytest --cov=spectrax` ≥ 80%, enforced in CI.
- [ ] Docs match the code; `surveillance.service` replaced with a valid unit.

## 7. Open questions

1. ~~**Dashboard TLS**~~ — **Decided (Phase 0):** plain HTTP on trusted LAN;
   `Secure=False` by default; `HttpOnly` + `SameSite=Strict` always. Self-signed dashboard
   HTTPS deferred.
2. ~~**Rename**~~ — **Decided (Phase 1):** package is `spectrax`; console scripts
   `spectrax` + temporary `surveillance` alias. Keychain service stays
   `video-feed-mediamtx`.
3. ~~**`.enc` extension**~~ — **Decided (Phase 1):** removed from files allowlist (dead).
4. **MediaMTX ownership**: keep spawning it as a child of the core (simplest, current
   behavior) vs separate systemd unit on Linux (survives core restarts)? Plan assumes
   child-process in dev, separate unit in production — confirm in Phase 2.

## 8. Phase 0 success criteria (ship gate)

- [ ] Unauthenticated requests to `/status`, `/api/recordings`, `/video/stream`,
      `/video/jpeg/{id}`, `/recordings/{file}`, and `DELETE /api/recordings/{id}` return
      401/403, not 2xx.
- [ ] Read session cookie or Bearer allows GETs (JSON + MJPEG + file media); only admin
      can DELETE.
- [ ] `POST /auth/verify` is gone; login rate-limited; secret compares use
      `secrets.compare_digest`.
- [ ] No 500 body leaks paths/exception text; missing recording → 404 not 500.
- [ ] Templates do not interpolate untrusted names into `innerHTML`; list/DELETE use
      `/api/recordings`.
- [ ] `rtspEncryption: strict` with TLS; no `user:pass@` in CLI URLs; reveal command exists.
- [ ] `/paths` side-server gone; default bind `127.0.0.1`.
- [ ] CI green on Ubuntu 3.11/3.12 (web-test stack, no torch).
- [ ] `reset` wipes stream secrets **and** admin hash, API keys, session signing key.
- [ ] Fail-closed when admin password unset.
