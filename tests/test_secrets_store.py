"""Unit tests for SecretsStore (Phase 2)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from spectrax.secrets import (
    FileSecretsStore,
    MemorySecretsStore,
    migrate_keyring_labels_to_file,
    select_secrets_store,
)


pytestmark = pytest.mark.unit


def test_memory_store_crud():
    store = MemorySecretsStore()
    assert store.get("x") is None
    store.set("x", "secret")
    assert store.get("x") == "secret"
    store.delete("x")
    assert store.get("x") is None


def test_file_store_mode_0600(tmp_path: Path):
    path = tmp_path / "secrets.yml"
    store = FileSecretsStore(path)
    store.set("admin_password_hash", "hashvalue")
    assert path.is_file()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    assert store.get("admin_password_hash") == "hashvalue"


def test_file_store_rejects_world_readable(tmp_path: Path):
    path = tmp_path / "secrets.yml"
    path.write_text("admin_password_hash: x\n", encoding="utf-8")
    os.chmod(path, 0o644)
    with pytest.raises(PermissionError):
        FileSecretsStore(path)


def test_credentials_facade_uses_memory(monkeypatch: pytest.MonkeyPatch):
    from spectrax import credentials as creds

    creds.use_memory_store(True)
    creds.set_admin_password("test-password-123")
    assert creds.verify_admin_password("test-password-123")
    assert not creds.verify_admin_password("wrong-password")
    raw = creds.create_api_key("t", scope="read")
    assert raw.startswith("sx_")
    assert len(creds.list_api_keys()) == 1
    creds.reset_creds()
    assert creds.get_admin_password_hash() is None
    creds.reset_memory_store()


def test_select_secrets_store_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPECTRAX_SECRETS_BACKEND", "file")
    monkeypatch.setenv("SPECTRAX_STATE_DIR", str(tmp_path))
    store = select_secrets_store()
    assert isinstance(store, FileSecretsStore)
    store.set("session_signing_key", "abc")
    assert (tmp_path / "secrets.yml").is_file()


def test_migrate_to_file(tmp_path: Path):
    src = MemorySecretsStore({"publisher": "p", "viewer": "v"})
    dst_path = tmp_path / "secrets.yml"
    dst = FileSecretsStore(dst_path)
    n = migrate_keyring_labels_to_file(src, dst)
    assert n == 2
    assert dst.get("publisher") == "p"
