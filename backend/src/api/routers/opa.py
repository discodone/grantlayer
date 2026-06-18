"""OPA policy enforcement FastAPI dependency."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ...policy.opa_client import evaluate_policy


async def require_policy(
    action: str,
    subject: dict[str, Any],
    resource: dict[str, Any],
) -> None:
    """FastAPI dependency: enforce OPA policy.

    Falls back to existing role checks if OPA is unreachable (graceful degradation).
    Raises 403 if OPA explicitly denies.
    """
    allowed = await evaluate_policy(action, subject, resource)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "policy_denied",
                "reason": f"Policy denied action '{action}'.",
            },
        )
