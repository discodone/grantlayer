"""GrantLayer secret source boundary hardening helpers.

This module provides isolated, dependency-free helpers for safe secret lookup
from environment variables, Docker Secrets files, and HashiCorp Vault KV v2.
No secret values are ever logged, printed, or exposed in representations or
error messages.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterable
from typing import Mapping, Optional, Sequence

REDACTED_SECRET_VALUE = "[REDACTED]"
SECRET_SOURCE_ENVIRONMENT = "environment"
SECRET_SOURCE_FILE = "file"
SECRET_SOURCE_VAULT = "vault"
DOCKER_SECRETS_DEFAULT_DIR = "/run/secrets"

_SECRET_KEY_PATTERNS = frozenset(
    [
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "authorization",
        "cookie",
        "database_url",
        "db_url",
        "operator_token",
        "admin_token",
        "signing_key",
        "credential",
    ]
)


class SecretConfigurationError(Exception):
    """Raised when a required secret is missing or misconfigured.

    Safe string representation: never includes raw secret values.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"

    def __str__(self) -> str:
        return self.message


def _is_none_or_non_string(value: object) -> bool:
    """Return True if value is None or not a string."""
    return value is None or not isinstance(value, str)


def _normalize_key(key: str) -> str:
    """Normalize a key to lower-cased with underscores replacing hyphens/spaces."""
    return key.lower().replace("-", "_").replace(" ", "_")


_SECRET_KEY_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def is_secret_key(key: object) -> bool:
    """Return True if *key* looks like a secret-like identifier.

    Matching is case-insensitive and detects at least the following patterns:
    password, secret, token, api_key, private_key, authorization, cookie,
    database_url, db_url, operator_token, admin_token, signing_key, credential.

    For non-string input (e.g. None, int), returns False so callers do not leak
    arbitrary data through the exception path.
    """
    if _is_none_or_non_string(key):
        return False
    normalized = _normalize_key(str(key))
    for pattern in _SECRET_KEY_PATTERNS:
        if pattern in normalized:
            return True
    return False


def redact_secret_value(value: object) -> object:
    """Return a redacted placeholder if *value* looks like a secret.

    Preserves None and safe primitives (bool, int, float). Redacts strings
    that look like credential-like values (non-empty strings that are not
    obvious booleans or the literal REDACTED placeholder itself).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        # Unknown type — keep as-is to avoid leaking via coercion.
        return value
    stripped = value.strip()
    if not stripped:
        return value
    # If it is already the redacted placeholder, leave it.
    if stripped == REDACTED_SECRET_VALUE:
        return value
    # Strings that look like they could be secrets (any non-trivial string).
    # We err on the side of redaction because this helper is meant for safe
    # diagnostics, not for preserving all non-secret strings.
    if len(stripped) >= 1:
        return REDACTED_SECRET_VALUE
    return value


def _validate_name(name: str) -> None:
    """Validate that a secret name is safe and non-empty.

    Raises a plain ValueError that never includes raw secret values.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("secret name must be a non-empty string")


def _read_raw(name: str, env: Optional[Mapping[str, str]]) -> Optional[str]:
    """Internal helper: read a raw secret value without any exposure."""
    source = env if env is not None else os.environ
    raw = source.get(name)
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    return stripped


def read_optional_secret(
    name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Return the secret value for *name*, or None if absent or empty.

    Reads from *env* if provided, otherwise from ``os.environ``.

    The raw secret is returned only to the caller. It is never logged,
    printed, or exposed internally.
    """
    _validate_name(name)
    return _read_raw(name, env)


def read_required_secret(
    name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> str:
    """Return the secret value for *name*, raising if absent or empty.

    Reads from *env* if provided, otherwise from ``os.environ``.

    Raises ``SecretConfigurationError`` when the secret is missing. The error
    message includes the secret name but never raw secret values or environment
    dumps.
    """
    _validate_name(name)
    value = _read_raw(name, env)
    if value is None:
        raise SecretConfigurationError(
            f"required secret '{name}' is missing or empty"
        )
    return value


def describe_secret_source(
    name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> dict:
    """Return safe metadata about a secret source.

    The returned dictionary contains only:
    - ``name``: the secret name
    - ``source``: always ``"environment"``
    - ``present``: whether the secret exists and is non-empty
    - ``valuePreview``: ``"[REDACTED]"`` if present, otherwise ``None``

    Raw secret values are never included.
    """
    _validate_name(name)
    value = _read_raw(name, env)
    present = value is not None
    return {
        "name": name,
        "source": SECRET_SOURCE_ENVIRONMENT,
        "present": present,
        "valuePreview": REDACTED_SECRET_VALUE if present else None,
    }


def validate_required_secrets(
    names: Sequence[str],
    *,
    env: Optional[Mapping[str, str]] = None,
) -> dict:
    """Return a safe validation summary for a sequence of required secret names.

    The returned dictionary contains:
    - ``valid``: True if all required secrets are present and non-empty
    - ``missing``: list of missing secret names (deterministic ordering)
    - ``present``: list of present secret names (deterministic ordering)
    - ``source``: always ``"environment"``

    Raw secret values and the raw environment are never included.
    """
    _validate_name_sequence(names)
    missing: list[str] = []
    present: list[str] = []
    for name in names:
        if _read_raw(name, env) is None:
            missing.append(name)
        else:
            present.append(name)
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present,
        "source": SECRET_SOURCE_ENVIRONMENT,
    }


def _validate_name_sequence(names: object) -> None:
    """Validate that *names* is an iterable of non-empty strings."""
    if names is None:
        raise ValueError("names must be a sequence of non-empty strings")
    if not isinstance(names, Iterable):
        raise ValueError("names must be a sequence of non-empty strings")
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("names must be a sequence of non-empty strings")


# ─────────────────────────────────────────────────────────────────────────────
# Docker Secrets / file-based secret sources
# ─────────────────────────────────────────────────────────────────────────────


def read_file_secret(path: str) -> Optional[str]:
    """Read a secret from *path*, returning the stripped value or None.

    Returns None when the file does not exist or is empty/whitespace-only.
    Raises ValueError for empty or non-string path.
    Raises SecretConfigurationError on permission or OS errors (never forwards
    the raw OS error reason into the exception message).
    """
    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if not path:
        raise ValueError("path must be a non-empty string")
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    except PermissionError:
        raise SecretConfigurationError("permission denied reading secret file")
    except OSError:
        raise SecretConfigurationError("error reading secret file")
    stripped = content.strip()
    return stripped if stripped else None


def read_docker_secret(
    name: str,
    *,
    secrets_dir: str = DOCKER_SECRETS_DEFAULT_DIR,
) -> Optional[str]:
    """Read secret *name* from the Docker Secrets directory.

    Raises ValueError for empty name or secrets_dir.
    Returns None when the file is absent or empty.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("secret name must be a non-empty string")
    if not isinstance(secrets_dir, str) or not secrets_dir.strip():
        raise ValueError("secrets_dir must be a non-empty string")
    return read_file_secret(os.path.join(secrets_dir, name))


def describe_file_secret_source(
    name: str,
    *,
    secrets_dir: str = DOCKER_SECRETS_DEFAULT_DIR,
) -> dict:
    """Return safe metadata for the Docker Secret *name* (no secret values)."""
    path = os.path.join(secrets_dir, name)
    try:
        value = read_file_secret(path)
    except SecretConfigurationError:
        value = None
    present = value is not None
    return {
        "name": name,
        "source": SECRET_SOURCE_FILE,
        "present": present,
        "valuePreview": REDACTED_SECRET_VALUE if present else None,
        "path": path,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HashiCorp Vault KV v2
# ─────────────────────────────────────────────────────────────────────────────


class VaultSecretReader:
    """Reads secrets from HashiCorp Vault KV v2 using urllib (no extra deps).

    Token is never included in __repr__ or error messages.
    """

    def __init__(
        self,
        addr: str,
        token: str,
        mount: str = "secret",
        path_prefix: str = "",
    ) -> None:
        self._addr = addr.rstrip("/")
        self._token = token
        self._mount = mount
        self._path_prefix = path_prefix

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
    ) -> Optional["VaultSecretReader"]:
        """Construct from env dict (or os.environ if None).  Returns None when not configured."""
        source: Mapping[str, str] = env if env is not None else os.environ
        addr = source.get("GRANTLAYER_VAULT_ADDR", "").strip()
        token = source.get("GRANTLAYER_VAULT_TOKEN", "").strip()
        if not addr or not token:
            return None
        mount = source.get("GRANTLAYER_VAULT_MOUNT", "secret").strip() or "secret"
        path_prefix = source.get("GRANTLAYER_VAULT_PATH", "").strip()
        return cls(addr=addr, token=token, mount=mount, path_prefix=path_prefix)

    def _build_url(self, name: str) -> str:
        if self._path_prefix:
            path = f"{self._path_prefix}/{name}"
        else:
            path = name
        return f"{self._addr}/v1/{self._mount}/data/{path}"

    def read(self, name: str) -> Optional[str]:
        """Fetch *name* from Vault KV v2.  Returns None on 404, raises on errors."""
        url = self._build_url(name)
        req = urllib.request.Request(url, headers={"X-Vault-Token": self._token})
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code == 403:
                raise SecretConfigurationError(
                    f"Vault 403 permission denied reading secret '{name}'"
                )
            raise SecretConfigurationError(
                f"Vault {exc.code} error reading secret '{name}'"
            )
        except urllib.error.URLError:
            raise SecretConfigurationError(
                f"Vault connection error reading secret '{name}'"
            )
        try:
            data = json.loads(body)
            return data["data"]["data"].get(name)
        except (json.JSONDecodeError, KeyError, TypeError):
            raise SecretConfigurationError(
                f"Vault response malformed reading secret '{name}'"
            )

    def describe(self, name: str) -> dict:
        """Return safe metadata for *name* (never includes token or value)."""
        try:
            value = self.read(name)
            present = value is not None
        except SecretConfigurationError:
            present = False
        return {
            "source": SECRET_SOURCE_VAULT,
            "present": present,
            "valuePreview": REDACTED_SECRET_VALUE if present else None,
        }

    def __repr__(self) -> str:
        return (
            f"VaultSecretReader(addr={self._addr!r}, mount={self._mount!r}, "
            f"path_prefix={self._path_prefix!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SecretResolver — priority chain: Vault > file > environment
# ─────────────────────────────────────────────────────────────────────────────


class SecretResolver:
    """Resolves secrets in priority order: Vault > Docker Secret file > env var."""

    def __init__(
        self,
        vault: Optional[VaultSecretReader],
        secrets_dir: str,
        env: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._vault = vault
        self._secrets_dir = secrets_dir
        self._env = env  # None → use os.environ at resolution time

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
    ) -> "SecretResolver":
        """Build a resolver from *env* (or os.environ when None)."""
        source: Mapping[str, str] = env if env is not None else os.environ
        vault = VaultSecretReader.from_env(source)
        secrets_dir = (
            source.get("GRANTLAYER_SECRETS_DIR", "").strip() or DOCKER_SECRETS_DEFAULT_DIR
        )
        return cls(vault=vault, secrets_dir=secrets_dir, env=env)

    def resolve(self, name: str) -> Optional[str]:
        """Return the secret value from the highest-priority source, or None."""
        if self._vault is not None:
            try:
                value = self._vault.read(name)
                if value is not None:
                    return value
            except SecretConfigurationError:
                pass

        try:
            value = read_docker_secret(name, secrets_dir=self._secrets_dir)
            if value is not None:
                return value
        except (SecretConfigurationError, ValueError):
            pass

        live_env: Mapping[str, str] = self._env if self._env is not None else os.environ
        raw = live_env.get(name, "").strip()
        return raw if raw else None

    def resolve_required(self, name: str) -> str:
        """Return the secret value or raise SecretConfigurationError when absent."""
        value = self.resolve(name)
        if value is None:
            raise SecretConfigurationError(
                f"required secret '{name}' is missing from all sources"
            )
        return value

    def describe_sources(self) -> dict:
        """Return safe configuration metadata (no tokens or secret values)."""
        vault_configured = self._vault is not None
        vault_addr = self._vault._addr if self._vault is not None else None
        return {
            "vault": {"configured": vault_configured, "addr": vault_addr},
            "file": {"configured": True, "secretsDir": self._secrets_dir},
            "environment": {"configured": True},
            "sources": [SECRET_SOURCE_VAULT, SECRET_SOURCE_FILE, SECRET_SOURCE_ENVIRONMENT],
        }

    def __repr__(self) -> str:
        return (
            f"SecretResolver(vault_configured={self._vault is not None!r}, "
            f"secrets_dir={self._secrets_dir!r})"
        )
