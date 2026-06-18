"""Pydantic models for GrantLayer API response shapes."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Grant(BaseModel):
    id: Optional[str] = None
    subjectId: Optional[str] = None
    role: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    validFrom: Optional[str] = None
    validUntil: Optional[str] = None
    createdBy: Optional[str] = None
    reason: Optional[str] = None
    revoked: Optional[bool] = None
    createdAt: Optional[str] = None
    signatureValid: Optional[bool] = None
    signaturePresent: Optional[bool] = None
    useCount: Optional[int] = None
    tenantId: Optional[str] = None
    workspaceId: Optional[str] = None

    model_config = {"extra": "allow"}


class GrantRequest(BaseModel):
    id: Optional[str] = None
    subjectId: Optional[str] = None
    role: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    validFrom: Optional[str] = None
    validUntil: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    createdAt: Optional[str] = None
    requesterId: Optional[str] = None
    tenantId: Optional[str] = None
    workspaceId: Optional[str] = None

    model_config = {"extra": "allow"}


class GrantExecution(BaseModel):
    id: Optional[str] = None
    grantId: Optional[str] = None
    agentId: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    outcome: Optional[str] = None
    executedAt: Optional[str] = None

    model_config = {"extra": "allow"}


class AuditEvent(BaseModel):
    id: Optional[str] = None
    subjectId: Optional[str] = None
    role: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    approved: Optional[bool] = None
    reason: Optional[str] = None
    matchedGrantId: Optional[str] = None
    timestamp: Optional[str] = None
    seq: Optional[int] = None

    model_config = {"extra": "allow"}


class EvidenceVerification(BaseModel):
    executionId: Optional[str] = None
    valid: Optional[bool] = None
    checks: Optional[List[Any]] = None

    model_config = {"extra": "allow"}


class WebhookSubscription(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None
    tenantId: Optional[str] = None
    workspaceId: Optional[str] = None
    createdAt: Optional[str] = None

    model_config = {"extra": "allow"}


class Operator(BaseModel):
    operatorId: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    tenantId: Optional[str] = None
    createdAt: Optional[str] = None
    expiresAt: Optional[str] = None

    model_config = {"extra": "allow"}


class AuthToken(BaseModel):
    access_token: str
    token_type: Optional[str] = "bearer"
    expires_in: Optional[int] = None

    model_config = {"extra": "allow"}


class PolicyRequirement(BaseModel):
    id: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    policy: Optional[Any] = None

    model_config = {"extra": "allow"}


class CursorPage(BaseModel):
    items: Optional[List[Any]] = Field(default_factory=list)
    nextCursor: Optional[str] = None
    total: Optional[int] = None

    model_config = {"extra": "allow"}
