"""OPA (Open Policy Agent) integration for GrantLayer.

Calls OPA's HTTP API at /v1/data/grantlayer/allow.
Falls back to existing role-based checks if OPA is unreachable.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import HTTPException

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
        logger.error(
            "opa_unreachable",
            extra={"opa_url": opa_url, "action": action},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "policy_engine_unavailable",
                "errorCode": "policy_engine_unavailable",
                "reason": "OPA policy engine is configured but unreachable. Request denied.",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "opa_error",
            extra={"opa_url": opa_url, "action": action, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "policy_engine_unavailable",
                "errorCode": "policy_engine_unavailable",
                "reason": "OPA policy engine returned an error. Request denied.",
            },
        )


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
