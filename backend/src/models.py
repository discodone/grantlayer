"""GrantLayer MVP — Data models."""

from dataclasses import dataclass, field, asdict
from typing import Optional
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
