"""Admin-only FastAPI dependency — raises 403 for non-admin callers."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException

from ..auth.auth import check_admin_token


def _get_authorization(authorization: Annotated[Optional[str], Header()] = None) -> Optional[str]:
    return authorization


def require_admin_user(authorization: str = Depends(_get_authorization)) -> dict:
    """FastAPI dependency: validates admin token, raises 403 for non-admin."""
    ok, status, payload = check_admin_token(authorization)
    if not ok:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "admin_required",
                "reason": "Admin access required.",
            },
        )
    return payload
