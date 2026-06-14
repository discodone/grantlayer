"""GrantLayer MVP — Structured logging utilities (stdlib only).

Minimal structured logging baseline using Python stdlib logging.
No external dependencies. No OpenTelemetry. No metrics/tracing platform.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_correlation_id_var: ContextVar[str | None] = ContextVar(
    "grantlayer_correlation_id",
    default=None,
)
_LOGGING_CONFIGURED = False
_LOG_LEVEL_ENV = "GRANTLAYER_LOG_LEVEL"
_DEFAULT_LOG_LEVEL = "INFO"

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
    "duration_ms",
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
    _configure_logging()
    return logging.getLogger(name)


def get_correlation_id() -> str | None:
    """Return the current request correlation ID, if one is available."""
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: str):
    """Set the current request correlation ID and return a reset token."""
    return _correlation_id_var.set(correlation_id)


def reset_correlation_id(token) -> None:
    """Reset the current request correlation ID from a contextvars token."""
    _correlation_id_var.reset(token)


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
        current_correlation_id = get_correlation_id()
        if "correlation_id" not in fields and current_correlation_id is not None:
            fields["correlation_id"] = current_correlation_id

        payload = build_log_record(event, **fields)
        extra = sanitize_log_fields(fields)
        extra["event"] = event
        log_method = getattr(logger, level.lower(), logger.info)
        log_method("%s", payload, extra=extra)
    except Exception:
        # Failsafe: log the absolute minimum without any user data
        try:
            logger.error("safe_log_failed event=%s", event)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# JSON formatter / logging configuration
# ──────────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Format log records as GrantLayer JSON log lines."""

    _reserved = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "correlation_id": correlation_id,
            "module": record.name,
        }

        for key, value in record.__dict__.items():
            if key in self._reserved or key in payload:
                continue
            if key.lower() in _SENSITIVE_FIELDS:
                payload[key] = _REDACTED
            else:
                payload[key] = _safe_value(value)

        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type is not None:
                payload["exception_type"] = exc_type.__name__

        return json.dumps(payload, sort_keys=False, default=_safe_default, separators=(",", ":"))


def _configure_logging() -> None:
    """Configure process-wide stdlib logging once."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    level_name = os.getenv(_LOG_LEVEL_ENV, _DEFAULT_LOG_LEVEL).strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    if not isinstance(level, int):
        level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler.setLevel(level)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    _LOGGING_CONFIGURED = True


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
