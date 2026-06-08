# GL-224 — Workspace Schema / Membership Baseline

## Overview

GL-224 introduces the database schema for workspace identity, membership, and
invite tracking. It adds three new tables (`workspaces`, `workspace_members`,
`workspace_invites`) via migration `0011_gl224_workspace_schema_membership_baseline`,
backfills existing demo-tenant resources to the canonical default workspace,
and exposes three new dataclasses in `models.py`.

This issue is a **schema-only** baseline. No server routes, auth enforcement,
or API changes are made here. Those are deferred to subsequent issues.

---

## Workspace Schema

### workspaces

| Column      | Type    | Notes                                       |
|-------------|---------|---------------------------------------------|
| id          | TEXT PK | UUID                                        |
| tenant_id   | TEXT    | NOT NULL — tenant scope                     |
| name        | TEXT    | Human-readable name                         |
| slug        | TEXT    | URL-friendly, unique per tenant             |
| owner_id    | TEXT    | operator_id of workspace owner              |
| status      | TEXT    | 'active' \| 'inactive' \| 'suspended'       |
| description | TEXT    | Optional description (nullable)             |
| created_at  | TEXT    | ISO-8601 UTC                                |
| updated_at  | TEXT    | ISO-8601 UTC                                |

**Unique constraint:** `(tenant_id, slug)` — no two workspaces in the same
tenant may share a slug.

### workspace_members

| Column      | Type    | Notes                                            |
|-------------|---------|--------------------------------------------------|
| id          | TEXT PK | UUID                                             |
| workspace_id| TEXT    | FK → workspaces.id                               |
| operator_id | TEXT    | FK → operators.id                                |
| role        | TEXT    | workspace_owner \| workspace_admin \| workspace_member \| workspace_readonly |
| invited_by  | TEXT    | operator_id of inviter (nullable)                |
| joined_at   | TEXT    | ISO-8601 UTC                                     |
| status      | TEXT    | 'active' \| 'removed' \| 'suspended'             |

**Unique constraint (index):** `(workspace_id, operator_id)` — one membership
record per operator per workspace.

### workspace_invites

| Column      | Type    | Notes                                         |
|-------------|---------|-----------------------------------------------|
| id          | TEXT PK | UUID                                          |
| workspace_id| TEXT    | FK → workspaces.id                            |
| invited_by  | TEXT    | operator_id of the inviting operator          |
| email_hash  | TEXT    | SHA-256 of invitee email — no plaintext email |
| role        | TEXT    | Target role for the invitee                   |
| status      | TEXT    | 'pending' \| 'accepted' \| 'expired' \| 'revoked' |
| expires_at  | TEXT    | ISO-8601 UTC                                  |
| created_at  | TEXT    | ISO-8601 UTC                                  |

**Privacy note:** Invitee email is stored as a hash only. No plaintext email is
persisted in the database.

---

## Migration

**File:** `backend/src/migrations/0011_gl224_workspace_schema_membership_baseline.py`

**Version:** `0011_gl224_workspace_schema_membership_baseline`

Both SQLite and PostgreSQL are supported. The migration is idempotent — re-running
`apply(conn)` is safe and will not create duplicate rows or raise errors.

---

## Backfill Strategy

1. Insert a canonical demo workspace `{ id: 'default', tenant_id: 'demo', slug: 'default' }`
   if not already present.
2. Update all existing resource rows (`grants`, `grant_requests`, `challenges`,
   `grant_executions`, `evidence_archives`) where `workspace_id IS NULL AND tenant_id = 'demo'`
   to `workspace_id = 'default'`.
3. Non-demo tenants are **not** backfilled — null `workspace_id` on non-demo tenants
   is a data-integrity signal to investigate, not silently fix.
4. Rows that already have a non-null `workspace_id` are not modified.

---

## Indexes

| Index name                             | Table             | Columns                     | Unique |
|----------------------------------------|-------------------|-----------------------------|--------|
| idx_workspaces_tenant_id               | workspaces        | tenant_id                   | No     |
| idx_workspaces_tenant_slug             | workspaces        | tenant_id, slug             | Yes    |
| idx_workspace_members_workspace_id     | workspace_members | workspace_id                | No     |
| idx_workspace_members_operator_id      | workspace_members | operator_id                 | No     |
| idx_workspace_members_workspace_operator | workspace_members | workspace_id, operator_id | Yes    |
| idx_workspace_invites_workspace_id     | workspace_invites | workspace_id                | No     |
| idx_workspace_invites_email_hash       | workspace_invites | email_hash                  | No     |

---

## New Models (`backend/src/models.py`)

- `Workspace` — workspace entity with `to_dict()`
- `WorkspaceMember` — membership record with `to_dict()`
- `WorkspaceInvite` — invite record with `to_dict()`
- `WorkspaceStatus` — Literal type: `"active" | "inactive" | "suspended"`
- `WorkspaceMemberStatus` — Literal type: `"active" | "removed" | "suspended"`
- `WorkspaceInviteStatus` — Literal type: `"pending" | "accepted" | "expired" | "revoked"`
- `WorkspaceMemberRole` — Literal type for the four workspace roles

---

## Rollback Strategy

To roll back GL-224:

1. `DROP TABLE workspace_invites`
2. `DROP TABLE workspace_members`
3. `DROP TABLE workspaces`
4. `UPDATE <table> SET workspace_id = NULL WHERE workspace_id = 'default'` for each backfilled table

No automated rollback script is provided in this baseline sprint.

---

## Safety Confirmations

- GL-224 is a **schema-only** migration. No server routes, no auth enforcement,
  no API changes, no client-facing behavior changes.
- GL-224 does not enable real customer data, real customer tenants, or production
  SaaS access.
- GL-224 does not claim Production SaaS readiness.
- Production SaaS remains **NO-GO**.
- Real Customer Data remains **NO-GO**.
- Private Grant / Institutional Data remains **NO-GO**.
- Official SDK/Package remains **NO-GO**.
- Compliance Certification remains **NO-GO**.
- Live PostgreSQL Production Readiness remains **NO-GO**.
- No exploit details are included.
- No real secrets are included.
- No real customer data is referenced.
- No public push / publish has occurred.
- No deployment, cloud, K8s, Terraform, or Helm files have been modified.
- No TLS cert or private key files have been modified.
- No package metadata (setup.py, package.json) has been modified.
- The migration is idempotent and safe to re-run.
- `backend/src/server.py`, `auth.py`, `grants.py`, `grant_requests.py`,
  `identity_access.py`, and `operators.py` are **not modified**.
- Boundaries established in GL-214 through GL-223 are **preserved**.

---

## Scope Boundaries (Deferred)

The following are explicitly out of scope for GL-224:

- Workspace API endpoints (`POST /workspaces`, `GET /workspaces`, etc.)
- Workspace enforcement in the policy engine
- Cross-workspace isolation enforcement at the application layer
- Workspace audit event propagation
- FK constraints from resource tables to `workspaces(id)` (SQLite does not
  enforce FK constraints on existing columns; deferred to enforcement sprint)
- Automated rollback script

---

## Recommended Next Issues

- **GL-225:** Workspace API — `POST /workspaces`, `GET /workspaces`,
  `POST /workspaces/{id}/members`
- **GL-226:** Workspace enforcement in policy engine and resource CRUD
- **GL-227:** Cross-workspace isolation enforcement and audit propagation
