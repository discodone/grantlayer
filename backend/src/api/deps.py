"""/Shared FastAPI dependency helpers."""

from __future__ import annotations

from typing import Any, Optional, cast

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..auth.auth import (
    check_admin_token,
    check_auth,
    check_workspace_resource_access,
    resolve_workspace_context,
)
from ..auth.oidc import validate_oidc_header
from ..auth.operator_service import AsyncOperatorService, OperatorService
from ..core.db import get_async_db, get_db
from ..core.repositories import (
    IGrantExecutionRepository,
    IGrantRepository,
    IGrantRequestRepository,
    IOperatorRepository,
)
from ..core.repositories_sqlalchemy import (
    SqlAlchemyAsyncGrantExecutionRepository,
    SqlAlchemyAsyncGrantRepository,
    SqlAlchemyAsyncGrantRequestRepository,
    SqlAlchemyAsyncOperatorRepository,
    SqlAlchemyGrantExecutionRepository,
    SqlAlchemyGrantRepository,
    SqlAlchemyGrantRequestRepository,
    SqlAlchemyOperatorRepository,
)
from ..grants.grant_request_service import AsyncGrantRequestService, GrantRequestService
from ..grants.grant_service import AsyncGrantService, GrantService
from .auth_jwt import validate_jwt_header


async def async_resolve_auth_and_workspace(
    authorization: Optional[str],
    required_roles: list[str],
    db: "AsyncSession",
    workspace_id: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Async version of resolve_auth_and_workspace that uses resolve_api_key_auth().

    Use this in async route handlers so API key DB lookups avoid the sync engine.
    Falls through to the same OIDC/JWT/legacy chain for non-API-key requests.
    """
    # 1. API key auth — async path using resolve_api_key_auth().
    if authorization:
        scheme, _, raw_token = authorization.partition(" ")
        if scheme.lower() == "bearer" and raw_token.strip().startswith("gl_live_"):
            from .routers.api_keys import resolve_api_key_auth
            api_payload = await resolve_api_key_auth(raw_token.strip(), db)
            if api_payload is None:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "invalid_api_key",
                        "errorCode": "invalid_api_key",
                        "reason": "API key is invalid, revoked, or expired.",
                    },
                )
            effective_workspace = workspace_id or api_payload["workspace_id"]
            ws_ctx: dict[str, Any] = {
                "workspace_id": effective_workspace,
                "tenant_id": api_payload.get("tenant_id", effective_workspace),
                "workspace_member_role": None,
                "cross_workspace_access": False,
                "resolution_mode": "api_key",
            }
            return api_payload, ws_ctx

    # 2-4: delegate to sync chain (OIDC/JWT/legacy — no DB needed there).
    return resolve_auth_and_workspace(authorization, required_roles, workspace_id)


def resolve_auth_and_workspace(
    authorization: Optional[str],
    required_roles: list[str],
    workspace_id: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authenticate and resolve workspace context.

    Auth priority (first match wins):
    1. API key  — when Authorization header contains a gl_live_* key.
    2. OIDC     — when GRANTLAYER_ENABLE_OIDC=true and fully configured.
    3. Internal JWT — when GRANTLAYER_JWT_SECRET or GRANTLAYER_JWT_PUBLIC_KEY is set.
    4. Legacy static-token / operator-model.

    Returns (auth_ctx, ws_ctx).  Raises HTTPException on failure.
    """
    payload: dict[str, Any]

    # 1. API key auth (Bearer gl_live_* tokens bypass JWT/OIDC pipeline).
    if authorization:
        scheme, _, raw_token = authorization.partition(" ")
        if scheme.lower() == "bearer" and raw_token.strip().startswith("gl_live_"):
            from .routers.api_keys import resolve_api_key_sync
            api_payload = resolve_api_key_sync(raw_token.strip())
            if api_payload is None:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "invalid_api_key",
                        "errorCode": "invalid_api_key",
                        "reason": "API key is invalid, revoked, or expired.",
                    },
                )
            # API keys carry an explicit workspace_id — construct ws_ctx directly
            # without going through membership resolution.
            effective_workspace = workspace_id or api_payload["workspace_id"]
            ws_ctx: dict[str, Any] = {
                "workspace_id": effective_workspace,
                "tenant_id": api_payload["tenant_id"],
                "workspace_member_role": None,
                "cross_workspace_access": False,
                "resolution_mode": "api_key",
            }
            return api_payload, ws_ctx

    # 2. OIDC validation (externally-issued JWTs from Keycloak/Okta/Azure AD).
    oidc_ok, oidc_status, oidc_result = validate_oidc_header(authorization)
    if oidc_ok is not None:
        if not oidc_ok:
            raise HTTPException(status_code=oidc_status or 401, detail=oidc_result)
        payload = cast(dict[str, Any], oidc_result)
    else:
        # 3. Internal JWT validation.
        jwt_ok, jwt_status, jwt_result = validate_jwt_header(authorization)
        if jwt_ok is not None:
            if not jwt_ok:
                raise HTTPException(status_code=jwt_status or 401, detail=jwt_result)
            payload = cast(dict[str, Any], jwt_result)
        else:
            # 4. Legacy static-token / operator-model auth.
            ok, http_status, payload = check_auth(authorization, required_roles=required_roles)
            if not ok:
                raise HTTPException(status_code=http_status, detail=payload)

    ws_id, ws_status, ws_ctx = resolve_workspace_context(payload, workspace_id)

    if ws_status != 200:
        raise HTTPException(status_code=ws_status, detail=ws_ctx)

    if ws_id is None or ws_ctx.get("workspace_id") is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "workspace_id is required",
                "errorCode": "workspace_id_required",
                "reason": "A valid workspace context is required.",
            },
        )

    return payload, ws_ctx


def require_admin(authorization: Optional[str]) -> dict:
    """Check admin token or JWT admin role. Returns payload dict or raises HTTPException."""
    # Prefer JWT when configured — extracts real caller identity and tenant.
    jwt_ok, jwt_status, jwt_result = validate_jwt_header(authorization)
    if jwt_ok is not None:
        if not jwt_ok:
            raise HTTPException(status_code=jwt_status or 401, detail=jwt_result)
        jwt_payload = cast(dict[str, Any], jwt_result)
        if jwt_payload.get("role") not in ("owner", "grant_admin", "admin"):
            raise HTTPException(
                status_code=403,
                detail={"error": "Forbidden", "errorCode": "forbidden", "reason": "Admin role required."},
            )
        return jwt_payload

    # Fall back to admin token (returns {} on success — no tenant context).
    ok, status, payload = check_admin_token(authorization)
    if not ok:
        raise HTTPException(status_code=status, detail=payload)
    return payload


def get_grant_repo(db: Session = Depends(get_db)) -> IGrantRepository:
    return SqlAlchemyGrantRepository(db)


def get_grant_request_repo(db: Session = Depends(get_db)) -> IGrantRequestRepository:
    return SqlAlchemyGrantRequestRepository(db)


def get_grant_execution_repo(db: Session = Depends(get_db)) -> IGrantExecutionRepository:
    return SqlAlchemyGrantExecutionRepository(db)


def get_operator_repo(db: Session = Depends(get_db)) -> IOperatorRepository:
    return SqlAlchemyOperatorRepository(db)


def get_grant_service(db: Session = Depends(get_db)) -> GrantService:
    return GrantService(repo=SqlAlchemyGrantRepository(db), session=db)


def get_grant_request_service(db: Session = Depends(get_db)) -> GrantRequestService:
    return GrantRequestService(
        repo=SqlAlchemyGrantRequestRepository(db),
        grant_repo=SqlAlchemyGrantRepository(db),
        session=db,
    )


def get_operator_service(db: Session = Depends(get_db)) -> OperatorService:
    return OperatorService(repo=SqlAlchemyOperatorRepository(db))


def enforce_workspace_mutation(ws_ctx: dict) -> None:
    """Raise 403 if the caller's workspace context does not allow mutation."""
    access_ok, access_status, access_err = check_workspace_resource_access(
        resource_workspace_id=None,
        caller_workspace_id=ws_ctx["workspace_id"],
        caller_tenant_id=ws_ctx["tenant_id"],
        resource_tenant_id=ws_ctx["tenant_id"],
        cross_workspace_access=ws_ctx.get("cross_workspace_access", False),
        require_mutation=True,
        workspace_member_role=ws_ctx.get("workspace_member_role"),
    )
    if not access_ok:
        raise HTTPException(status_code=access_status, detail=access_err)


# ── Async dependency factories ────────────────────────────────────────────────


def get_async_grant_repo(db: AsyncSession = Depends(get_async_db)) -> SqlAlchemyAsyncGrantRepository:
    return SqlAlchemyAsyncGrantRepository(db)


def get_async_grant_request_repo(
    db: AsyncSession = Depends(get_async_db),
) -> SqlAlchemyAsyncGrantRequestRepository:
    return SqlAlchemyAsyncGrantRequestRepository(db)


def get_async_grant_execution_repo(
    db: AsyncSession = Depends(get_async_db),
) -> SqlAlchemyAsyncGrantExecutionRepository:
    return SqlAlchemyAsyncGrantExecutionRepository(db)


def get_async_operator_repo(db: AsyncSession = Depends(get_async_db)) -> SqlAlchemyAsyncOperatorRepository:
    return SqlAlchemyAsyncOperatorRepository(db)


def get_async_grant_service(db: AsyncSession = Depends(get_async_db)) -> AsyncGrantService:
    return AsyncGrantService(repo=SqlAlchemyAsyncGrantRepository(db), session=db)


def get_async_grant_request_service(db: AsyncSession = Depends(get_async_db)) -> AsyncGrantRequestService:
    return AsyncGrantRequestService(
        repo=SqlAlchemyAsyncGrantRequestRepository(db),
        grant_repo=SqlAlchemyAsyncGrantRepository(db),
        session=db,
    )


def get_async_operator_service(db: AsyncSession = Depends(get_async_db)) -> AsyncOperatorService:
    return AsyncOperatorService(repo=SqlAlchemyAsyncOperatorRepository(db))
