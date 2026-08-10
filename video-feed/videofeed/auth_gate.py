"""API authentication: signed session cookies and bearer API keys.

Phase 0 auth for the existing FastAPI app. Secrets live in the OS keyring
(see credentials.py). Browser clients use HttpOnly session cookies so MJPEG
<img> tags work without Authorization headers. Machine clients use
Authorization: Bearer sx_<token>.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from . import credentials as creds_mod

logger = logging.getLogger(__name__)

COOKIE_NAME = "spectrax_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours
LOGIN_RATE_LIMIT = 10  # attempts
LOGIN_RATE_WINDOW = 60  # seconds

# Paths that do not require authentication
PUBLIC_PATHS = frozenset({
    "/auth/login",
    "/auth/logout",
    "/login",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# In-memory login rate limiter: key -> list of attempt timestamps
_login_attempts: dict[str, list[float]] = {}

# Test/override hooks
_force_secure_cookie: Optional[bool] = None
_signing_key_override: Optional[str] = None


@dataclass(frozen=True)
class AuthPrincipal:
    """Authenticated caller."""

    subject: str  # "admin" or api key id/name
    scope: str  # "read" | "admin"
    via: str  # "session" | "bearer"


def reset_auth_state() -> None:
    """Reset module state between tests."""
    global _login_attempts, _force_secure_cookie, _signing_key_override
    _login_attempts = {}
    _force_secure_cookie = None
    _signing_key_override = None


def set_signing_key_override(key: Optional[str]) -> None:
    """Inject session signing key for tests (bypasses keyring)."""
    global _signing_key_override
    _signing_key_override = key


def set_secure_cookie(secure: Optional[bool]) -> None:
    """Override Secure cookie flag (None = derive from request)."""
    global _force_secure_cookie
    _force_secure_cookie = secure


def _get_signing_key() -> str:
    if _signing_key_override is not None:
        return _signing_key_override
    return creds_mod.get_or_create_session_signing_key()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_signing_key(), salt="spectrax-session-v1")


def create_session_token(scope: str = "admin") -> str:
    """Create a signed session payload for the dashboard admin."""
    return _serializer().dumps({"sub": "admin", "scope": scope})


def read_session_token(token: str) -> Optional[dict[str, Any]]:
    """Validate and decode a session token. Returns None if invalid/expired."""
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str) -> Optional[AuthPrincipal]:
    """Look up a bearer key against the keyring blob. Constant-time compare."""
    entries = creds_mod.list_api_keys(include_revoked=True)
    candidate = hash_api_key(raw_key)
    for entry in entries:
        stored = entry.get("hash", "")
        if not stored:
            continue
        if secrets.compare_digest(candidate, stored):
            if entry.get("revoked_at"):
                return None
            scope = entry.get("scope", "read")
            if scope not in ("read", "admin"):
                scope = "read"
            return AuthPrincipal(
                subject=entry.get("name") or entry.get("id", "apikey"),
                scope=scope,
                via="bearer",
            )
    return None


def authenticate_request(request: Request) -> Optional[AuthPrincipal]:
    """Resolve principal from Bearer header or session cookie."""
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            principal = verify_api_key(token)
            if principal is not None:
                return principal
            # Invalid bearer — do not fall through to cookie (explicit auth attempt)
            return None

    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        payload = read_session_token(cookie)
        if payload and payload.get("sub"):
            scope = payload.get("scope", "admin")
            if scope not in ("read", "admin"):
                scope = "read"
            return AuthPrincipal(
                subject=str(payload["sub"]),
                scope=scope,
                via="session",
            )
    return None


def require_scope(principal: Optional[AuthPrincipal], needed: str) -> AuthPrincipal:
    """Raise 401/403 if principal missing or under-scoped."""
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if needed == "admin" and principal.scope != "admin":
        raise HTTPException(status_code=403, detail="Admin scope required")
    return principal


def check_login_rate_limit(client_key: str) -> None:
    """Raise 429 if client has exceeded login attempt budget."""
    now = time.time()
    window_start = now - LOGIN_RATE_WINDOW
    attempts = [t for t in _login_attempts.get(client_key, []) if t >= window_start]
    _login_attempts[client_key] = attempts
    if len(attempts) >= LOGIN_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many login attempts")


def record_login_attempt(client_key: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    attempts = _login_attempts.setdefault(client_key, [])
    attempts.append(now)


def clear_login_attempts(client_key: str) -> None:
    """Clear rate-limit history after a successful login."""
    _login_attempts.pop(client_key, None)


def cookie_secure_flag(request: Request) -> bool:
    """Whether Set-Cookie should include Secure."""
    if _force_secure_cookie is not None:
        return _force_secure_cookie
    # Explicit config flag via request app state if present
    flag = getattr(request.app.state, "secure_cookies", None)
    if flag is not None:
        return bool(flag)
    return request.url.scheme == "https"


def set_session_cookie(response: Response, token: str, request: Request) -> None:
    """Attach session cookie to a response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=cookie_secure_flag(request),
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def is_public_path(path: str) -> bool:
    """Return True if path may be accessed without auth."""
    if path in PUBLIC_PATHS:
        return True
    # Static-ish openapi assets under /docs
    if path.startswith("/docs/") or path.startswith("/redoc"):
        return True
    return False


def wants_html(request: Request) -> bool:
    """Heuristic: browser navigation wants HTML redirect to login."""
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept and "application/json" not in accept.split(",")[0]:
        return True
    # Page routes without Accept still often navigated by browser
    if request.method == "GET" and (
        path_is_page(request.url.path)
    ):
        return True
    return False


def path_is_page(path: str) -> bool:
    return path in ("/", "/recordings.html", "/login")


class AuthMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests except public auth/login routes."""

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if is_public_path(path):
            return await call_next(request)

        principal = authenticate_request(request)
        if principal is None:
            # Invalid bearer present
            auth_header = request.headers.get("Authorization") or ""
            if auth_header.lower().startswith("bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or revoked API key"},
                )
            if wants_html(request) and request.method == "GET":
                return RedirectResponse(url="/login", status_code=303)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        request.state.principal = principal
        return await call_next(request)


def get_principal(request: Request) -> Optional[AuthPrincipal]:
    """Read principal attached by middleware (or re-authenticate)."""
    principal = getattr(request.state, "principal", None)
    if principal is not None:
        return principal
    return authenticate_request(request)


async def require_read(request: Request) -> AuthPrincipal:
    """FastAPI dependency: any authenticated principal."""
    return require_scope(get_principal(request), "read")


async def require_admin(request: Request) -> AuthPrincipal:
    """FastAPI dependency: admin scope only."""
    return require_scope(get_principal(request), "admin")
