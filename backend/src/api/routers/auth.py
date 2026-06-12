"""/auth/token endpoint — exchange credentials for a JWT."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth_jwt import encode_token, is_jwt_enabled, _get_jwt_secret
from ...auth.auth import check_auth, check_admin_token
from ...core import config

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
def issue_token(request: Request, body: TokenRequest) -> Any:
    """Exchange operator credentials for a JWT Bearer token.

    The `secret` field accepts either the GRANTLAYER_ADMIN_TOKEN or, when
    the operator model is enabled, an active operator Bearer token.

    Returns a signed HS256 JWT valid for 1 hour.  Requires
    GRANTLAYER_JWT_SECRET to be set in the environment.
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
                    "GRANTLAYER_JWT_SECRET is not set. "
                    "Add it to .env to enable JWT token issuance."
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

    # Determine tenant_id from auth payload or fall back to operator_id.
    tenant_id = payload.get("tenant_id") or "demo"
    role = "owner"
    if config.ENABLE_OPERATOR_MODEL:
        op = payload.get("operator", {})
        role = op.get("role", "owner")
        tenant_id = op.get("tenantId") or tenant_id

    secret = _get_jwt_secret()
    token = encode_token(
        {"sub": body.operator_id, "tenant_id": tenant_id, "role": role},
        secret,
        ttl_hours=_TTL_HOURS,
    )

    return TokenResponse(access_token=token)
