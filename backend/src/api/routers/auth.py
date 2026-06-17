"""/auth/token endpoint — exchange credentials for a JWT."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...auth.auth import check_admin_token, check_auth
from ...core import config
from ..auth_jwt import is_jwt_enabled, sign_token

router = APIRouter(prefix="/auth", tags=["auth"])

_TTL_HOURS = 1


class TokenRequest(BaseModel):
    operator_id: str
    secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = _TTL_HOURS * 3600


@router.post("/token", response_model=TokenResponse)
async def issue_token(request: Request, body: TokenRequest) -> Any:
    """Exchange operator credentials for a JWT Bearer token.

    The `secret` field accepts either the GRANTLAYER_ADMIN_TOKEN or, when
    the operator model is enabled, an active operator Bearer token.

    Returns a signed JWT valid for 1 hour.  Algorithm is determined by
    GRANTLAYER_JWT_ALGORITHM (default RS256).  Requires the matching key
    material to be set in the environment.
    """
    rate_limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if rate_limiter is not None:
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = rate_limiter.check(client_ip, "auth")
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "errorCode": "rate_limit_exceeded",
                    "reason": f"Too many requests. Retry after {retry_after} seconds.",
                },
                headers={"Retry-After": str(retry_after)},
            )

    if not is_jwt_enabled():
        raise HTTPException(
            status_code=501,
            detail={
                "error": "jwt_not_configured",
                "errorCode": "jwt_not_configured",
                "reason": (
                    "JWT signing key is not configured. "
                    "Set GRANTLAYER_JWT_PRIVATE_KEY (RS256) or GRANTLAYER_JWT_SECRET (HS256)."
                ),
            },
        )

    # Verify supplied secret against the existing auth system.
    # Wrap the secret as a Bearer header so check_auth can validate it.
    auth_header = f"Bearer {body.secret}"
    ok, _status, payload = check_auth(auth_header, required_roles=["owner", "grant_admin", "auditor"])

    if not ok:
        # Also try admin-token path directly (covers legacy/JWT-only setups).
        ok, _status, payload = check_admin_token(auth_header)

    if not ok:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_credentials",
                "errorCode": "invalid_credentials",
                "reason": "operator_id or secret is incorrect.",
            },
        )

    # When check_admin_token succeeds (no operator found), payload has no tenant_id.
    # Admin-token auth is bound to "demo" for backward compat; operator auth uses op.tenant_id.
    tenant_id = payload.get("tenant_id") if payload.get("tenant_id") else "demo"
    role = "owner"
    if config.ENABLE_OPERATOR_MODEL:
        op = payload.get("operator", {})
        role = op.get("role", "owner")
        tenant_id = op.get("tenantId") or tenant_id

    try:
        token = sign_token(
            {"sub": body.operator_id, "tenant_id": tenant_id, "role": role},
            ttl_hours=_TTL_HOURS,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "jwt_signing_key_missing",
                "errorCode": "jwt_signing_key_missing",
                "reason": str(exc),
            },
        ) from exc

    return TokenResponse(access_token=token)
