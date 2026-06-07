"""GrantLayer MVP — Structured logging utilities (stdlib only).

GL-113: Minimal structured logging baseline using Python stdlib logging.
No external dependencies. No OpenTelemetry. No metrics/tracing platform.
"""

from __future__ import annotations

import json
import logging

# ──────────────────────────────────────────────────────────────
# Field allowlists / blocklists
# ──────────────────────────────────────────────────────────────

_SAFE_FIELDS: set[str] = {
    "event",
    "component",
    "action",
    "status",
    "method",
    "path",
    "status_code",
    "correlation_id",
    "request_id",
    "exception_type",
    "reason_code",
    "operator_id",
    "tenant_id",
}

_SENSITIVE_FIELDS: set[str] = {
    "authorization",
    "cookie",
    "token",
    "admin_token",
    "operator_token",
    "raw_token",
    "token_hash",
    "token_lookup_hash",
    "password",
    "passphrase",
    "private_key",
    "secret",
    "signature",
    "request_body",
    "body",
    "evidence",
    "payload",
    "database_url",
    "connection_string",
    "dsn",
    "stack_trace",
}

_REDACTED = "[REDACTED]"


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger for the given name."""
    return logging.getLogger(name)


def sanitize_log_fields(fields: dict) -> dict:
    """Return a sanitized copy of *fields*.

    - Safe fields are preserved.
    - Sensitive fields are replaced with ``[REDACTED]``.
    - Unknown fields are omitted.
    - Non-dict input returns an empty dict.
    """
    if not isinstance(fields, dict):
        return {}

    result: dict = {}
    for key, value in fields.items():
        key_lower = key.lower()
        if key_lower in _SENSITIVE_FIELDS:
            result[key] = _REDACTED
        elif key_lower in _SAFE_FIELDS:
            result[key] = value
        # Unknown fields are silently dropped
    return result


def build_log_record(event: str, **fields) -> str:
    """Build a deterministic structured log payload as a JSON string.

    Keys are sorted for determinism. Sensitive fields are redacted.
    Unknown fields are dropped. Unserializable values are safely converted.
    Raw exception messages are never emitted — only *exception_type* is safe.
    """
    record: dict = {"event": event}

    for key in sorted(fields.keys()):
        key_lower = key.lower()
        if key_lower in _SENSITIVE_FIELDS:
            record[key] = _REDACTED
        elif key_lower in _SAFE_FIELDS:
            record[key] = _safe_value(fields[key])
        # Unknown fields are dropped

    try:
        # Manually build ordered dict so "event" is always first, rest sorted
        ordered = {"event": record.pop("event")}
        for key in sorted(record.keys()):
            ordered[key] = record[key]
        return json.dumps(ordered, sort_keys=False, default=_safe_default, separators=(",", ":"))
    except (TypeError, ValueError):
        # Ultimate fallback — never leak user data on serialization failure
        return json.dumps(
            {"event": event, "_error": "serialization_failed"},
            sort_keys=True,
            separators=(",", ":"),
        )


def safe_log(logger: logging.Logger, level: str, event: str, **fields) -> None:
    """Log a structured event safely.

    - Never logs raw exception messages (only *exception_type*).
    - Redacts sensitive fields.
    - Drops unknown fields.
    - Never raises — fails safe.
    """
    try:
        payload = build_log_record(event, **fields)
        log_method = getattr(logger, level.lower(), logger.info)
        log_method("%s", payload)
    except Exception:
        # Failsafe: log the absolute minimum without any user data
        try:
            logger.error("safe_log_failed event=%s", event)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────

def _safe_value(value):
    """Return a safe serializable value."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _safe_value(v) for k, v in value.items()}
    return _safe_default(value)


def _safe_default(obj):
    """Default serializer for json.dumps."""
    try:
        return str(obj)
    except Exception:
        return "[UNSERIALIZABLE]"
