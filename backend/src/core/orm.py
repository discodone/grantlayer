"""GrantLayer MVP — SQLAlchemy table definitions (Alembic metadata source).

These Table/Column definitions mirror the raw-SQL schema managed by the
custom migration runner in backend/src/migrations/.  They are used solely
by Alembic autogenerate; the application continues to use the raw sqlite3/
psycopg2 layer via backend/src/core/db.py.

Column types are intentionally all Text/Integer to match the TEXT/INTEGER
columns in the original SQLite schema.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData()


# ── Core business tables ────────────────────────────────────────────────────

class Grant(Base):
    __tablename__ = "grants"

    id = Column(Text, primary_key=True)
    subject_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    valid_from = Column(Text, nullable=False)
    valid_until = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    revoked = Column(Integer, nullable=False, default=0)
    revoked_by = Column(Text)
    revoked_reason = Column(Text)
    revoked_at = Column(Text)
    created_at = Column(Text, nullable=False)
    signature = Column(Text)
    signing_key_id = Column(Text)
    payload_hash = Column(Text)
    max_uses = Column(Integer)
    use_count = Column(Integer, nullable=False, default=0)
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_grants_tenant_id", "tenant_id"),
        Index("idx_grants_tenant_subject", "tenant_id", "subject_id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Text, primary_key=True)
    timestamp = Column(Text, nullable=False)
    subject_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    approved = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    matched_grant_id = Column(Text)
    challenge_id = Column(Text)
    challenge_present = Column(Integer, default=0)
    challenge_result = Column(Text, default="legacy_mode")
    grant_signature_result = Column(Text, default="not_checked")
    # from migration 0006
    row_hash = Column(Text)
    prev_hash = Column(Text)
    # from migration 0010
    tenant_id = Column(Text)
    workspace_id = Column(Text)
    scope = Column(Text)
    # from migration 0013: stable insertion-order tiebreak (BIGSERIAL on PG)
    seq = Column(BigInteger)
    # from migration 0020: stable machine decision code on decision events
    reason_code = Column(Text)

    __table_args__ = (
        Index("idx_audit_events_tenant_id", "tenant_id"),
        Index("idx_audit_events_seq", "seq"),
    )


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Text, primary_key=True)
    subject_id = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False)
    expires_at = Column(Text, nullable=False)
    used_at = Column(Text)
    status = Column(Text, nullable=False, default="active")
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_challenges_tenant_id", "tenant_id"),
    )


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    token_hash = Column(Text, nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(Text, nullable=False)
    # from migration 0007
    token_lookup_hash = Column(Text)
    # from migration 0009
    expires_at = Column(Text)
    rotated_at = Column(Text)
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_operators_token_lookup_hash", "token_lookup_hash"),
        Index("idx_operators_tenant_id", "tenant_id"),
    )


class GrantRequest(Base):
    __tablename__ = "grant_requests"

    id = Column(Text, primary_key=True)
    subject_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    valid_from = Column(Text, nullable=False)
    valid_until = Column(Text, nullable=False)
    requested_by = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="requested")
    approved_by = Column(Text)
    approved_at = Column(Text)
    denied_by = Column(Text)
    denied_at = Column(Text)
    denial_reason = Column(Text)
    revoked_by = Column(Text)
    revoked_at = Column(Text)
    revoked_reason = Column(Text)
    grant_id = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_grant_requests_tenant_id", "tenant_id"),
    )


class GrantExecution(Base):
    __tablename__ = "grant_executions"

    id = Column(Text, primary_key=True)
    grant_id = Column(Text)
    grant_request_id = Column(Text)
    operator_id = Column(Text)
    action = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    challenge_id = Column(Text)
    challenge_result = Column(Text)
    policy_result = Column(Text, nullable=False)
    result = Column(Text, nullable=False)
    error_code = Column(Text)
    executed_at = Column(Text, nullable=False)
    audit_event_id = Column(Text)
    metadata_json = Column(Text)
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_grant_executions_grant_id", "grant_id"),
        Index("idx_grant_executions_grant_request_id", "grant_request_id"),
        Index("idx_grant_executions_operator_id", "operator_id"),
        Index("idx_grant_executions_executed_at", "executed_at"),
        Index("idx_grant_executions_tenant_id", "tenant_id"),
    )


# ── Evidence tables ─────────────────────────────────────────────────────────

class EvidenceArchive(Base):
    __tablename__ = "evidence_archives"

    id = Column(Text, primary_key=True)
    evidence_hash = Column(Text, nullable=False)
    canonical_version = Column(Text, nullable=False)
    hash_algorithm = Column(Text, nullable=False)
    bundle_json = Column(Text, nullable=False)
    execution_id = Column(Text, nullable=False, unique=True)
    grant_id = Column(Text)
    grant_request_id = Column(Text)
    created_at = Column(Text, nullable=False)
    stored_by = Column(Text)
    # from migration 0003
    last_verified_at = Column(Text)
    last_verification_status = Column(Text)
    # from migration 0010
    tenant_id = Column(Text, nullable=False, default="demo")
    workspace_id = Column(Text)

    __table_args__ = (
        Index("idx_evidence_archives_grant_id", "grant_id"),
        Index("idx_evidence_archives_execution_id", "execution_id"),
        Index("idx_evidence_archives_created_at", "created_at"),
        Index("idx_evidence_archives_tenant_id", "tenant_id"),
    )


class EvidenceHash(Base):
    __tablename__ = "evidence_hashes"

    evidence_hash = Column(Text, primary_key=True)
    archive_id = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_evidence_hashes_archive_id", "archive_id"),
    )


# ── Provenance events ────────────────────────────────────────────────────────

class ProvenanceEvent(Base):
    __tablename__ = "provenance_events"

    id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    occurred_at = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False)
    resource_type = Column(Text)
    resource_id = Column(Text)
    execution_id = Column(Text)
    grant_id = Column(Text)
    evidence_hash = Column(Text)
    verification_status = Column(Text)
    metadata_json = Column(Text)

    __table_args__ = (
        Index("idx_provenance_events_execution_id", "execution_id"),
        Index("idx_provenance_events_grant_id", "grant_id"),
        Index("idx_provenance_events_actor_type", "actor_type"),
        Index("idx_provenance_events_occurred_at", "occurred_at"),
        Index("idx_provenance_events_resource_type_resource_id", "resource_type", "resource_id"),
    )


# ── Workspace tables ─────────────────────────────────────────────────────────

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Text, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    owner_id = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")
    description = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)
    # from migration 0016: tiered rate limiting
    plan_tier = Column(Text, nullable=False, default="free")
    rate_limit_override = Column(Integer)

    __table_args__ = (
        Index("idx_workspaces_tenant_id", "tenant_id"),
        Index("idx_workspaces_tenant_slug", "tenant_id", "slug", unique=True),
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(Text, primary_key=True)
    workspace_id = Column(Text, nullable=False)
    operator_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="workspace_member")
    invited_by = Column(Text)
    joined_at = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")

    __table_args__ = (
        Index("idx_workspace_members_workspace_id", "workspace_id"),
        Index("idx_workspace_members_operator_id", "operator_id"),
        UniqueConstraint("workspace_id", "operator_id", name="idx_workspace_members_workspace_operator"),
    )


class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id = Column(Text, primary_key=True)
    workspace_id = Column(Text, nullable=False)
    invited_by = Column(Text, nullable=False)
    email_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="workspace_member")
    status = Column(Text, nullable=False, default="pending")
    expires_at = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_workspace_invites_workspace_id", "workspace_id"),
        Index("idx_workspace_invites_email_hash", "email_hash"),
    )


# ── API Key table ─────────────────────────────────────────────────────────────

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Text, primary_key=True)
    workspace_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    key_hash = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    scopes = Column(Text, nullable=False, default="[]")
    expires_at = Column(Text)
    last_used_at = Column(Text)
    created_at = Column(Text, nullable=False)
    revoked_at = Column(Text)
    # Subject identity binding (additive, nullable): the ONLY subject this key
    # may exercise as on /v1/exercise. NULL = unbound; unbound keys are refused
    # on the exercise path (fail-closed) — they cannot assert subjects at all.
    subject_id = Column(Text)

    __table_args__ = (
        Index("idx_api_keys_workspace_id", "workspace_id"),
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )


# ── Grant Template table ───────────────────────────────────────────────────────

class GrantTemplate(Base):
    __tablename__ = "grant_templates"

    id = Column(Text, primary_key=True)
    workspace_id = Column(Text)
    name = Column(Text, nullable=False)
    description = Column(Text)
    schema_json = Column(Text, nullable=False, default="{}")
    default_values = Column(Text, nullable=False, default="{}")
    version = Column(Integer, nullable=False, default=1)
    parent_id = Column(Text)
    is_active = Column(Integer, nullable=False, default=1)
    locked = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_grant_templates_workspace_id", "workspace_id"),
        Index("idx_grant_templates_parent_id", "parent_id"),
        Index("idx_grant_templates_is_active", "is_active"),
    )


# ── Webhook tables ────────────────────────────────────────────────────────────

class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Text, primary_key=True)
    webhook_id = Column(Text, nullable=False)
    tenant_id = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    http_status = Column(Integer)
    error = Column(Text)
    attempt = Column(Integer, nullable=False, default=1)
    created_at = Column(Text, nullable=False)
    delivered_at = Column(Text)

    __table_args__ = (
        Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        Index("idx_webhook_deliveries_tenant_id", "tenant_id"),
        Index("idx_webhook_deliveries_created_at", "created_at"),
    )


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Text, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    workspace_id = Column(Text)
    url = Column(Text, nullable=False)
    events = Column(Text, nullable=False)
    secret = Column(Text, nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_webhook_subscriptions_tenant_id", "tenant_id"),
        Index("idx_webhook_subscriptions_active", "tenant_id", "active"),
    )


class AnchorRecord(Base):
    """Bookkeeping for one on-chain anchor of a workspace's audit-export head.

    PII-PREVENTION INVARIANT: exactly these 9 columns, no foreign keys to
    grants/applications, no free-text. It carries only the same {h, s, t} the
    chain payload carries (final_hash/entry_count/anchored_at) plus the chain
    bookkeeping needed to make the daily job idempotent (tx_id, network,
    anchor_label, status). ``workspace_id`` is an opaque uuid, not PII.
    """

    __tablename__ = "anchor_records"

    id = Column(Text, primary_key=True)
    workspace_id = Column(Text, nullable=False)
    final_hash = Column(Text, nullable=False)
    entry_count = Column(Integer, nullable=False)
    anchored_at = Column(Text, nullable=False)
    tx_id = Column(Text)
    network = Column(Text, nullable=False)
    anchor_label = Column(Integer, nullable=False)
    status = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_anchor_records_workspace_id", "workspace_id"),
        Index("idx_anchor_records_status", "workspace_id", "status"),
    )
