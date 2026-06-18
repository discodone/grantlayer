"""Pydantic request/response schemas for FastAPI layer."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
)

# ── Health / Readiness ─────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    service: str
    check_type: str = Field(alias="checkType")

    model_config = {"populate_by_name": True}


class ReadinessResponse(BaseModel):
    status: str
    service: str
    check_type: str = Field(alias="checkType")
    runtime_mode: Optional[str] = Field(default=None, alias="runtimeMode")
    is_production_like: Optional[bool] = Field(default=None, alias="isProductionLike")
    error_code: Optional[str] = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}


# ── Grants ─────────────────────────────────────────────────────────────────


class GrantCreateRequest(BaseModel):
    subject_id: str = Field(alias="subjectId", max_length=MAX_SHORT_ID_LENGTH)
    role: str = Field(max_length=MAX_ROLE_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)
    valid_from: str = Field(alias="validFrom")
    valid_until: str = Field(alias="validUntil")
    created_by: str = Field(alias="createdBy", max_length=MAX_SHORT_ID_LENGTH)
    reason: str = Field(max_length=MAX_REASON_LENGTH)
    max_uses: Optional[int] = Field(default=None, alias="maxUses", ge=1)

    model_config = {"populate_by_name": True}


class GrantResponse(BaseModel):
    id: str
    subject_id: str = Field(alias="subjectId")
    role: str
    action: str
    resource: str
    valid_from: str = Field(alias="validFrom")
    valid_until: str = Field(alias="validUntil")
    created_by: str = Field(alias="createdBy")
    reason: str
    revoked: bool
    revoked_by: Optional[str] = Field(default=None, alias="revokedBy")
    revoked_reason: Optional[str] = Field(default=None, alias="revokedReason")
    revoked_at: Optional[str] = Field(default=None, alias="revokedAt")
    created_at: str = Field(alias="createdAt")
    signature: Optional[str] = None
    signing_key_id: Optional[str] = Field(default=None, alias="signingKeyId")
    payload_hash: Optional[str] = Field(default=None, alias="payloadHash")
    signature_present: bool = Field(alias="signaturePresent")
    signature_valid: bool = Field(alias="signatureValid")
    max_uses: Optional[int] = Field(default=None, alias="maxUses")
    use_count: int = Field(alias="useCount")

    model_config = {"populate_by_name": True, "from_attributes": True}

    @classmethod
    def from_grant(cls, grant, signature_valid: bool) -> "GrantResponse":
        d = grant.to_dict()
        return cls(
            id=d["id"],
            subjectId=d["subject_id"],
            role=d["role"],
            action=d["action"],
            resource=d["resource"],
            validFrom=d["valid_from"],
            validUntil=d["valid_until"],
            createdBy=d["created_by"],
            reason=d["reason"],
            revoked=d["revoked"],
            revokedBy=d.get("revoked_by"),
            revokedReason=d.get("revoked_reason"),
            revokedAt=d.get("revoked_at"),
            createdAt=d["created_at"],
            signature=d.get("signature"),
            signingKeyId=d.get("signing_key_id"),
            payloadHash=d.get("payload_hash"),
            signaturePresent=d.get("signature") is not None,
            signatureValid=signature_valid,
            maxUses=d.get("max_uses"),
            useCount=d.get("use_count", 0),
        )


class GrantListResponse(BaseModel):
    items: list[GrantResponse]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")

    model_config = {"populate_by_name": True}


class GrantRequestResponse(BaseModel):
    id: str
    subject_id: str = Field(alias="subjectId")
    role: str
    action: str
    resource: str
    valid_from: str = Field(alias="validFrom")
    valid_until: str = Field(alias="validUntil")
    requested_by: str = Field(alias="requestedBy")
    reason: str
    status: str
    approved_by: Optional[str] = Field(default=None, alias="approvedBy")
    approved_at: Optional[str] = Field(default=None, alias="approvedAt")
    denied_by: Optional[str] = Field(default=None, alias="deniedBy")
    denied_at: Optional[str] = Field(default=None, alias="deniedAt")
    denial_reason: Optional[str] = Field(default=None, alias="denialReason")
    revoked_by: Optional[str] = Field(default=None, alias="revokedBy")
    revoked_at: Optional[str] = Field(default=None, alias="revokedAt")
    revoked_reason: Optional[str] = Field(default=None, alias="revokedReason")
    grant_id: Optional[str] = Field(default=None, alias="grantId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True, "from_attributes": True}

    @classmethod
    def from_grant_request(cls, req) -> "GrantRequestResponse":
        d = req.to_dict()
        return cls(
            id=d["id"],
            subjectId=d["subject_id"],
            role=d["role"],
            action=d["action"],
            resource=d["resource"],
            validFrom=d["valid_from"],
            validUntil=d["valid_until"],
            requestedBy=d["requested_by"],
            reason=d["reason"],
            status=d["status"],
            approvedBy=d.get("approved_by"),
            approvedAt=d.get("approved_at"),
            deniedBy=d.get("denied_by"),
            deniedAt=d.get("denied_at"),
            denialReason=d.get("denial_reason"),
            revokedBy=d.get("revoked_by"),
            revokedAt=d.get("revoked_at"),
            revokedReason=d.get("revoked_reason"),
            grantId=d.get("grant_id"),
            createdAt=d["created_at"],
            updatedAt=d["updated_at"],
        )


class GrantRequestListResponse(BaseModel):
    items: list[GrantRequestResponse]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")

    model_config = {"populate_by_name": True}


class AuditEventResponse(BaseModel):
    id: str
    timestamp: str
    subject_id: str
    role: str
    action: str
    resource: str
    approved: bool
    reason: str
    matched_grant_id: Optional[str] = None
    challenge_id: Optional[str] = None
    challenge_present: bool
    challenge_result: str
    grant_signature_result: str
    row_hash: Optional[str] = None
    prev_hash: Optional[str] = None
    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scope: Optional[str] = None


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = None


class GrantExecutionResponse(BaseModel):
    id: str
    grant_id: Optional[str] = Field(default=None, alias="grantId")
    grant_request_id: Optional[str] = Field(default=None, alias="grantRequestId")
    operator_id: Optional[str] = Field(default=None, alias="operatorId")
    action: str
    resource: str
    challenge_id: Optional[str] = Field(default=None, alias="challengeId")
    challenge_result: Optional[str] = Field(default=None, alias="challengeResult")
    policy_result: str = Field(alias="policyResult")
    result: str
    error_code: Optional[str] = Field(default=None, alias="errorCode")
    executed_at: str = Field(alias="executedAt")
    audit_event_id: Optional[str] = Field(default=None, alias="auditEventId")
    metadata_json: Optional[str] = Field(default=None, alias="metadataJson")

    model_config = {"populate_by_name": True}


class GrantExecutionListResponse(BaseModel):
    items: list[GrantExecutionResponse]
    total: int
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class ChallengeResponse(BaseModel):
    id: str
    subject_id: str = Field(alias="subjectId")
    action: str
    resource: str
    created_at: str = Field(alias="createdAt")
    expires_at: str = Field(alias="expiresAt")
    used_at: Optional[str] = Field(default=None, alias="usedAt")
    status: str

    model_config = {"populate_by_name": True}


class ChallengeCreateResponse(BaseModel):
    challenge_id: str = Field(alias="challengeId")
    subject_id: str = Field(alias="subjectId")
    action: str
    resource: str
    expires_at: str = Field(alias="expiresAt")

    model_config = {"populate_by_name": True}


class ChallengeListResponse(BaseModel):
    items: list[ChallengeResponse]
    total: int
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class OkResponse(BaseModel):
    ok: bool


class DynamicResponse(BaseModel):
    model_config = {"extra": "allow"}


class DictResponse(BaseModel):
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    error: str
    error_code: str = Field(alias="errorCode")
    reason: str

    model_config = {"populate_by_name": True}


# ── Shared validators ──────────────────────────────────────────────────────

import datetime as _dt

from fastapi import HTTPException as _HTTPException


def _validate_iso_timestamp(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise _HTTPException(
            status_code=400,
            detail={"error": f"Invalid {field_name}", "errorCode": "invalid_timestamp", "reason": f"{field_name} must be a valid ISO-8601 timestamp."},
        )
    try:
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        _dt.datetime.fromisoformat(v)
    except ValueError:
        raise _HTTPException(
            status_code=400,
            detail={"error": f"Invalid {field_name}", "errorCode": "invalid_timestamp", "reason": f"{field_name} must be a valid ISO-8601 timestamp."},
        )


def _validate_grant_dates(valid_from: str, valid_until: str) -> None:
    _validate_iso_timestamp(valid_from, "validFrom")
    _validate_iso_timestamp(valid_until, "validUntil")
    vf = _dt.datetime.fromisoformat(valid_from.replace("Z", "+00:00") if valid_from.endswith("Z") else valid_from)
    vu = _dt.datetime.fromisoformat(valid_until.replace("Z", "+00:00") if valid_until.endswith("Z") else valid_until)
    if vf >= vu:
        raise _HTTPException(
            status_code=400,
            detail={"error": "Invalid date range", "errorCode": "invalid_date_range", "reason": "validFrom must be strictly before validUntil."},
        )
