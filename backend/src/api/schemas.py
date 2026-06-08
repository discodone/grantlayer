"""GL-228: Pydantic request/response schemas for FastAPI layer."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from ..validation import (
    MAX_SHORT_ID_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
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


class ErrorResponse(BaseModel):
    error: str
    error_code: str = Field(alias="errorCode")
    reason: str

    model_config = {"populate_by_name": True}
