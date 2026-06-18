"""OPA (Open Policy Agent) integration for GrantLayer.

Calls OPA's HTTP API at /v1/data/grantlayer/allow.
Falls back to existing role-based checks if OPA is unreachable.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("grantlayer.opa")

_OPA_URL_ENV = "GRANTLAYER_OPA_URL"
_DEFAULT_OPA_URL = "http://localhost:8181"
_OPA_TIMEOUT = 2.0  # seconds


def _get_opa_url() -> Optional[str]:
    return os.environ.get(_OPA_URL_ENV)


async def evaluate_policy(
    action: str,
    subject: dict[str, Any],
    resource: dict[str, Any],
) -> bool:
    """Call OPA to evaluate allow/deny.

    Args:
        action: The action being requested (e.g., 'grant.create').
        subject: Caller context (role, workspace_id, tenant_id, scopes).
        resource: Resource being acted on (workspace_id, tenant_id).

    Returns:
        True if allowed, False if denied.
        Falls back to True (allow) with a warning if OPA is unreachable.
    """
    opa_url = _get_opa_url()
    if not opa_url:
        return True  # OPA not configured; skip

    payload = {
        "input": {
            "action": action,
            "subject": subject,
            "resource": resource,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=_OPA_TIMEOUT) as client:
            response = await client.post(
                f"{opa_url}/v1/data/grantlayer/allow",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return bool(result.get("result", False))
    except httpx.ConnectError:
        logger.warning(
            "opa_unreachable",
            extra={"opa_url": opa_url, "action": action},
        )
        return True  # graceful fallback: allow when OPA unreachable
    except Exception as exc:
        logger.warning(
            "opa_error",
            extra={"opa_url": opa_url, "action": action, "error": str(exc)},
        )
        return True  # graceful fallback


def evaluate_policy_sync(
    action: str,
    subject: dict[str, Any],
    resource: dict[str, Any],
) -> bool:
    """Synchronous OPA evaluation (uses httpx sync client)."""
    opa_url = _get_opa_url()
    if not opa_url:
        return True

    payload = {
        "input": {
            "action": action,
            "subject": subject,
            "resource": resource,
        }
    }

    try:
        with httpx.Client(timeout=_OPA_TIMEOUT) as client:
            response = client.post(
                f"{opa_url}/v1/data/grantlayer/allow",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return bool(result.get("result", False))
    except Exception as exc:
        logger.warning(
            "opa_error_sync",
            extra={"opa_url": opa_url, "action": action, "error": str(exc)},
        )
        return True  # graceful fallback
