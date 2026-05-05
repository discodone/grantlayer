"""GrantLayer MVP — Data models."""

from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
import uuid
import datetime


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Grant:
    subject_id: str
    role: str
    action: str
    resource: str
    valid_from: str
    valid_until: str
    created_by: str
    reason: str
    id: str = field(default_factory=_new_id)
    revoked: bool = False
    revoked_by: Optional[str] = None
    revoked_reason: Optional[str] = None
    revoked_at: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    signature: Optional[str] = None
    signing_key_id: Optional[str] = None
    payload_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


GrantSignatureResult = Literal["valid", "missing", "invalid", "hash_mismatch", "not_checked"]

ChallengeStatus = Literal["active", "used", "expired"]
ChallengeResult = Literal[
    "valid", "missing", "not_found", "expired",
    "already_used", "mismatch", "legacy_mode", "required_missing",
]

# GL-022 Grant Request statuses
GrantRequestStatus = Literal["requested", "approved", "denied", "revoked", "expired"]

# GL-023 Grant Execution result
GrantExecutionResult = Literal["succeeded", "denied", "failed"]


@dataclass
class GrantExecution:
    """GL-023 — One row per protected action attempt."""
    action: str
    resource: str
    id: str = field(default_factory=_new_id)
    grant_id: Optional[str] = None
    grant_request_id: Optional[str] = None
    operator_id: Optional[str] = None
    challenge_id: Optional[str] = None
    challenge_result: Optional[str] = None
    policy_result: str = ""
    result: GrantExecutionResult = "denied"
    error_code: Optional[str] = None
    executed_at: str = field(default_factory=_now_iso)
    audit_event_id: Optional[str] = None
    metadata_json: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "grantId": self.grant_id,
            "grantRequestId": self.grant_request_id,
            "operatorId": self.operator_id,
            "action": self.action,
            "resource": self.resource,
            "challengeId": self.challenge_id,
            "challengeResult": self.challenge_result,
            "policyResult": self.policy_result,
            "result": self.result,
            "errorCode": self.error_code,
            "executedAt": self.executed_at,
            "auditEventId": self.audit_event_id,
            "metadataJson": self.metadata_json,
        }


@dataclass
class Challenge:
    subject_id: str
    action: str
    resource: str
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now_iso)
    expires_at: str = ""          # set by challenges.create_challenge
    used_at: Optional[str] = None
    status: ChallengeStatus = "active"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEvent:
    subject_id: str
    role: str
    action: str
    resource: str
    approved: bool
    reason: str
    matched_grant_id: Optional[str] = None
    challenge_id: Optional[str] = None
    challenge_present: bool = False
    challenge_result: ChallengeResult = "legacy_mode"
    grant_signature_result: str = "not_checked"
    id: str = field(default_factory=_new_id)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AccessRequest:
    subject_id: str
    role: str
    action: str
    resource: str


@dataclass
class PolicyResult:
    approved: bool
    reason: str
    matched_grant_id: Optional[str] = None


# ──────────────────────────────────────────────
# GL-021 Operator model
# ──────────────────────────────────────────────

@dataclass
class Operator:
    operator_id: str
    name: str
    role: str
    active: bool = True
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "operatorId": self.operator_id,
            "name": self.name,
            "role": self.role,
            "active": self.active,
        }


# ──────────────────────────────────────────────
# GL-022 Grant Request model
# ──────────────────────────────────────────────

@dataclass
class GrantRequest:
    """Grant Request entity for approval workflow."""
    subject_id: str
    role: str
    action: str
    resource: str
    valid_from: str
    valid_until: str
    requested_by: str  # Operator ID who requested
    reason: str
    id: str = field(default_factory=_new_id)
    status: GrantRequestStatus = "requested"
    
    # Approval fields
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    
    # Denial fields
    denied_by: Optional[str] = None
    denied_at: Optional[str] = None
    denial_reason: Optional[str] = None
    
    # Revocation fields
    revoked_by: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_reason: Optional[str] = None
    
    # Link to created grant (if approved)
    grant_id: Optional[str] = None
    
    # Timestamps
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)
