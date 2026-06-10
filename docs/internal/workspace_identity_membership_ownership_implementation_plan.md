# GL-223 — Workspace Identity / Membership / Ownership Implementation Plan

**Issue ID:** GL-223
**Title:** Workspace Identity / Membership / Ownership Implementation Plan
**Branch:** `gl-223-workspace-identity-membership-ownership-implementation-plan`
**Status:** Internal / Developer Preview — Planning Only

GL-223 is an implementation plan, not the implementation itself.
GL-223 does not add migrations.
GL-223 does not enable real customer, private grant, or institutional data.
GL-223 does not claim Production SaaS readiness.
GL-223 does not change public export, publish, or visibility.

Developer Preview remains GO / CONTINUE.
Controlled External Technical Review remains GO with strict boundaries.
Synthetic/Demo Controlled Pilot remains CONDITIONAL.
Real Customer Data remains NO-GO.
Private Grant / Institutional Data remains NO-GO.
Production SaaS remains NO-GO.
Official SDK/Package remains NO-GO.
Compliance Certification remains NO-GO.
Live PostgreSQL Production Readiness remains NO-GO.

Security-sensitive reports route to GitHub Security Advisories.
No exploit details are included.
No real secrets are included.
No real customer, private grant, or private institutional data is included.

Unrelated website-design/import files (`website-design/`,
`docs/website_design_workspace_import_report.md`,
`docs/website_design_workspace_import_report_dirty_stop.md`,
and similarly named files) are excluded from GL-223.

---

## Context

GL-214 through GL-222 are merged internally. The final readiness matrix v6
from GL-221, confirmed by GL-222, identifies the following current posture:

| Tier | Decision |
|---|---|
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Snapshot Preparation | CONDITIONAL — separate explicit gate required |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

GL-215 remains the authoritative tenant/workspace runtime baseline:
`tenant_id` is server-derived and enforced at application level.
`workspace_id` is reserved/nullable and not production-enforced.

GL-213 and GL-221 both identified workspace identity, membership, and
ownership as remaining production blockers requiring a plan before
implementation can proceed safely.

GL-223 provides that plan.

---

## Scope

GL-223 covers:

1. Documentation of the current tenant/workspace enforcement state.
2. Documentation of workspace trust gaps.
3. The workspace identity model to be implemented in a future issue.
4. The membership model.
5. The ownership model.
6. The role/scope model.
7. The workspace lifecycle model (invitation, join, leave).
8. The admin/operator ownership boundary.
9. The server-derived workspace context model.
10. The unsafe workspace override prevention model.
11. Cross-workspace lookup and mutation denial models.
12. The audit/provenance/evidence/compliance propagation model.
13. The database/schema plan.
14. The migration/backfill plan.
15. The API/server plan.
16. The OpenAPI impact plan.
17. The testing strategy.
18. The rollout and rollback strategy.
19. The compatibility model for current demo/synthetic flows.
20. Remaining blockers before real data.
21. Proposed implementation issue breakdown.
22. A risk register.

---

## Non-Goals

GL-223 does not:
- Implement the full workspace system.
- Add database migrations.
- Create DB schema changes.
- Modify API behavior or routing.
- Change the OpenAPI spec beyond planning references.
- Enable real customer, private grant, or institutional data.
- Claim Production SaaS readiness.
- Add dependencies or package metadata.
- Create public snapshots, export directories, release branches, or public pushes.
- Change GitHub workflows, snapshot publish scripts, visibility, or deployment config.
- Weaken GL-214 through GL-222 boundaries.

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/controlled_external_review_handoff_pack.md | Yes |
| docs/examples/gl222/controlled_external_review_handoff_pack.json | Yes |
| docs/workspace_enforcement_final_go_no_go_v6.md | Yes |
| docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json | Yes |
| docs/production_runtime_infrastructure_hardening_pack.md | Yes |
| docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json | Yes |
| docs/production_identity_access_hardening_pack.md | Yes |
| docs/examples/gl219/production_identity_access_hardening_pack.json | Yes |
| docs/public_external_review_export_safety_pack.md | Yes |
| docs/examples/gl218/public_external_review_export_safety_pack.json | Yes |
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/tenant_workspace_data_model_design.md | Yes |
| docs/examples/gl144/tenant_workspace_data_model_design.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/openapi.yaml | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/server.py | Inspected (planning context only) |
| backend/src/config.py | Inspected (planning context only) |
| backend/src/auth.py | Inspected (planning context only) |
| backend/src/identity_access.py | Inspected (planning context only) |
| backend/src/operators.py | Inspected (planning context only) |
| backend/src/audit_log.py | Inspected (planning context only) |
| backend/src/db.py | Inspected (planning context only) |
| backend/src/models.py | Inspected (planning context only) |
| backend/src/grants.py | Inspected (planning context only) |
| backend/src/grant_requests.py | Inspected (planning context only) |

---

## 1. Current Tenant/Workspace State Summary

### 1.1 What is implemented

- **`tenant_id` on all business resources.** Migration `0010_gl200b_tenant_workspace_isolation`
  added `tenant_id TEXT NOT NULL DEFAULT 'demo'` and `workspace_id TEXT DEFAULT NULL`
  to all resource tables (grants, grant requests, grant executions, audit events,
  provenance events, operators, challenges).
- **Server-derived `tenant_id`.** `server.py::_get_tenant_id()` extracts
  `tenant_id` from the auth context (from operator record in operator-model
  mode, or `"demo"` in legacy admin-token mode). Clients cannot override.
- **Tenant-filtered queries.** All major read routes filter by `tenant_id`.
  Cross-tenant lookup returns 404.
- **Tenant-propagated audit events.** `AuditEvent` and `ProvenanceEvent` carry
  `tenant_id`. Audit writes propagate the authenticated tenant.
- **Operator `tenant_id` server-assigned.** GL-206 requires `tenant_id` as a
  positional argument to `create_operator()`; clients cannot self-assign tenant.
- **Revoke/inactive fail-closed.** Revoked and inactive operators are denied
  authentication.
- **Admin/operator route protection.** `/admin/operators/*` routes require admin
  role.

### 1.2 What is NOT implemented (current gaps)

- **`workspace_id` is reserved/nullable.** No workspace enforcement exists.
  `workspace_id = NULL` on all records. All workspace-specific queries are
  planned but not implemented.
- **No `workspaces` table.** There is no persistent workspace entity. A
  workspace cannot be created, named, or retrieved.
- **No workspace membership table.** There is no `workspace_members` or
  equivalent. No operator is assigned to a workspace. No join/leave lifecycle
  exists.
- **No workspace ownership model.** Resources are owned by tenants, not
  workspaces. There is no `workspace_owner_id` field or concept in the DB.
- **No workspace-level role/scope.** Operator roles (`grant_admin`, `approver`,
  `agent`) are tenant-level. No workspace-specific role assignment exists.
- **No workspace-scoped authorization in server routes.** Routes filter by
  `tenant_id` but not `workspace_id`. Any operator in a tenant can read any
  grant in the same tenant regardless of workspace.
- **No workspace invitation/join/leave lifecycle.** No invite tokens, join
  flows, or leave/removal flows exist.
- **No workspace context in API responses.** Grant/request/execution responses
  include `tenant_id` (from the operator) but `workspace_id` is `null`.
- **No cross-workspace denial.** A future workspace-aware query must explicitly
  deny cross-workspace reads. This guard does not exist.
- **No workspace provenance propagation.** Audit events carry `workspace_id =
  null`. Future workspace-scoped audit queries are blocked.

---

## 2. Current Workspace Trust Gaps

| Gap ID | Gap | Severity |
|---|---|---|
| WG-001 | `workspace_id` is nullable/unset on all resources — no workspace enforcement | P0 |
| WG-002 | No `workspaces` entity — a workspace cannot be created or looked up | P0 |
| WG-003 | No `workspace_members` entity — no operator/workspace association | P0 |
| WG-004 | No workspace-scoped authorization in server routes | P0 |
| WG-005 | No workspace ownership model on resources | P1 |
| WG-006 | No workspace-level role/scope assignment | P1 |
| WG-007 | No workspace invitation/join/leave lifecycle | P1 |
| WG-008 | Audit events carry `workspace_id = null` — no workspace audit trail | P1 |
| WG-009 | No cross-workspace lookup denial guard | P1 |
| WG-010 | No cross-workspace mutation denial guard | P1 |
| WG-011 | No workspace provenance propagation | P2 |
| WG-012 | No workspace-scoped API endpoints | P2 |
| WG-013 | No OpenAPI workspace path/parameter documentation | P2 |
| WG-014 | No workspace migration/backfill plan for existing `null` records | P2 |

---

## 3. Workspace Identity Model

### 3.1 Core concept

A **workspace** is a named, scoped operating context within a tenant. Each
workspace has:
- A stable UUID (`workspace_id`)
- A human-readable name (`name`, unique within tenant)
- A `tenant_id` (FK to tenant, immutable after creation)
- An `owner_operator_id` (the creating or explicitly-assigned owner)
- A `created_at` timestamp
- An `active` boolean (deactivated workspaces block access)
- An optional `description`

### 3.2 Trust model

- `workspace_id` is server-assigned on resource creation. Clients cannot
  supply or override `workspace_id` on any resource write.
- `workspace_id` is derived from the authenticated operator's current workspace
  context (set at operator-session time via a future workspace context API),
  not from request body parameters.
- A `workspace_id` present in a request body must be rejected with 400 or
  silently ignored in favor of the server-derived value.

### 3.3 Workspace entity (planned schema — not implemented in GL-223)

```
workspaces
  id            TEXT PRIMARY KEY
  tenant_id     TEXT NOT NULL REFERENCES tenants(id)  -- or operator-derived
  name          TEXT NOT NULL
  description   TEXT DEFAULT NULL
  owner_id      TEXT NOT NULL REFERENCES operators(id)
  active        INTEGER NOT NULL DEFAULT 1
  created_at    TEXT NOT NULL
  updated_at    TEXT NOT NULL
  UNIQUE(tenant_id, name)
```

---

## 4. Membership Model

### 4.1 Concept

A **workspace membership** is an explicit record binding one operator to one
workspace with a defined role. Operators are not automatically members of any
workspace. Membership must be granted explicitly by a workspace owner or admin.

### 4.2 Membership entity (planned schema — not implemented in GL-223)

```
workspace_members
  id              TEXT PRIMARY KEY
  workspace_id    TEXT NOT NULL REFERENCES workspaces(id)
  operator_id     TEXT NOT NULL REFERENCES operators(id)
  workspace_role  TEXT NOT NULL  -- owner | admin | member | readonly
  invited_by      TEXT REFERENCES operators(id)
  joined_at       TEXT NOT NULL
  active          INTEGER NOT NULL DEFAULT 1
  UNIQUE(workspace_id, operator_id)
```

### 4.3 Membership rules

- An operator may be a member of multiple workspaces within the same tenant.
- An operator may only access resources in workspaces they are an active member
  of.
- Membership grants access within the workspace; tenant membership is a
  prerequisite (an operator must belong to the tenant before joining a
  workspace).
- Deactivated membership denies access fail-closed.
- Workspace owner is automatically the first member with role `owner`.

### 4.4 Membership invariants

- `workspace_id` and `operator_id` together form a unique constraint.
- An operator with no active workspace membership in the requested workspace
  receives 403 (not 404 — to prevent workspace enumeration via timing).
- Membership revocation is audited.

---

## 5. Ownership Model

### 5.1 Workspace ownership

- Each workspace has exactly one `owner_id` (FK to `operators.id`).
- The owner may transfer ownership to another active member with role `owner`
  or `admin`.
- Ownership transfer is audited.
- The last owner cannot leave without first transferring ownership or the
  workspace being deactivated by a tenant admin.

### 5.2 Resource ownership within workspace

- Every business resource (grant, grant request, grant execution, evidence,
  audit event, provenance event) must carry both `tenant_id` and
  `workspace_id` after workspace enforcement is implemented.
- `workspace_id = NULL` on legacy/demo records is acceptable only in
  `developer_preview` and `demo` runtime modes. In production-like modes,
  `workspace_id = NULL` on a resource write must be rejected or assigned from
  the authenticated operator's workspace context.
- Resources cannot be moved between workspaces. `workspace_id` is immutable
  after creation.
- Resources cannot be shared across workspace boundaries in normal operation.
  Cross-workspace sharing, if ever added, requires an explicit future design.

### 5.3 Admin/operator override boundary

- Tenant admins may manage workspace membership and deactivate workspaces but
  may NOT read workspace-owned resources unless they are also a workspace
  member.
- A future super-admin or system-operator role for break-glass access is not
  defined in GL-223 and must be a separate design decision.

---

## 6. Role / Scope Model

### 6.1 Tenant-level roles (existing)

| Role | Permissions |
|---|---|
| `owner` | Full tenant control, operator create/revoke |
| `grant_admin` | Create/revoke grants within tenant |
| `approver` | Approve/deny grant requests |
| `agent` | Submit grant requests, execute grants |
| `readonly` | Read-only access to tenant resources |

### 6.2 Workspace-level roles (planned)

| Role | Permissions within workspace |
|---|---|
| `workspace_owner` | Full workspace control, membership management, ownership transfer |
| `workspace_admin` | Add/remove members, manage workspace settings |
| `workspace_member` | Create/read resources within workspace |
| `workspace_readonly` | Read-only access within workspace |

### 6.3 Composition rule

An operator's effective permission for an action within a workspace is the
**intersection** of their tenant-level role and their workspace-level role:
- Tenant `grant_admin` + workspace `workspace_readonly` → read-only within
  workspace (workspace role is more restrictive).
- Tenant `approver` + workspace `workspace_member` → may approve requests
  within workspace but not create grants.
- Tenant `readonly` + workspace `workspace_owner` → effective readonly (tenant
  role is the ceiling).

### 6.4 Scope model

- Resource access decisions must check:
  1. Is the operator authenticated? (existing)
  2. Does the operator belong to the resource's tenant? (existing, enforced)
  3. Is the operator an active member of the resource's workspace? (new)
  4. Does the operator's workspace role permit the requested operation? (new)

---

## 7. Workspace Lifecycle Model

### 7.1 Workspace creation

1. A tenant admin or `owner`-role operator sends `POST /workspaces` with
   `{ "name": "...", "description": "..." }`.
2. Server assigns `workspace_id` (UUID), `tenant_id` (from operator auth),
   `owner_id` (from operator auth). Client cannot supply these.
3. Creating operator is automatically added to `workspace_members` with role
   `workspace_owner`.
4. `workspace_created` audit event is emitted.

### 7.2 Member invitation

1. Workspace owner/admin sends `POST /workspaces/{workspace_id}/members`
   with `{ "operator_id": "...", "role": "..." }`.
2. Server verifies inviting operator is active workspace owner/admin.
3. Server verifies invited operator belongs to the same tenant.
4. Membership record is created with `active = 1`.
5. `workspace_member_added` audit event is emitted.

### 7.3 Member removal/leave

1. Owner/admin sends `DELETE /workspaces/{workspace_id}/members/{operator_id}`.
2. Member sends `POST /workspaces/{workspace_id}/leave`.
3. Server blocks removal of the last owner (unless workspace is being deactivated).
4. Membership record is set to `active = 0`.
5. `workspace_member_removed` audit event is emitted.

### 7.4 Workspace deactivation

1. Tenant admin sends `POST /admin/workspaces/{workspace_id}/deactivate`.
2. Workspace `active` is set to `0`.
3. All membership access is denied fail-closed.
4. Existing resources remain readable by tenant admin for audit/provenance
   purposes (but not through workspace-scoped routes).
5. `workspace_deactivated` audit event is emitted.

### 7.5 Workspace deletion

Workspace deletion is explicitly deferred. Audit immutability requires that
resources with `workspace_id` references remain accessible for audit review
even after a workspace is deactivated. Hard deletion requires a separate data
retention/erasure policy design.

---

## 8. Admin/Operator Ownership Boundary

### 8.1 Tenant admin capabilities

- Create workspaces (on behalf of tenant).
- Deactivate workspaces.
- List workspaces within tenant.
- View workspace membership lists.
- Forcibly remove members (break-glass, audited).
- Transfer workspace ownership.
- **Cannot** read workspace-owned grant/request/execution resources unless also
  a workspace member (enforced by workspace filter on resource routes).

### 8.2 Workspace owner capabilities

- Invite/remove workspace members.
- Transfer workspace ownership to another member.
- Deactivate workspace (subject to tenant admin approval in future).
- **Can** read/write all resources within their workspace (subject to
  tenant-level role).

### 8.3 Operator capabilities (member without admin)

- Read/write resources within their workspace per tenant-level + workspace role.
- Leave workspace.
- **Cannot** access other workspaces.
- **Cannot** modify workspace membership.

### 8.4 Invariant

Operator `tenant_id` and workspace membership are server-assigned and
server-enforced. No client-supplied `tenant_id` or `workspace_id` value can
override the server-derived workspace context.

---

## 9. Server-Derived Workspace Context Model

### 9.1 Context derivation

After workspace enforcement is implemented, a server request handler derives
workspace context in this order:

1. Authenticate operator (existing: from `Authorization` header).
2. Extract `tenant_id` from operator record (existing, server-assigned).
3. Determine the effective `workspace_id`:
   a. From a future `X-Workspace-ID` header (if present and the operator is
      an active member of that workspace within their tenant).
   b. From the operator's default workspace (if a single-workspace operator).
   c. Deny with 400 `workspace_context_required` if the operator is a member
      of multiple workspaces and no workspace header is supplied.
4. Verify the operator is an active member of the resolved workspace.
5. Propagate (`tenant_id`, `workspace_id`) to all resource reads/writes.

### 9.2 Workspace context injection

- All route handlers must receive and pass `(tenant_id, workspace_id)` to
  data-layer functions.
- No route handler may accept `workspace_id` from the request body for
  authorization decisions. Only `X-Workspace-ID` header (a future addition)
  is trusted for workspace context selection.
- The data layer must validate that the passed `workspace_id` belongs to the
  passed `tenant_id` before any data operation.

---

## 10. Unsafe Workspace Override Prevention Model

### 10.1 Prevented vectors

- **Request body injection.** Any `workspace_id` or `tenant_id` present in a
  request body must be ignored for authorization decisions (may be included in
  response for display, but derived from server context for writes).
- **Header injection (non-workspace headers).** `tenant_id` must never be
  accepted from any client header. Only `X-Workspace-ID` (once implemented)
  is permitted, and only after membership verification.
- **Token elevation.** Operator tokens must not carry a `workspace_id` claim
  that the server trusts without membership verification. The operator token
  carries `tenant_id` and `operator_id`; workspace context is resolved at
  request time, not minted into the token.
- **Cross-workspace resource address.** A resource URL (e.g.
  `/grants/{id}`) must not be resolvable by an operator in a different
  workspace, even within the same tenant. The query must include
  `AND workspace_id = ?` after workspace enforcement is enabled.
- **Null workspace bypass.** `workspace_id = NULL` must not be a magic value
  that grants cross-workspace access. In production-like modes, null workspace
  on a resource must either return 404 or be treated as a legacy-only
  developer-preview resource.

### 10.2 Required server-side checks

Each protected route handler must, in order:
1. Authenticate.
2. Derive `tenant_id` (existing).
3. Derive `workspace_id` (new — per section 9).
4. Verify workspace membership and role.
5. Filter all DB queries by both `tenant_id` AND `workspace_id`.
6. Deny 403 if workspace membership check fails.

---

## 11. Cross-Workspace Lookup Denial Model

### 11.1 Read routes

After workspace enforcement:
- `GET /grants` → filter by `tenant_id = ? AND workspace_id = ?`.
- `GET /grants/{id}` → verify record has matching `tenant_id` AND
  `workspace_id`; return 404 otherwise.
- `GET /grant-requests` → filter by `tenant_id = ? AND workspace_id = ?`.
- `GET /grant-requests/{id}` → workspace match required.
- `GET /executions/{id}` → workspace match required.
- `GET /audit-events` → filter by `tenant_id = ? AND workspace_id = ?`.
- `GET /provenance` → filter by `tenant_id = ? AND workspace_id = ?`.

### 11.2 404 vs 403

Cross-workspace resource lookups return **404** (not 403) to prevent workspace
enumeration. A 403 would reveal that a resource with that ID exists in a
different workspace.

### 11.3 Tenant admin exception

Tenant admin read of workspace resources (for audit/break-glass) must go
through a separately authorized admin route (`GET
/admin/workspaces/{id}/resources`) and must emit a `workspace_admin_access`
audit event.

---

## 12. Cross-Workspace Mutation Denial Model

### 12.1 Write routes

After workspace enforcement:
- `POST /grants` → `workspace_id` assigned from operator context. Any
  client-supplied `workspace_id` in body is rejected.
- `POST /grant-requests` → same as above.
- `POST /grant-requests/{id}/approve` → operator must be workspace member with
  workspace role permitting approval AND tenant-level `approver` or above.
- `POST /grant-requests/{id}/deny` → same as above.
- `POST /grant-requests/{id}/execute` → same as above.
- `POST /grants/{id}/revoke` → must match `tenant_id` AND `workspace_id` of
  operator's current context.

### 12.2 Mutation denial invariant

A mutation that would assign `workspace_id` from client input, or that would
modify a resource whose `workspace_id` does not match the operator's current
workspace context, must be denied fail-closed with 403 and a logged audit
event.

---

## 13. Audit / Evidence / Provenance / Compliance Propagation Model

### 13.1 Audit event propagation

After workspace enforcement:
- Every `AuditEvent` must carry a non-null `workspace_id` for all events in
  production-like modes.
- `workspace_id` must be derived from the operator context at event-write
  time, not from any client-supplied value.
- Audit events with `workspace_id = NULL` in production-like mode must be
  rejected by the audit writer (fail-closed).

### 13.2 Provenance event propagation

- Every `ProvenanceEvent` must carry a non-null `workspace_id` after
  workspace enforcement.
- Provenance event workspace attribution must match the resource's
  `workspace_id`.

### 13.3 Evidence archive workspace attribution

- Evidence archive records must carry `workspace_id`.
- Evidence queried for a workspace must be filtered by `workspace_id`.

### 13.4 Compliance / immutability implications

- The audit hash chain (GL-103/GL-104/GL-105) must incorporate `workspace_id`
  as a chain input field after workspace enforcement is live. This is a
  breaking audit-chain change.
- Existing audit records with `workspace_id = NULL` must be treated as
  legacy/developer-preview records. The hash chain for pre-enforcement records
  remains valid as-is.
- A future compliance-gate must verify that all audit events in a compliance
  window carry non-null `workspace_id` before compliance readiness is claimed.

### 13.5 Retention / erasure workspace boundary

- Data retention and erasure policies (GDPR right-to-erasure) must be
  workspace-scoped. Erasure of a workspace must cascade to all owned resources.
- This is explicitly deferred beyond GL-223.

---

## 14. Database / Schema Plan

The following schema changes are planned for a future implementation issue.
**None of these changes are made in GL-223.**

### 14.1 New tables

```sql
-- Planned: workspaces table
CREATE TABLE workspaces (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    owner_id    TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(tenant_id, name)
);

-- Planned: workspace_members table
CREATE TABLE workspace_members (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(id),
    operator_id     TEXT NOT NULL REFERENCES operators(id),
    workspace_role  TEXT NOT NULL,
    invited_by      TEXT,
    joined_at       TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    UNIQUE(workspace_id, operator_id)
);
```

### 14.2 Indexes (planned)

```sql
CREATE INDEX idx_workspaces_tenant_id ON workspaces(tenant_id);
CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_members_operator_id ON workspace_members(operator_id);
```

### 14.3 Constraints

- `workspace_role` must be validated against an allowlist:
  `('workspace_owner', 'workspace_admin', 'workspace_member', 'workspace_readonly')`.
- `tenant_id` on workspace must match `operator.tenant_id` at creation.
- `workspace_id` on all business resource tables must reference a valid, active
  workspace in the same tenant.

### 14.4 Existing table changes (planned)

No column additions are needed (columns already exist with `DEFAULT NULL`).
Required changes:
- Add FK constraint from resource tables to `workspaces(id)` (deferred to
  implementation migration).
- Add index on `(tenant_id, workspace_id)` for all resource tables (confirm
  existing coverage).

---

## 15. Migration / Backfill Plan

### 15.1 Migration strategy

A single new migration (`0012_gl224_workspace_enforcement` or equivalent) will:
1. Create the `workspaces` table.
2. Create the `workspace_members` table.
3. Insert a default/legacy workspace `{ id: 'default', tenant_id: 'demo',
   name: 'default', ... }` for backfill.
4. Update all existing resource records with `workspace_id = NULL` to
   `workspace_id = 'default'` within `tenant_id = 'demo'`.

### 15.2 Backfill rules

- Backfill only applies to `developer_preview` and `demo` runtime modes.
- Production-like mode must never backfill — null workspace records in
  production are a data integrity error requiring investigation.
- Backfill is idempotent (re-runnable safely).
- Backfill must not touch records that already have a non-null `workspace_id`.

### 15.3 Migration ordering

Migration must be added after the last merged migration. Current last known
migration: `0011_*` (or as identified at implementation time).

### 15.4 Rollback strategy for migration

The migration can be reversed by:
1. Dropping `workspace_members`.
2. Dropping `workspaces`.
3. Setting `workspace_id = NULL` on all backfilled resources.

Automated rollback scripts must be provided at implementation time.

---

## 16. API / Server Plan

The following server changes are planned for future implementation issues.
**None of these changes are made in GL-223.**

### 16.1 New endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/workspaces` | Create a workspace (tenant admin or owner role) |
| `GET` | `/workspaces` | List workspaces the operator is a member of |
| `GET` | `/workspaces/{workspace_id}` | Get workspace details |
| `POST` | `/workspaces/{workspace_id}/members` | Add a member |
| `DELETE` | `/workspaces/{workspace_id}/members/{operator_id}` | Remove a member |
| `POST` | `/workspaces/{workspace_id}/leave` | Leave a workspace |
| `POST` | `/workspaces/{workspace_id}/transfer-ownership` | Transfer ownership |
| `POST` | `/admin/workspaces/{workspace_id}/deactivate` | Deactivate workspace |
| `GET` | `/admin/workspaces` | List all workspaces (tenant admin) |

### 16.2 Modified endpoints

All existing resource endpoints must be updated to:
- Accept `X-Workspace-ID` header for workspace context selection.
- Derive `workspace_id` server-side (not from body).
- Filter data queries by `(tenant_id, workspace_id)`.
- Reject requests where workspace context cannot be resolved.

### 16.3 Auth changes

`check_auth()` must return `workspace_id` in addition to `tenant_id` after
workspace context is resolved. The `_get_workspace_context()` helper is the
appropriate extension point.

### 16.4 Existing route backward compatibility

During the transition period (developer preview / demo mode):
- Routes that currently return resources with `workspace_id = NULL` continue
  to function if the operator is in `developer_preview` or `demo` mode.
- In production-like mode, `workspace_id = NULL` resources must be invisible
  to workspace-scoped queries.

---

## 17. OpenAPI Impact Plan

The following OpenAPI changes are planned. **None are made in GL-223.**

### 17.1 New path groups

- `/workspaces/*` paths with schemas for:
  - `WorkspaceCreateRequest`
  - `WorkspaceResponse`
  - `WorkspaceMemberAddRequest`
  - `WorkspaceMemberResponse`
  - `WorkspaceOwnershipTransferRequest`

### 17.2 Modified components

- All resource response schemas (`GrantResponse`, `GrantRequestResponse`,
  `ExecutionResponse`, `AuditEventResponse`) must include a non-nullable
  `workspace_id` field after enforcement is live.
- `X-Workspace-ID` header must be documented as a required parameter on all
  workspace-aware endpoints.

### 17.3 Security scheme

- The `operatorToken` security scheme must be documented to require workspace
  membership verification in addition to operator authentication.

---

## 18. Testing Strategy

### 18.1 Unit tests required

- `test_workspace_create_assigns_server_id` — workspace_id is server-assigned.
- `test_workspace_create_client_id_rejected` — client-supplied workspace_id in
  body is ignored or rejected.
- `test_workspace_member_add` — adding a member creates membership record.
- `test_workspace_member_remove` — removing a member deactivates membership.
- `test_workspace_last_owner_cannot_leave` — last owner blocked from leaving.
- `test_cross_workspace_lookup_denied` — operator A cannot read workspace B
  resources.
- `test_cross_workspace_mutation_denied` — operator A cannot mutate workspace
  B resources.
- `test_workspace_deactivate_blocks_access` — deactivated workspace denies all
  member access.
- `test_null_workspace_id_rejected_in_production_mode` — null workspace on
  write is rejected in production-like modes.
- `test_workspace_audit_event_carries_workspace_id` — audit events after
  workspace enforcement carry non-null workspace_id.
- `test_workspace_context_derived_from_header` — X-Workspace-ID header is
  verified against membership before use.
- `test_workspace_context_client_body_override_denied` — body workspace_id
  ignored for context.
- `test_workspace_role_scope_composition` — effective permission is intersection
  of tenant and workspace roles.
- `test_workspace_ownership_transfer` — transfer updates owner_id and audits.
- `test_workspace_member_not_in_tenant_rejected` — operator from different
  tenant cannot be added as workspace member.

### 18.2 Integration tests required

- Full workspace lifecycle: create → add member → write grant → read grant →
  remove member → verify denied access.
- Cross-tenant workspace isolation: two tenants with same workspace name do
  not interfere.
- Audit event workspace propagation: all events in workspace have matching
  workspace_id.
- Backfill idempotency: running migration twice produces identical state.

### 18.3 Security regression tests required

- Cross-workspace resource address (URL manipulation with known ID from
  another workspace) returns 404.
- Body workspace_id injection does not change resource ownership.
- Token-derived workspace context cannot be overridden by request headers for
  tenant_id.

### 18.4 Gate tests required

A new `gl224_workspace_enforcement_gate.py` (or equivalent) gate must verify:
- All resource tables have non-null `workspace_id` in production-like mode.
- All audit events in a compliance window have non-null `workspace_id`.
- No cross-workspace reads pass the membership check.

---

## 19. Rollout Strategy

### 19.1 Phase 1 — Schema migration (no behavior change)

- Add `workspaces` and `workspace_members` tables.
- Backfill existing records with default workspace (`developer_preview` /
  `demo` modes only).
- No route behavior changes. `workspace_id` remains unused in routing logic.
- Full suite passes with no new failures.

### 19.2 Phase 2 — Workspace CRUD API

- Add workspace creation, listing, and membership management endpoints.
- Routes are guarded by tenant admin or workspace owner roles.
- No enforcement on existing resource routes yet.
- Demo/synthetic flows unaffected.

### 19.3 Phase 3 — Workspace context derivation

- Add `X-Workspace-ID` header support.
- Add `_get_workspace_context()` helper to `server.py`.
- Resource routes accept and propagate workspace context but do not yet
  filter (backwards-compatible mode).
- Tests verify context derivation without enforcement.

### 19.4 Phase 4 — Workspace enforcement

- Enable workspace filtering on all resource read routes.
- Enable workspace validation on all resource write routes.
- Null workspace in production-like modes is rejected.
- Full suite passes. Security regression tests pass. Gate script passes.

### 19.5 Phase 5 — Audit enforcement

- Require non-null `workspace_id` on all audit events in production-like mode.
- Audit chain updated to incorporate `workspace_id`.
- Compliance gate test passes.

---

## 20. Rollback Strategy

- Each phase is a separate commit/issue. Each phase can be reverted
  independently.
- Phase 1 (schema migration) rollback: drop new tables, nullify backfilled
  workspace_id values. Existing resource routes are unaffected.
- Phase 2 (CRUD API) rollback: remove workspace endpoint handlers. No data
  loss if workspaces table is preserved.
- Phase 3 (context derivation) rollback: remove `X-Workspace-ID` header
  processing. Routes revert to tenant-only context.
- Phase 4 (enforcement) rollback: remove workspace filters from resource
  queries. Revert to tenant-only filtering.
- Phase 5 (audit enforcement) rollback: revert audit writer to accept null
  workspace_id. Note: hash chain schema change requires coordinated rollback.

---

## 21. Compatibility with Demo / Synthetic Flows

- Demo and synthetic flows use `tenant_id = 'demo'` and `workspace_id = NULL`
  (currently).
- After Phase 1 backfill, demo records will have `workspace_id = 'default'`.
- Demo operator tokens will be assigned to the `default` workspace via
  membership backfill.
- All existing demo API smoke tests and quickstart flows must continue to
  pass through Phase 4 by targeting the `default` workspace.
- The `X-Workspace-ID: default` header will be required in demo mode after
  Phase 3 if the operator is only a member of one workspace (auto-selected).
- Existing `grant_lifecycle_evidence_bundle.py` example must be updated in
  the implementation phase to send `X-Workspace-ID` if required.

---

## 22. Production-Readiness Impact

GL-223 does not change the production-readiness posture. The following
decisions from GL-221 and GL-222 remain unchanged:

| Tier | Decision |
|---|---|
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

Implementing the plan in GL-224 through GL-228 (see section 25) is a
prerequisite for any future reassessment of the NO-GO posture for Production
SaaS or Real Customer Data.

---

## 23. Controlled-Preview Impact

GL-223 does not change the Controlled External Technical Review posture.
Review materials remain synthetic/demo only. The plan documented here does
not authorize any change to the review boundary or the content of review
materials.

---

## 24. Real-Data Impact

GL-223 does not enable real customer data, private grant data, or
institutional data. These tiers remain NO-GO. Implementing the workspace
enforcement plan (GL-224 through GL-228) and passing a subsequent production
go/no-go gate is the required path before any real-data tier can be
reconsidered.

---

## 25. Remaining Blockers Before Real Data

| Blocker ID | Description | Blocking Tier |
|---|---|---|
| RD-001 | workspace_id not enforced on any resource routes | Production SaaS, Real Customer Data |
| RD-002 | No workspaces or workspace_members tables | Production SaaS, Real Customer Data |
| RD-003 | No workspace membership verification in auth/route layer | Production SaaS, Real Customer Data |
| RD-004 | No workspace-scoped authorization | Production SaaS, Real Customer Data |
| RD-005 | Audit events carry workspace_id = null | Compliance Certification |
| RD-006 | No cross-workspace denial guards | Production SaaS, Real Customer Data |
| RD-007 | No workspace lifecycle (create/deactivate) API | Production SaaS |
| RD-008 | No production OAuth/OIDC/JWT identity provider | Production SaaS, Real Customer Data |
| RD-009 | No production PostgreSQL deployment | Live PostgreSQL Production Readiness |
| RD-010 | No GDPR/data-retention workspace erasure policy | Compliance Certification |

---

## 26. Proposed Implementation Issue Breakdown

| Issue | Title | Phase | Priority |
|---|---|---|---|
| GL-224 | Workspace Schema Migration and Entity Layer | Phase 1 | P0 |
| GL-225 | Workspace CRUD API and Admin Control Plane | Phase 2 | P0 |
| GL-226 | Workspace Context Derivation and Header Support | Phase 3 | P0 |
| GL-227 | Workspace Enforcement on Resource Routes | Phase 4 | P0 |
| GL-228 | Workspace Audit Event and Provenance Enforcement | Phase 5 | P1 |
| GL-229 | Workspace Security Regression Test Suite | Phase 4/5 | P0 |
| GL-230 | Workspace Enforcement Gate Script | Phase 4/5 | P0 |
| GL-231 | Production Go/No-Go v7 (post-workspace enforcement) | Post-Phase 5 | P1 |

### GL-224 — Workspace Schema Migration and Entity Layer

- Add `workspaces` and `workspace_members` DB tables via a new migration.
- Add entity classes (`Workspace`, `WorkspaceMember`) to `models.py`.
- Add DB helpers (`create_workspace`, `get_workspace`, `list_workspaces_for_operator`,
  `add_workspace_member`, `remove_workspace_member`).
- Add backfill logic for `developer_preview`/`demo` modes.
- Full suite must pass.
- No behavior change to existing routes.

### GL-225 — Workspace CRUD API and Admin Control Plane

- Add `/workspaces` and `/admin/workspaces` route handlers.
- Require tenant admin or owner role for workspace creation.
- Add membership add/remove/leave routes.
- Add ownership transfer route.
- Add audit events for workspace lifecycle.
- OpenAPI spec updated for new paths.

### GL-226 — Workspace Context Derivation and Header Support

- Add `_get_workspace_context()` to `server.py`.
- Add `X-Workspace-ID` header processing with membership verification.
- Update `check_auth()` to return `workspace_id` in payload.
- Backwards-compatible: null workspace context continues to function in
  `developer_preview`/`demo` modes.

### GL-227 — Workspace Enforcement on Resource Routes

- Update all resource read handlers to filter by `(tenant_id, workspace_id)`.
- Update all resource write handlers to assign `workspace_id` from context.
- Add null-workspace rejection in production-like modes.
- Full suite + security regression tests must pass.
- Gate script must pass.

### GL-228 — Workspace Audit Event and Provenance Enforcement

- Require non-null `workspace_id` on audit writes in production-like modes.
- Update audit hash chain to include `workspace_id` field.
- Require non-null `workspace_id` on provenance writes.
- Add compliance gate check for audit workspace coverage.

### GL-229 — Workspace Security Regression Test Suite

- Implement all tests from section 18.
- Cross-workspace lookup denial, mutation denial, context override prevention.
- Must all pass before GL-231 gate.

### GL-230 — Workspace Enforcement Gate Script

- `scripts/ops/gl230_workspace_enforcement_gate.py` (or equivalent).
- Verifies workspace tables exist, membership is enforced, null workspace
  blocked in production-like mode, audit events carry workspace_id.
- Dry-run / plan-only. No credentials. No network. No destructive ops.

### GL-231 — Production Go/No-Go v7 (post-workspace enforcement)

- Full production readiness gate after GL-224 through GL-230 are complete.
- Reassesses Production SaaS, Real Customer Data, and Live PostgreSQL tiers.
- Must not claim readiness before all P0 blockers from section 25 are resolved.

---

## 27. Risk Register

| Risk ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R-001 | Backfill corrupts existing demo data | Low | High | Idempotent backfill with transaction rollback; test in demo mode before schema merge |
| R-002 | Workspace enforcement breaks existing demo/quickstart flows | Medium | Medium | Backwards-compatible phase approach; demo mode auto-selects default workspace |
| R-003 | Audit hash chain incompatibility after workspace_id addition | Medium | High | Treat pre-enforcement chain as legacy; start new chain segment at enforcement boundary |
| R-004 | Cross-workspace 404 leaks timing side channel | Low | Medium | Constant-time membership check before query |
| R-005 | Workspace owner cannot leave — operational dead-end | Low | Medium | Ownership transfer flow required before leave; admin break-glass documented |
| R-006 | Workspace context header spoofing | Low | High | Membership verification gates all workspace context claims before trust |
| R-007 | Null workspace_id bypass in production | Medium | High | Null-workspace rejection gate in production-like mode; gate script verification |
| R-008 | Migration rollback complexity increases with phases | Medium | Medium | Each phase is independently reversible; rollback procedures documented per phase |

---

## 28. Decision

**GL-223 decision: APPROVED — plan accepted, implementation deferred to GL-224 through GL-231.**

The implementation plan is complete, internally consistent, and safe to
proceed. No production-readiness tier changes. No real data enabled. No
migrations added. No backend/src changes. The plan is the prerequisite for
all future workspace enforcement work.

---

## 29. Decision Rationale

- The current `workspace_id = NULL` posture is explicitly documented and
  tracked since GL-144 and GL-200A/B/C. GL-215 preserved it. GL-221 confirmed
  it as a remaining production blocker.
- A structured implementation plan is required before workspace enforcement
  can be safely implemented without risking audit integrity, tenant isolation
  regression, or demo-flow breakage.
- The phased approach (GL-224 through GL-231) minimizes blast radius at each
  step and ensures full test coverage before enforcement is activated.
- No production SaaS or real-data tiers are unlocked by the plan itself.
  A post-enforcement go/no-go gate (GL-231) is required.

---

## 30. Findings

| Finding ID | Finding |
|---|---|
| F-001 | workspace_id column exists on all resource tables but is null for all existing records |
| F-002 | No workspaces or workspace_members tables exist |
| F-003 | No workspace membership verification in any route handler |
| F-004 | All cross-tenant lookup denial is enforced; cross-workspace denial is not |
| F-005 | Audit events carry workspace_id = null throughout |
| F-006 | Operator model is tenant-aware but not workspace-aware |
| F-007 | Server-derived tenant_id model is sound and can be extended to workspace |
| F-008 | The phased rollout plan preserves all existing GL-214 through GL-222 boundaries |
| F-009 | Demo/synthetic flows are compatible with the planned default-workspace backfill |
| F-010 | The audit hash chain will require a defined break-point at workspace enforcement boundary |

---

## 31. Safety Confirmations

- GL-223 is a planning document. No migrations, schema, or API changes are
  included.
- GL-223 does not enable real customer data, private grant data, or
  institutional data.
- GL-223 does not claim Production SaaS readiness.
- GL-223 does not change public export, publish, visibility, GitHub workflows,
  or snapshot publish scripts.
- GL-223 does not weaken GL-214 through GL-222 boundaries.
- GL-223 does not include exploit details.
- GL-223 does not include real secrets.
- GL-223 does not include real customer or private data.
- Unrelated website-design/import files are excluded from GL-223.
- No backend/src changes are made.
- No dependencies are added.
- No package metadata is added.
- No deployment/cloud/Kubernetes/Terraform/Helm files are added.
- No TLS certificates or private keys are added.

---

## 32. Recommended Next Issues

| Issue | Title |
|---|---|
| GL-224 | Workspace Schema Migration and Entity Layer |
| GL-225 | Workspace CRUD API and Admin Control Plane |
| GL-226 | Workspace Context Derivation and Header Support |
| GL-227 | Workspace Enforcement on Resource Routes |
| GL-228 | Workspace Audit Event and Provenance Enforcement |
| GL-229 | Workspace Security Regression Test Suite |
| GL-230 | Workspace Enforcement Gate Script |
| GL-231 | Production Go/No-Go v7 (post-workspace enforcement) |
