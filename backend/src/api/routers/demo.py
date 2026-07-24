"""Demo endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...core import config
from ...core.validation import (
    MAX_NAME_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_optional_string_length,
    validate_string_length,
)
from ...demo.demo_action import handle_demo_action
from ...grants.grants import tamper_grant
from ..deps import require_mutation_authz, resolve_auth_and_workspace
from ..schemas import DynamicResponse, ExerciseResponse

router = APIRouter(tags=["demo"])

# Registered only when GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true (see app.py).
# Kept separate so demo-action (always available) is not gated.
tamper_router = APIRouter(tags=["demo"])


class DemoActionRequest(BaseModel):
    # Optional so an API-key caller may omit it and exercise as the key's
    # bound subject; non-API-key callers must still supply it (enforced in
    # the endpoint, 400 invalid_field).
    subject_id: Optional[str] = Field(
        default=None, alias="subjectId", max_length=MAX_SHORT_ID_LENGTH
    )
    role: str = Field(max_length=MAX_ROLE_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)
    challenge_id: Optional[str] = Field(default=None, alias="challengeId", max_length=MAX_SHORT_ID_LENGTH)

    model_config = {"populate_by_name": True}


@tamper_router.post("/demo/tamper-grant/{grant_id}", response_model=DynamicResponse)
async def tamper_grant_endpoint(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "demo_operator"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    result = tamper_grant(grant_id, tenant_id=tenant_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant not found", "errorCode": "grant_not_found", "reason": "The requested grant does not exist."},
        )
    return result


@router.post("/exercise", response_model=ExerciseResponse, response_model_by_alias=True)
async def exercise_endpoint(
    body: DemoActionRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    # Shared mutation gate (API-key write scope + OPA), same as every sibling
    # mutating route — a decision write is a mutation. Accepted auth methods
    # are unchanged; this closes the old allowlist exception.
    await require_mutation_authz(auth_ctx, ws_ctx)
    caller_operator_id: Optional[str] = None
    if config.ENABLE_OPERATOR_MODEL:
        caller_operator_id = auth_ctx.get("operator", {}).get("operatorId")
    tenant_id = ws_ctx["tenant_id"]

    # Subject identity binding (mirrors the workspace-binding contract): an
    # API key exercises as ITS bound subject, never as a caller-asserted one.
    #   * unbound key            -> 403 api_key_subject_unbound (fail-closed;
    #     mirrors api_key_workspace_unbound — no fallback, no grandfathering);
    #   * body subjectId present and mismatching -> 400 subject_id_mismatch
    #     (mirrors the body_workspace_id_not_allowed 400 precedent);
    #   * body subjectId absent  -> derived from the binding.
    # Non-API-key callers (JWT/OIDC/legacy owner|grant_admin operators) keep
    # today's semantics: they record decisions for subjects they name and are
    # attributed via operator_id; for them subjectId stays required.
    effective_subject: Optional[str] = body.subject_id
    if ws_ctx.get("resolution_mode") == "api_key":
        bound_subject = auth_ctx.get("subject_id")
        if not bound_subject:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "api_key_subject_unbound",
                    "errorCode": "api_key_subject_unbound",
                    "reason": (
                        "This API key has no subject binding and cannot "
                        "exercise grants. Re-issue the key with a subjectId "
                        "binding (or bind this key) to use /v1/exercise."
                    ),
                },
            )
        if body.subject_id is not None and body.subject_id != bound_subject:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "subject_id mismatch",
                    "errorCode": "subject_id_mismatch",
                    "reason": (
                        "The subject identity is derived from the API key's "
                        "binding; a different body subjectId is refused. "
                        "Omit subjectId or send the bound value."
                    ),
                },
            )
        effective_subject = bound_subject
    elif effective_subject is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid field: subjectId",
                "errorCode": "invalid_field",
                "reason": "subjectId is required for non-API-key callers.",
            },
        )

    for field_name, value, max_len in (
        ("subjectId", effective_subject, MAX_SHORT_ID_LENGTH),
        ("role", body.role, MAX_ROLE_LENGTH),
        ("action", body.action, MAX_NAME_LENGTH),
        ("resource", body.resource, MAX_NAME_LENGTH),
    ):
        try:
            validate_string_length(value, field_name, max_len)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid field: {field_name}", "errorCode": "invalid_field", "reason": str(exc)},
            ) from exc

    try:
        validate_optional_string_length(body.challenge_id, "challengeId", MAX_SHORT_ID_LENGTH)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid field", "errorCode": "invalid_field", "reason": str(exc)},
        ) from exc

    result = handle_demo_action(
        subject_id=effective_subject,
        role=body.role,
        action=body.action,
        resource=body.resource,
        challenge_id=body.challenge_id,
        operator_id=caller_operator_id,
        tenant_id=tenant_id,
        workspace_id=ws_ctx["workspace_id"],
    )
    # Validate against the typed contract; exclude_unset preserves the exact
    # per-path field set (e.g. no `message` on denials).
    resp = ExerciseResponse.model_validate(result)
    status_code = 200 if resp.approved else 403
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=resp.model_dump(by_alias=True, exclude_unset=True),
        status_code=status_code,
    )
