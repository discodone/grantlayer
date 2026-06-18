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


def resolve_auth_and_workspace(
    authorization: Optional[str],
    required_roles: list[str],
    workspace_id: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authenticate and resolve workspace context.

    Auth priority (first match wins):
    1. OIDC — when GRANTLAYER_ENABLE_OIDC=true and fully configured.
    2. Internal JWT — when GRANTLAYER_JWT_SECRET or GRANTLAYER_JWT_PUBLIC_KEY is set.
    3. Legacy static-token / operator-model.

    Returns (auth_ctx, ws_ctx).  Raises HTTPException on failure.
    """
    payload: dict[str, Any]

    # 1. OIDC validation (externally-issued JWTs from Keycloak/Okta/Azure AD).
    oidc_ok, oidc_status, oidc_result = validate_oidc_header(authorization)
    if oidc_ok is not None:
        if not oidc_ok:
            raise HTTPException(status_code=oidc_status or 401, detail=oidc_result)
        payload = cast(dict[str, Any], oidc_result)
    else:
        # 2. Internal JWT validation.
        jwt_ok, jwt_status, jwt_result = validate_jwt_header(authorization)
        if jwt_ok is not None:
            if not jwt_ok:
                raise HTTPException(status_code=jwt_status or 401, detail=jwt_result)
            payload = cast(dict[str, Any], jwt_result)
        else:
            # 3. Legacy static-token / operator-model auth.
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
    """Check admin token. Returns payload dict or raises HTTPException."""
    ok, status, payload = check_admin_token(authorization)
    if not ok:
        raise HTTPException(status_code=status, detail=payload)
    return {"tenant_id": "demo"}


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
