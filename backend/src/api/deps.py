"""/Shared FastAPI dependency helpers."""

from __future__ import annotations

from typing import Annotated, Any, Optional, cast

from fastapi import Depends, Header, HTTPException
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
from ..policy.opa_client import evaluate_policy
from .auth_jwt import validate_jwt_header


def _api_key_workspace(
    api_payload: dict[str, Any], client_workspace_id: Optional[str]
) -> str:
    """Return the workspace an API-key request resolves into: the key's binding.

    Fail-closed contract (shared by the sync and async resolvers):
      * a key with a missing/empty workspace binding is refused — never a
        fallback to a default;
      * a client-supplied workspace header can never override the binding —
        present and mismatching is a 403, present and matching is allowed.
    """
    bound = api_payload.get("workspace_id")
    if not bound:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "api_key_workspace_unbound",
                "errorCode": "api_key_workspace_unbound",
                "reason": "This API key has no workspace binding and cannot be used.",
            },
        )
    client = client_workspace_id.strip() if client_workspace_id else None
    if client and client != bound:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "workspace_mismatch",
                "errorCode": "workspace_mismatch",
                "reason": "X-Workspace-Id does not match this API key's bound workspace.",
            },
        )
    return bound


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
            effective_workspace = _api_key_workspace(api_payload, workspace_id)
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
            effective_workspace = _api_key_workspace(api_payload, workspace_id)
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


def assert_admin_tenant_scope(
    admin_payload: dict, target_tenant_id: Optional[str]
) -> None:
    """Reject a tenant-scoped admin acting on a resource in a different tenant.

    Control-plane admin authority is NOT global for tenant-scoped admins. A
    deployment-level admin (static admin token) carries no tenant context in its
    payload and retains full cross-tenant authority. A tenant-scoped admin (JWT
    with a ``tenant_id`` claim) may only act within its own tenant; acting on
    another tenant's resource is a privilege escalation and is rejected with 403.

    ``target_tenant_id`` is the tenant the action targets, derived from the
    verified request (request body for create, or the persisted resource row for
    reads/updates) — never trusted from an unauthenticated source.
    """
    caller_tenant = admin_payload.get("tenant_id")
    if (
        caller_tenant is not None
        and target_tenant_id is not None
        and caller_tenant != target_tenant_id
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "cross_tenant_forbidden",
                "reason": "Admin authority is scoped to your own tenant; you cannot act on another tenant's resources.",
            },
        )


class AdminScope:
    """Resolved admin caller + the SINGLE shared tenant-scope mechanism.

    Injected via ``Depends(require_admin_scope)`` so every admin-plane route enforces
    tenant scope the same way instead of hand-bolting checks per handler (the prior
    root cause: ``require_admin`` was hand-called and sibling routes forgot the check).

    Authority model:
      - deployment-level admin (static admin token, NO ``tenant_id`` claim) →
        ``tenant_id is None`` → full cross-tenant authority.
      - tenant-scoped admin (JWT with a ``tenant_id`` claim) → confined to its tenant.

    Usage:
      - ``scope.tenant_filter``        → caller's tenant_id, or None for a deployment
        admin; pass to list/query methods so reads are scoped at the data layer.
      - ``scope.assert_target(t)``     → 403 cross_tenant_forbidden if a tenant-scoped
        admin targets another tenant (no-op for a deployment admin).
      - ``scope.require_deployment_admin()`` → 403 for a tenant-scoped admin on a route
        whose resource has no tenant dimension (e.g. the infra job queue), where
        ownership cannot be proven.
    """

    __slots__ = ("payload", "tenant_id")

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.tenant_id: Optional[str] = payload.get("tenant_id")

    @property
    def is_deployment_admin(self) -> bool:
        return self.tenant_id is None

    @property
    def tenant_filter(self) -> Optional[str]:
        """Tenant to scope reads to, or None (deployment admin → unrestricted)."""
        return self.tenant_id

    def assert_target(self, target_tenant_id: Optional[str]) -> None:
        assert_admin_tenant_scope(self.payload, target_tenant_id)

    def require_deployment_admin(self) -> None:
        if self.tenant_id is not None:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Forbidden",
                    "errorCode": "deployment_admin_required",
                    "reason": "This resource has no tenant scope; only a deployment-level admin may access it.",
                },
            )


def require_admin_scope(
    authorization: Annotated[Optional[str], Header()] = None,
) -> AdminScope:
    """FastAPI dependency: authenticate an admin and return its tenant-scope guard.

    Replaces the hand-called ``require_admin(authorization)`` so admin auth + the
    shared tenant-scope mechanism are declared structurally in the route signature.
    """
    return AdminScope(require_admin(authorization))


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


def enforce_api_key_write_scope(auth_ctx: dict) -> None:
    """Raise 403 if the caller is a read_only API key (no write permission)."""
    if auth_ctx.get("auth_method") != "api_key":
        return
    scopes: list[str] = auth_ctx.get("scopes") or []
    if "read_write" in scopes or "admin" in scopes:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": "Forbidden",
            "errorCode": "insufficient_scope",
            "reason": "This API key has read_only scope. A read_write or admin key is required for write operations.",
        },
    )


async def require_mutation_authz(auth_ctx: dict, ws_ctx: dict) -> None:
    """Shared gate for all mutation routes: API-key scope check + OPA policy evaluation.

    Call immediately after resolve_auth_and_workspace, before any business logic or
    DB lookups, so that unauthorized callers never observe resource existence.
    """
    enforce_api_key_write_scope(auth_ctx)
    allowed = await evaluate_policy(
        action="resource.mutate",
        subject={"sub": auth_ctx.get("sub"), "role": auth_ctx.get("role")},
        resource={
            "workspace_id": ws_ctx.get("workspace_id"),
            "tenant_id": ws_ctx.get("tenant_id"),
        },
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "policy_denied",
                "reason": "OPA policy denied this operation.",
            },
        )


def enforce_workspace_mutation(ws_ctx: dict, auth_ctx: Optional[dict] = None) -> None:
    """Raise 403 if the caller's workspace context does not allow mutation.

    When auth_ctx is provided, also enforces API key write-scope gate.
    """
    if auth_ctx is not None:
        enforce_api_key_write_scope(auth_ctx)
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
