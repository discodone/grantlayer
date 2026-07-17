"""Workspace bootstrap — deliberate creation of ONE real workspace.

The product has no self-serve workspace creation: the only workspace that has
ever existed is the dev-runner's seeded demo workspace, which the production
(PostgreSQL/Alembic) path never creates. This module is the explicit,
operator-run alternative: it creates a real workspace with a real owner, and
nothing else.

Guarantees (all enforced here, none left to the caller):
  * Fail-closed owner gate — the owner operator must exist, be active, and
    belong to the target tenant. No orphan owners.
  * One transaction — the workspace row, the owner membership row, and TWO
    audit events (``workspace_created``, ``workspace_member_added``) are
    written on the same session and committed together. A failure anywhere,
    including the audit write, rolls back everything: a workspace whose own
    creation is not in the audit chain must not exist. The two events are
    entries 1 and 2 of the new workspace's audit chain.
  * Idempotent, refuse-to-clobber — re-running with identical arguments is a
    no-op reporting "already exists"; an existing workspace with the same
    (tenant_id, slug) but different name/owner is a hard error.
  * Opaque id — the workspace id is a uuid4 string, never the slug (anchor
    bookkeeping documents workspace_id as an opaque uuid, not PII).

This module deliberately does NOT create operators (use the admin API) and
does NOT depend on the demo/default seed path.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.audit_log import append_event
from ..core.models import AuditEvent
from ..core.orm import Operator, Workspace, WorkspaceMember

# Role recorded on the owner's membership row. Distinct from the operator's
# own role ("owner"): this is the workspace-membership role.
OWNER_MEMBER_ROLE = "workspace_owner"

# Recorded as workspace_members.invited_by for the bootstrap-created owner row.
BOOTSTRAP_ACTOR = "bootstrap"

# Mirrors the /v1/workspaces plan PATCH validation set.
VALID_PLAN_TIERS = frozenset({"free", "pro", "enterprise"})


class WorkspaceBootstrapError(Exception):
    """Base class: the bootstrap refused to run. Nothing was written."""


class OwnerOperatorInvalid(WorkspaceBootstrapError):
    """The owner operator is missing, inactive, or in the wrong tenant."""


class WorkspaceBootstrapConflict(WorkspaceBootstrapError):
    """A different workspace already occupies (tenant_id, slug)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceBootstrapError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_owner(session: Session, owner_operator_id: str, tenant_id: str) -> None:
    """Fail-closed owner gate: exists, active, tenant matches."""
    op = session.get(Operator, owner_operator_id)
    if op is None:
        raise OwnerOperatorInvalid(
            f"owner operator {owner_operator_id!r} does not exist — refusing "
            "(no orphan owners; create the operator first via the admin API)"
        )
    if int(op.active) != 1:
        raise OwnerOperatorInvalid(
            f"owner operator {owner_operator_id!r} is not active — refusing"
        )
    if op.tenant_id != tenant_id:
        raise OwnerOperatorInvalid(
            f"owner operator {owner_operator_id!r} belongs to tenant "
            f"{op.tenant_id!r}, not {tenant_id!r} — refusing"
        )


def _existing_is_identical(
    session: Session,
    existing: Workspace,
    *,
    name: str,
    owner_operator_id: str,
) -> bool:
    """True only when the existing workspace matches this bootstrap exactly."""
    if existing.name != name or existing.owner_id != owner_operator_id:
        return False
    membership = session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == existing.id,
            WorkspaceMember.operator_id == owner_operator_id,
            WorkspaceMember.role == OWNER_MEMBER_ROLE,
            WorkspaceMember.status == "active",
        )
    ).scalar_one_or_none()
    return membership is not None


def bootstrap_workspace(
    session: Session,
    *,
    tenant_id: str,
    name: str,
    slug: str,
    owner_operator_id: str,
    description: Optional[str] = None,
    plan_tier: str = "free",
) -> dict:
    """Create one workspace + its owner membership + its two genesis audit events.

    Returns ``{"status": "created" | "already_exists", "workspace_id": <uuid>}``.
    Owns the transaction: commits on success, rolls back and re-raises on any
    failure. Raises OwnerOperatorInvalid / WorkspaceBootstrapConflict /
    WorkspaceBootstrapError without writing anything.
    """
    tenant_id = _require_nonempty(tenant_id, "tenant_id")
    name = _require_nonempty(name, "name")
    slug = _require_nonempty(slug, "slug")
    owner_operator_id = _require_nonempty(owner_operator_id, "owner_operator_id")
    if plan_tier not in VALID_PLAN_TIERS:
        raise WorkspaceBootstrapError(
            f"plan_tier must be one of {sorted(VALID_PLAN_TIERS)}, got {plan_tier!r}"
        )

    _validate_owner(session, owner_operator_id, tenant_id)

    existing = session.execute(
        select(Workspace).where(
            Workspace.tenant_id == tenant_id, Workspace.slug == slug
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _existing_is_identical(
            session, existing, name=name, owner_operator_id=owner_operator_id
        ):
            return {"status": "already_exists", "workspace_id": existing.id}
        raise WorkspaceBootstrapConflict(
            f"a different workspace already occupies (tenant={tenant_id!r}, "
            f"slug={slug!r}) — refusing to clobber. If you truly intend to "
            "replace it, that is a deliberate manual act, not a bootstrap re-run."
        )

    workspace_id = str(uuid.uuid4())
    now = _now_iso()
    try:
        session.add(
            Workspace(
                id=workspace_id,
                tenant_id=tenant_id,
                name=name,
                slug=slug,
                owner_id=owner_operator_id,
                status="active",
                description=description,
                created_at=now,
                updated_at=now,
                plan_tier=plan_tier,
            )
        )
        session.add(
            WorkspaceMember(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                operator_id=owner_operator_id,
                role=OWNER_MEMBER_ROLE,
                invited_by=BOOTSTRAP_ACTOR,
                joined_at=now,
                status="active",
            )
        )
        session.flush()

        # Entries 1 and 2 of this workspace's audit chain — written on the SAME
        # transaction so a failed audit write rolls back the workspace itself.
        conn = session.connection()
        append_event(
            AuditEvent(
                subject_id=owner_operator_id,
                role="owner",
                action="workspace_created",
                resource=f"workspace/{workspace_id}",
                approved=True,
                reason=f"Workspace '{slug}' bootstrapped for tenant '{tenant_id}'",
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                scope="tenant",
            ),
            conn=conn,
        )
        append_event(
            AuditEvent(
                subject_id=owner_operator_id,
                role="owner",
                action="workspace_member_added",
                resource=f"operator/{owner_operator_id}",
                approved=True,
                reason=(
                    f"Operator bound as {OWNER_MEMBER_ROLE} of workspace '{slug}'"
                ),
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                scope="tenant",
            ),
            conn=conn,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"status": "created", "workspace_id": workspace_id}
