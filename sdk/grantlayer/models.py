"""Typed dicts for GrantLayer API response shapes (informational only)."""

from __future__ import annotations

from typing import List, Optional
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[no-redef]


class Grant(TypedDict, total=False):
    id: str
    subjectId: str
    role: str
    action: str
    resource: str
    validFrom: str
    validUntil: str
    createdBy: str
    reason: str
    revoked: bool
    createdAt: str
    signatureValid: bool
    signaturePresent: bool
    useCount: int


class GrantRequest(TypedDict, total=False):
    id: str
    subjectId: str
    role: str
    action: str
    resource: str
    validFrom: str
    validUntil: str
    reason: str
    status: str
    createdAt: str


class AuditEvent(TypedDict, total=False):
    id: str
    subjectId: str
    role: str
    action: str
    resource: str
    approved: bool
    reason: str
    matchedGrantId: str
    timestamp: str


class EvidenceVerification(TypedDict, total=False):
    executionId: str
    valid: bool
    checks: List[dict]
