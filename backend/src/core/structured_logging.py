"""
GrantLayer structured logging and correlation ID helper.

Provides safe structured event construction, correlation ID generation/normalization,
and deterministic metadata redaction. Dependency-free except Python standard library.
"""

import datetime
import re
import uuid
from typing import Any, Mapping, Optional, TypeGuard

DEFAULT_SERVICE_NAME = "grantlayer"

SUPPORTED_EVENT_TYPES = frozenset([
    "api_request",
    "api_error",
    "auth_event",
    "permission_decision",
    "evidence_verification",
    "approval_transition",
    "policy_evaluation",
    "persistence_operation",
    "configuration_event",
    "operator_action",
    "health_check",
    "readiness_check",
])

SUPPORTED_SEVERITIES = frozenset([
    "debug",
    "info",
    "warning",
    "error",
    "critical",
])

_MAX_ID_LENGTH = 128
_MAX_DEPTH = 10
_REDACTED_MARKER = "[REDACTED]"

# Safe ID characters: letters, digits, underscore, dash, dot, colon
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")

# Sensitive key substrings that trigger unconditional redaction
_SENSITIVE_KEY_SUBSTRINGS = frozenset([
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
])

# Known safe runtime modes (self-contained)
_SAFE_RUNTIME_MODES = frozenset([
    "local",
    "test",
    "demo",
    "staging",
    "production",
])


def generate_correlation_id() -> str:
    """Return a safe random UUID-style correlation ID.

    Does not encode secrets, timestamps with sensitive meaning, hostname,
    username, PID, or environment information.
    """
    return uuid.uuid4().hex


def _is_safe_id(value: Optional[str]) -> TypeGuard[str]:
    """Check whether a string is a safe ID without generating a replacement."""
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if len(stripped) > _MAX_ID_LENGTH:
        return False
    return bool(_SAFE_ID_RE.match(stripped))


def normalize_correlation_id(value: Optional[str]) -> str:
    """Normalize a correlation ID to a safe value.

    If the value is absent, empty, whitespace-only, too long, or contains
    unsafe characters, return a newly generated correlation ID.
    Does not include raw unsafe input in error messages.
    """
    if value is None:
        return generate_correlation_id()
    stripped = value.strip()
    if not stripped:
        return generate_correlation_id()
    if len(stripped) > _MAX_ID_LENGTH:
        return generate_correlation_id()
    if not _SAFE_ID_RE.match(stripped):
        return generate_correlation_id()
    return stripped


def _is_sensitive_key(key: str) -> bool:
    """Determine whether a dict key indicates sensitive data."""
    lowered = key.lower()
    return any(sub in lowered for sub in _SENSITIVE_KEY_SUBSTRINGS)


def _looks_like_secret(value: str) -> bool:
    """Heuristic to detect secret-like string values."""
    v = value.strip()
    if v.startswith("Bearer "):
        return True
    if v.startswith("Basic "):
        return True
    if "-----BEGIN" in v:
        return True
    if "-----END" in v:
        return True
    if v.startswith("postgres://"):
        return True
    if v.startswith("mysql://"):
        return True
    if v.startswith("mongodb://"):
        return True
    if v.startswith("redis://"):
        return True
    if v.startswith("amqp://"):
        return True
    if v.startswith("sqlite://"):
        return True
    if v.startswith("sk-"):
        return True
    if v.startswith("ak_"):
        return True
    if v.startswith("pk_"):
        return True
    if v.startswith("rk_"):
        return True
    if "private_key" in v.lower():
        return True
    return False


def redact_log_value(value: object, _depth: int = 0) -> object:
    """Redact sensitive values in metadata recursively.

    - Values under keys containing sensitive substrings are fully redacted.
    - Strings that look like secrets (bearer tokens, private keys, DB URLs,
      API keys, etc.) are replaced with a redaction marker.
    - Nested dicts and lists are processed recursively up to a safe depth limit.
    - Safe scalars (int, float, bool, None) are preserved.
    - If the depth limit is reached, a safe redaction marker is returned.

    The function is deterministic: the same input always produces the same output.
    """
    if _depth >= _MAX_DEPTH:
        return _REDACTED_MARKER

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                result[k] = _REDACTED_MARKER
            else:
                result[k] = redact_log_value(v, _depth=_depth + 1)
        return result
    elif isinstance(value, list):
        return [redact_log_value(item, _depth=_depth + 1) for item in value]
    elif isinstance(value, str):
        if _looks_like_secret(value):
            return _REDACTED_MARKER
        return value
    elif isinstance(value, (int, float, bool)) or value is None:
        return value
    else:
        # For other types, convert to string and check for secret patterns
        s = str(value)
        if _looks_like_secret(s):
            return _REDACTED_MARKER
        return s


def build_request_context(
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> dict:
    """Return a safe request context dictionary with normalized correlation IDs.

    - correlationId is always present (generated if missing).
    - requestId, workflowId, executionId, actorId, and agentId are included
      only when the provided value is safe.
    - Raw unsafe inputs are never exposed.
    """
    context: dict[str, Any] = {
        "correlationId": normalize_correlation_id(correlation_id),
    }

    if _is_safe_id(request_id):
        context["requestId"] = request_id.strip()
    if _is_safe_id(workflow_id):
        context["workflowId"] = workflow_id.strip()
    if _is_safe_id(execution_id):
        context["executionId"] = execution_id.strip()
    if _is_safe_id(actor_id):
        context["actorId"] = actor_id.strip()
    if _is_safe_id(agent_id):
        context["agentId"] = agent_id.strip()

    return context


def _normalize_severity(severity: str) -> str:
    """Normalize and validate severity.

    Returns lowercased severity if supported.
    Raises safe ValueError for unknown or empty severity.
    Error messages never include raw unsafe input.
    """
    normalized = severity.strip().lower()
    if normalized not in SUPPORTED_SEVERITIES:
        raise ValueError(
            "Unsupported severity. Supported severities are: "
            f"{', '.join(sorted(SUPPORTED_SEVERITIES))}."
        )
    return normalized


def _is_safe_runtime_mode(value: str) -> bool:
    """Check whether a runtime mode string is safe and known."""
    stripped = value.strip().lower()
    return stripped in _SAFE_RUNTIME_MODES


def build_log_event(
    event_type: str,
    message: str,
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    runtime_mode: Optional[str] = None,
    severity: str = "info",
    metadata: Optional[Mapping[str, object]] = None,
) -> dict:
    """Build a safe structured log event dictionary.

    Validates event_type against supported event types and severity against
    supported severities. Normalizes correlation IDs and redacts sensitive
    metadata values. Never exposes raw secrets, tokens, private keys,
    database URLs, credentials, or full evidence payloads.

    Returns a JSON-serializable dictionary.
    """
    normalized_type = event_type.strip().lower()
    if normalized_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            "Unsupported event type. Supported event types are: "
            f"{', '.join(sorted(SUPPORTED_EVENT_TYPES))}."
        )

    normalized_severity = _normalize_severity(severity)

    event: dict[str, Any] = {
        "eventType": normalized_type,
        "message": message,
        "severity": normalized_severity,
        "service": DEFAULT_SERVICE_NAME,
        "correlationId": normalize_correlation_id(correlation_id),
        "timestamp": (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        ),
    }

    if _is_safe_id(request_id):
        event["requestId"] = request_id.strip()
    if _is_safe_id(workflow_id):
        event["workflowId"] = workflow_id.strip()
    if _is_safe_id(execution_id):
        event["executionId"] = execution_id.strip()
    if _is_safe_id(actor_id):
        event["actorId"] = actor_id.strip()
    if _is_safe_id(agent_id):
        event["agentId"] = agent_id.strip()
    if runtime_mode is not None and _is_safe_runtime_mode(runtime_mode):
        event["runtimeMode"] = runtime_mode.strip().lower()

    if metadata is not None:
        event["metadata"] = redact_log_value(dict(metadata))

    return event
