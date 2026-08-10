"""SecretsStore protocol and backends (Phase 2).

Stream and API secrets never live in YAML. Headless Linux uses a mode-0600
file store; macOS/desktop uses the OS keychain by default.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Dict, Optional, Protocol, runtime_checkable

import yaml

from .constants import KEYCHAIN_SERVICE
from .paths import state_dir

# Labels shared with credentials facade
LABEL_PUBLISHER = "publisher"
LABEL_VIEWER = "viewer"
LABEL_ADMIN_HASH = "admin_password_hash"
LABEL_SESSION_KEY = "session_signing_key"
LABEL_API_KEYS = "api_keys"

KNOWN_LABELS = (
    LABEL_PUBLISHER,
    LABEL_VIEWER,
    LABEL_ADMIN_HASH,
    LABEL_SESSION_KEY,
    LABEL_API_KEYS,
)


@runtime_checkable
class SecretsStore(Protocol):
    def get(self, label: str) -> Optional[str]: ...

    def set(self, label: str, value: str) -> None: ...

    def delete(self, label: str) -> None: ...


class MemorySecretsStore:
    """In-memory store for tests."""

    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self._data: Dict[str, str] = dict(initial or {})

    def get(self, label: str) -> Optional[str]:
        return self._data.get(label)

    def set(self, label: str, value: str) -> None:
        self._data[label] = value

    def delete(self, label: str) -> None:
        self._data.pop(label, None)


class FileSecretsStore:
    """YAML file secrets store. File must be mode 0600 (fail closed if wider)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if self.path.exists():
            self._assert_mode()
            self._data = self._read()
        else:
            self._data = {}
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _assert_mode(self) -> None:
        mode = stat.S_IMODE(self.path.stat().st_mode)
        if mode & 0o077:
            raise PermissionError(
                f"Secrets file {self.path} mode is {oct(mode)}; "
                "must be 0600 (not group/other readable)"
            )

    def _read(self) -> Dict[str, str]:
        with open(self.path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            return {}
        return {str(k): str(v) for k, v in raw.items() if v is not None}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, default_flow_style=False)
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)

    def get(self, label: str) -> Optional[str]:
        return self._data.get(label)

    def set(self, label: str, value: str) -> None:
        self._data[label] = value
        self._write()

    def delete(self, label: str) -> None:
        if label in self._data:
            del self._data[label]
            self._write()


class KeyringSecretsStore:
    """OS keychain store (macOS Keychain, etc.)."""

    def __init__(self, service: str = KEYCHAIN_SERVICE) -> None:
        self.service = service

    def get(self, label: str) -> Optional[str]:
        import keyring

        return keyring.get_password(self.service, label)

    def set(self, label: str, value: str) -> None:
        import keyring

        keyring.set_password(self.service, label, value)

    def delete(self, label: str) -> None:
        import keyring

        try:
            keyring.delete_password(self.service, label)
        except Exception:
            # keyring.errors.PasswordDeleteError and missing entries
            pass


def default_secrets_path() -> Path:
    return state_dir() / "secrets.yml"


def select_secrets_store(
    backend: Optional[str] = None,
    *,
    file_path: Optional[Path] = None,
) -> SecretsStore:
    """Select secrets backend.

    ``SPECTRAX_SECRETS_BACKEND``: ``file`` | ``keyring`` | ``auto`` (default).
    auto → keyring on macOS, file elsewhere.
    """
    choice = (backend or os.environ.get("SPECTRAX_SECRETS_BACKEND") or "auto").lower()
    if choice == "auto":
        choice = "keyring" if sys.platform == "darwin" else "file"
    if choice == "file":
        return FileSecretsStore(file_path or default_secrets_path())
    if choice == "keyring":
        return KeyringSecretsStore()
    if choice == "memory":
        return MemorySecretsStore()
    raise ValueError(f"Unknown secrets backend: {choice}")


def migrate_keyring_labels_to_file(
    src: SecretsStore,
    dst: FileSecretsStore,
    labels: tuple[str, ...] = KNOWN_LABELS,
) -> int:
    """Copy known labels from src to dst. Returns count migrated. Never logs values."""
    count = 0
    for label in labels:
        value = src.get(label)
        if value is not None and dst.get(label) is None:
            dst.set(label, value)
            count += 1
    return count
