"""Credential management for stream (MediaMTX) and API (dashboard) secrets.

Backed by :mod:`spectrax.secrets` stores. Tests use :func:`use_memory_store`.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .secrets import (
    LABEL_ADMIN_HASH,
    LABEL_API_KEYS,
    LABEL_PUBLISHER,
    LABEL_SESSION_KEY,
    LABEL_VIEWER,
    KNOWN_LABELS,
    MemorySecretsStore,
    SecretsStore,
    select_secrets_store,
)

ALL_SECRET_LABELS = KNOWN_LABELS

# Process-wide default store (tests override via use_memory_store)
_store: Optional[SecretsStore] = None
_memory_mode: bool = False


def get_store() -> SecretsStore:
    """Return the active secrets store (lazy-selected)."""
    global _store
    if _store is None:
        _store = select_secrets_store("memory" if _memory_mode else None)
    return _store


def set_store(store: SecretsStore) -> None:
    """Install a process-wide secrets store (tests / app factory)."""
    global _store, _memory_mode
    _store = store
    _memory_mode = isinstance(store, MemorySecretsStore)


def use_memory_store(enabled: bool = True) -> Dict[str, str]:
    """Enable an in-memory secrets backend for tests. Returns the backing dict."""
    global _store, _memory_mode
    if enabled:
        mem = MemorySecretsStore()
        _store = mem
        _memory_mode = True
        return mem._data
    _store = None
    _memory_mode = False
    return {}


def reset_memory_store() -> None:
    """Clear and disable the in-memory store."""
    global _store, _memory_mode
    _store = None
    _memory_mode = False


def _get_password(label: str) -> Optional[str]:
    return get_store().get(label)


def _set_password(label: str, value: str) -> None:
    get_store().set(label, value)


def _delete_password(label: str) -> None:
    get_store().delete(label)


def rand_secret() -> str:
    """Return a 32-char, URL-safe random secret."""
    return secrets.token_urlsafe(24)


def get_secret(label: str) -> str:
    """Fetch or generate a secret stored in the active store."""
    secret = _get_password(label)
    if not secret:
        secret = rand_secret()
        _set_password(label, secret)
    return secret


def get_credentials() -> Dict[str, str]:
    """Return publisher and viewer stream credentials (MediaMTX)."""
    return {
        "publish_user": "publisher",
        "publish_pass": get_secret(LABEL_PUBLISHER),
        "read_user": "viewer",
        "read_pass": get_secret(LABEL_VIEWER),
    }


def reset_creds() -> None:
    """Clear all stored secrets (stream + API + session)."""
    for label in ALL_SECRET_LABELS:
        _delete_password(label)


def get_or_create_session_signing_key() -> str:
    """Return the session cookie signing key, generating once if missing."""
    existing = _get_password(LABEL_SESSION_KEY)
    if existing:
        return existing
    key = secrets.token_urlsafe(32)
    _set_password(LABEL_SESSION_KEY, key)
    return key


def hash_password(password: str) -> str:
    """Hash a password with argon2."""
    from argon2 import PasswordHasher

    return PasswordHasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against argon2 hash. Never raises for bad password."""
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerifyMismatchError

    try:
        return PasswordHasher().verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def set_admin_password(password: str) -> None:
    """Store argon2 hash of the admin dashboard password."""
    if not password or len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters")
    _set_password(LABEL_ADMIN_HASH, hash_password(password))


def get_admin_password_hash() -> Optional[str]:
    """Return admin password hash, or None if not configured."""
    return _get_password(LABEL_ADMIN_HASH)


def verify_admin_password(password: str) -> bool:
    """Check password against stored admin hash. False if unset or wrong."""
    stored = get_admin_password_hash()
    if not stored:
        return False
    return verify_password(password, stored)


def _load_api_keys() -> List[Dict[str, Any]]:
    raw = _get_password(LABEL_API_KEYS)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _save_api_keys(entries: List[Dict[str, Any]]) -> None:
    _set_password(LABEL_API_KEYS, json.dumps(entries))


def create_api_key(name: str, scope: str = "read") -> str:
    """Create an API key. Returns the raw key once (sx_...). Stores only the hash."""
    if scope not in ("read", "admin"):
        raise ValueError("scope must be 'read' or 'admin'")
    from .auth_gate import hash_api_key

    raw = "sx_" + secrets.token_urlsafe(32)
    entry = {
        "id": str(uuid.uuid4()),
        "name": name,
        "hash": hash_api_key(raw),
        "scope": scope,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "revoked_at": None,
    }
    entries = _load_api_keys()
    entries.append(entry)
    _save_api_keys(entries)
    return raw


def list_api_keys(include_revoked: bool = False) -> List[Dict[str, Any]]:
    """List API key metadata (never includes raw secrets)."""
    entries = _load_api_keys()
    if include_revoked:
        return list(entries)
    return [e for e in entries if not e.get("revoked_at")]


def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key by id. Returns True if found."""
    entries = _load_api_keys()
    found = False
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        if entry.get("id") == key_id or entry.get("name") == key_id:
            if not entry.get("revoked_at"):
                entry["revoked_at"] = now
            found = True
    if found:
        _save_api_keys(entries)
    return found


def load_config_credentials(config_path) -> Dict[str, str]:
    """Load credentials from an existing mediamtx.yml file."""
    import typer
    import yaml

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        creds: Dict[str, str] = {}
        if "authInternalUsers" in config:
            for user_info in config["authInternalUsers"]:
                if user_info.get("permissions"):
                    for perm in user_info["permissions"]:
                        if perm.get("action") == "publish":
                            creds["publish_user"] = user_info["user"]
                            creds["publish_pass"] = user_info["pass"]
                        elif perm.get("action") == "read":
                            creds["read_user"] = user_info["user"]
                            creds["read_pass"] = user_info["pass"]

        required_keys = ["publish_user", "publish_pass", "read_user", "read_pass"]
        if not all(k in creds for k in required_keys):
            typer.secho("Missing required credentials in config", fg=typer.colors.RED)
            raise typer.Exit(1)

        return creds
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"Failed to load credentials: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from e
