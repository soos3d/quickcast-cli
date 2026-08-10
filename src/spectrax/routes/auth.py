"""Authentication routes: login / logout (session cookie)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from spectrax import credentials as creds_mod
from spectrax.auth_gate import (
    check_login_rate_limit,
    clear_login_attempts,
    clear_session_cookie,
    create_session_token,
    record_login_attempt,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Dashboard login body."""

    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Successful login."""

    authenticated: bool = True
    scope: str = "admin"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    """Authenticate admin password and set session cookie."""
    client_key = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_key)

    admin_hash = creds_mod.get_admin_password_hash()
    if not admin_hash:
        raise HTTPException(
            status_code=503,
            detail="Admin password not configured. Run: spectrax admin set-password",
        )

    if not creds_mod.verify_admin_password(body.password):
        record_login_attempt(client_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    clear_login_attempts(client_key)
    token = create_session_token(scope="admin")
    set_session_cookie(response, token, request)
    return LoginResponse(authenticated=True, scope="admin")


@router.post("/logout")
async def logout(response: Response):
    """Clear the session cookie."""
    clear_session_cookie(response)
    return {"authenticated": False}
