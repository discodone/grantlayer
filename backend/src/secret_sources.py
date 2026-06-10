"""GrantLayer secret source boundary hardening helpers.

This module provides isolated, dependency-free helpers for safe secret lookup
and validation. It does not integrate with vault/KMS/cloud secret managers,
does not change server or API behavior, and does not expose secret values in
representations or error messages.
"""

from __future__ import annotations

import os
import re
from typing import Mapping, Optional, Sequence

REDACTED_SECRET_VALUE = "[REDACTED]"
SECRET_SOURCE_ENVIRONMENT = "environment"

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
    try:
        iterable = iter(names)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError("names must be a sequence of non-empty strings") from exc
    for name in iterable:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("names must be a sequence of non-empty strings")
