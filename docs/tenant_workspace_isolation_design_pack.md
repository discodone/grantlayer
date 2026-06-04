# GL-200A Tenant/Workspace Isolation Design Pack

## Issue ID

GL-200A

## Title

Tenant/Workspace Isolation Design Pack

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture.

GL-199 (Production Readiness Gap Report v2) concluded:

- Developer Preview may continue.
- Controlled Preview may continue only with strict boundaries.
- Production SaaS is not ready.
- Real customer data is no-go.
- Private grant/institutional data is no-go.

GL-199 identified **GL-200 — Tenant/Workspace Isolation** as the
highest-priority production blocker (P0). This issue (GL-200A) is the
**design pack only**. It does not implement tenant/workspace isolation.
It defines architecture, scope, risks, migration strategy, and the
implementation plan for GL-200B and later issues.

---

## Scope

This issue is **design / docs / test / artifact only.**

This issue does **not**:
- implement tenant/workspace isolation
- modify `backend/src/*`
- modify runtime API behavior
- modify `docs/openapi.yaml`, migrations, DB/schema
- modify dependency manifests
- create SDK implementation or publish packages
- modify examples runtime behavior
- modify frontend, website, or design
- change GitHub workflows or snapshot publish script behavior
- push to GitHub
- change GitHub visibility

Allowed files created in this issue:
- `docs/tenant_workspace_isolation_design_pack.md` (this file)
- `docs/examples/gl200a/tenant_workspace_isolation_design_pack.json`
- `backend/tests/test_gl200a_tenant_workspace_isolation_design_pack.py`

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| README.md | yes |
| SECURITY.md | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes |
| docs/production_readiness_gap_report_v2.md | yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | yes |
| docs/controlled_preview_boundary_pack.md | yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | yes |
| docs/api_sdk_agent_value_decision_pack.md | yes |
| docs/examples/gl197/api_sdk_agent_value_decision_pack.json | yes |
| docs/public_safety_scanner_claim_consistency_gate.md | yes |
| docs/public_smoke_matrix_pack.md | yes |
| docs/tenant_workspace_boundary_decision.md (GL-132) | yes |
| docs/tenant_workspace_data_model_design.md (GL-144) | yes |
| docs/production_auth_operator_access_design.md | yes |
| docs/production_hardening_roadmap.md | yes |
| backend/src/server.py | yes (routes, auth guards) |
| backend/src/auth.py | yes |
| backend/src/grants.py | yes |
| backend/src/grant_requests.py | yes |
| backend/src/challenges.py | yes |
| backend/src/audit_log.py | yes |
| backend/src/db.py | yes |
| backend/src/agent_permissions.py | yes |
| backend/src/agent_permission_assignments.py | yes |
| backend/src/models.py | yes |
| backend/src/migrations/0001_gl032_baseline.py | yes |
| backend/src/migrations/0005_gl102_audit_log_immutability.py | yes |
| backend/src/migrations/0006_gl103_audit_hash_chain.py | yes |
| backend/src/migrations/0007_gl107_operator_token_lookup.py | yes |
| backend/tests/test_security_boundary_regression.py | yes |
| backend/tests/test_gl199_production_readiness_gap_report_v2.py | yes |
| backend/tests/test_gl198_controlled_preview_boundary_pack.py | yes |

---

## Current State Summary

GrantLayer has **no production tenant/workspace isolation implemented.**

The following posture statements describe the current system:

- All grants, grant requests, grant executions, challenges, evidence
  archives, provenance events, and audit events share a **single
  namespace** within any given deployment.
- There is no `tenant_id`, `workspace_id`, or any tenant/workspace
  entity in the data model, schema, or API.
- The only boundary today is the **operator-bounded workspace model**
  from GL-132 Option B: all data implicitly belongs to the named
  operator who controls the deployment.
- Auth provides admin-token mode (dev/demo) and operator-token mode
  (hardened). Neither mode carries tenant/workspace context.
- Agent permission scopes are globally-scoped within a deployment;
  no per-tenant or per-workspace scope enforcement exists.
- Audit events carry no tenant/workspace identifier.
- The demo endpoint and health/readiness endpoints are public and
  intentionally unauthenticated; they are not customer-scoped.

This state is acceptable for Developer Preview and Controlled Preview
under strict boundaries (GL-198). It is **not** acceptable for
Production SaaS with unrelated customers on shared infrastructure.

---

## Terminology

### Tenant

A **tenant** is the top-level logical isolation boundary in GrantLayer.
It isolates one customer's or institution's data — grants, grant requests,
grant executions, evidence, audit records, and operator identities — from
all other customers. Each production deployment serving multiple customers
must enforce tenant boundaries at the data, auth, and API layers.

A tenant maps to: a university, a foundation, a corporation, or any other
institution that controls a bounded set of grants and operators.

### Workspace

A **workspace** is a scoped operating context within a tenant. It maps
to a team, department, program office, or organizational unit inside the
tenant that shares grants and evidence but remains isolated from other
workspaces within the same tenant.

A workspace is optional in the minimum viable implementation. The
production baseline (GL-200B) must support `tenant_id` at minimum;
`workspace_id` may be staged.

### Actor

An **actor** is any entity — human operator, automated agent, or admin —
that performs an action tracked by GrantLayer. Actors must be bound to a
tenant at minimum; workspaces are optional in the GL-200B baseline.

### Operator

An **operator** is an authenticated individual or service identity that
performs actions within a tenant/workspace. Operators carry a role
(`owner`, `grant_admin`, `grant_reviewer`, `readonly`, `auditor`) that
constrains their permitted actions within their tenant/workspace boundary.

### Admin

An **admin** is an operator with elevated privileges (`owner` or
`grant_admin`) who can manage tenant configuration, membership, and
boundary policies. System-level admin actions (cross-tenant by design)
must be explicitly marked and restricted.

### Agent

An **agent** is an automated software entity (e.g., a LangChain agent,
a Claude-powered AI) that performs grant workflow actions on behalf of an
operator. Agents inherit their owner's tenant/workspace context via
agent permission assignments. They carry scopes such as
`evidence:read`, `grant_request:read`, etc.

### Grant

A **grant** is a time-bounded authorization record permitting a subject to
perform a specific action on a specific resource. In a tenant-aware model,
every grant must carry a `tenant_id` and optionally a `workspace_id`.
Cross-tenant grant access must be impossible.

### Grant Request

A **grant request** is a structured request for a grant submitted by an
operator and subject to approval workflow. Grant requests must be scoped
to the same tenant/workspace as the operator who submitted them.

### Challenge

A **challenge** is a cryptographic proof-of-intent token created during
grant execution. Challenges must be scoped to the same tenant/workspace
as the actor and grant they are associated with.

### Execution

A **grant execution** is a record of a protected action attempt —
authorized, denied, or pending. Executions must carry the same
tenant/workspace context as the grant that produced them.

### Evidence

**Evidence** is the collection of artifacts — files, verification records,
attestations — that document the outcome of a grant execution. Evidence
must be scoped to the same workspace (and tenant) as the execution.

### Audit Event

An **audit event** is an immutable, hash-chained record of every
authorization decision. Audit events must carry tenant/workspace context.
System-level events (e.g., migrations, health checks) are explicitly
marked as `scope: system`.

---

## Threat Model

The following threat scenarios motivate the isolation design:

| Threat | Vector | Current Risk | Required Mitigation |
|--------|--------|-------------|---------------------|
| Cross-tenant data read | Operator A queries grant list; no tenant filter | Critical — all grants visible | `tenant_id` filter on all queries |
| Cross-tenant data write | Operator A creates grant for tenant B's resources | Critical — no constraint | `tenant_id` enforcement on create |
| Tenant impersonation via token | Attacker with valid operator token accesses other tenant | Critical — token carries no tenant claim | Bind operator token to `tenant_id` at creation |
| Workspace boundary leak | Workspace A user reads workspace B grants | High — no workspace filter | `workspace_id` filter where applicable |
| Audit event leakage | Auditor reads another tenant's audit trail | Critical — single audit log | `tenant_id` on audit events + filtered queries |
| Agent over-privilege | Agent with `grant:read` scope reads all tenants | Critical — scope is global | Agent permissions must be tenant-scoped |
| Admin cross-tenant access | System admin reads any tenant's data | Acceptable only if explicitly marked | Explicit `is_system_admin` flag, logged |
| Demo endpoint data leak | Demo endpoint reveals real tenant data | High if real data exists | Demo endpoint serves only synthetic data (GL-190) |
| Migration data cross-contamination | Backfill assigns wrong `tenant_id` | High — data integrity | Idempotent migration with explicit tenant assignment |

---

## Isolation Goals

1. Every business resource (grant, grant request, grant execution, challenge,
   evidence, audit event, agent permission assignment) must carry an explicit
   `tenant_id` in the database schema.
2. Every API query or mutation involving business resources must filter by the
   requesting actor's `tenant_id`; cross-tenant access must be denied.
3. Operators must be bound to a `tenant_id` at creation; operator tokens must
   carry tenant context in the auth layer.
4. Agent permission scopes must be scoped to the operator's tenant context.
5. Audit events must record tenant context; the audit chain must be
   tenant-aware.
6. Demo, health, and readiness endpoints are public by design and remain
   outside tenant scope.
7. System/admin operations that require cross-tenant access must be explicitly
   marked, logged, and restricted to named admin roles.
8. The design must support both SQLite (dev/test) and PostgreSQL (production)
   backends.

---

## Isolation Non-Goals

The following are **not** required by GL-200B:

- Full RBAC/policy engine (deferred to GL-200D or later)
- Per-workspace row-level security at the DB layer (deferred)
- Billing/subscription tenant model (not in scope)
- Frontend tenant onboarding UI (not in scope)
- Customer-facing tenant admin panel (not in scope)
- Multi-region tenant isolation (not in scope)
- Federated identity / SSO per tenant (not in scope)
- Tenant-level rate limiting (not in scope for GL-200B)
- Workspace sub-isolation as a hard requirement in the GL-200B baseline
  (workspace support is additive; baseline requires `tenant_id`)

---

## Resource Scoping Matrix

| Resource | Current Scope Status | Required Future Scope | Production Risk | Recommended GL-200B Action |
|----------|---------------------|-----------------------|-----------------|---------------------------|
| grants | global (unscoped) | tenant (+ optional workspace) | Critical | Add `tenant_id` column; filter all queries |
| grant_requests | global (unscoped) | tenant (+ optional workspace) | Critical | Add `tenant_id` column; filter all queries |
| challenges | global (unscoped) | tenant (+ optional workspace) | Critical | Add `tenant_id` column; filter queries |
| grant_executions | global (unscoped) | tenant (+ optional workspace) | Critical | Add `tenant_id` column; filter queries |
| evidence/executions | global (unscoped) | tenant (+ optional workspace) | Critical | Add `tenant_id` column; filter queries |
| audit_events | global (unscoped) | tenant (explicit system scope for system events) | Critical | Add `tenant_id` column; system events get `scope: system` |
| operators | global (unscoped) | tenant | Critical | Add `tenant_id` column; operator bound to tenant at creation |
| operator tokens / token_hash | implicitly scoped via operator | tenant (via operator) | Critical | Ensure operator lookup enforces tenant context |
| agent_permissions (profiles) | global (unscoped) | tenant | High | Add `tenant_id` to assignments; profiles may remain global templates |
| agent_permission_assignments | global (unscoped) | tenant | High | Add `tenant_id` column; enforce tenant context |
| demo endpoints (`/demo/*`) | global_public (intentional) | global_public (no change) | Low | Document synthetic-data-only; maintain GL-190 guard |
| health endpoint (`/health`) | global_public (intentional) | global_public (no change) | None | No change required |
| readiness endpoint (`/readiness`) | global_public (intentional) | global_public (no change) | None | No change required |
| configuration / env vars | system_internal | system_internal | Medium | No tenant-scoping needed; per-deployment config sufficient |
| migrations | system_internal | system_internal | Medium | Migrations must add tenant columns safely; backfill strategy required |

---

## Design Options

### Option A — `tenant_id` Only Baseline

**Description:** Add a `tenant_id` column to all business resource tables.
All API queries filter by the requesting operator's `tenant_id`. No
workspace sub-boundary. Operator tokens are bound to a `tenant_id` at
creation. Auth layer reads `tenant_id` from the authenticated operator
and injects it into all DB queries.

**Benefits:**
- Minimal schema change (one new column per table).
- Straightforward migration with backfill.
- Fail-closed by design: missing `tenant_id` on an operator → deny.
- Compatible with both SQLite and PostgreSQL.
- Unblocks production readiness assessment quickly.

**Risks:**
- No workspace sub-isolation; all operators in a tenant share access.
- Workspace isolation deferred — must not be claimed as implemented.
- Tenant creation/management API not included; tenants are pre-provisioned.

**Implementation Complexity:** Low.
**Migration Cost:** Medium (backfill existing data to a `dev/demo` tenant).
**Test Burden:** Medium (cross-tenant denial tests, audit context tests).
**Suitability for GL-200B:** High — recommended as the baseline.

---

### Option B — `tenant_id` + `workspace_id` on All Business Resources

**Description:** Add both `tenant_id` and `workspace_id` to all business
resource tables. Operators are bound to both a tenant and a workspace at
creation. All API queries filter by both. Workspace membership is explicit.

**Benefits:**
- Full two-level isolation from the start.
- Workspace-level export, audit, and evidence boundaries.
- No technical debt when workspace isolation is eventually required.

**Risks:**
- Significantly higher implementation complexity than Option A.
- Every query, model, and API endpoint must carry workspace context.
- Workspace creation/management API required upfront.
- Migration complexity doubles (two columns, two backfill dimensions).
- Risk of shipping a partially-correct implementation under time pressure.

**Implementation Complexity:** High.
**Migration Cost:** High.
**Test Burden:** High.
**Suitability for GL-200B:** Medium — recommended only if workspace
isolation is required before controlled preview moves to production.

---

### Option C — Request-Context Isolation Layer with Staged DB Migration

**Description:** Add a middleware/request-context layer that extracts and
validates tenant context from the auth token on every request. DB schema
changes (adding `tenant_id`) are staged in a separate migration.
The isolation is enforced at the query layer via a context object passed
through all resource functions, rather than by changing every call site.

**Benefits:**
- Decouples schema migration from enforcement rollout.
- Context object is a clean seam for future workspace support.
- Enables incremental rollout: enforce at API layer first, then migrate schema.

**Risks:**
- Two-phase rollout creates a window where schema is migrated but
  enforcement is incomplete (or vice versa).
- Context object must be threaded through every resource function —
  high refactor surface area.
- Higher risk of incomplete enforcement if staging is not carefully managed.

**Implementation Complexity:** High (context threading).
**Migration Cost:** Medium (same columns as Option A).
**Test Burden:** High (must verify enforcement in both phases).
**Suitability for GL-200B:** Medium — valuable pattern but adds complexity.

---

### Option D — Full RBAC / Tenant / Workspace Policy Engine

**Description:** Implement a complete policy engine with tenant, workspace,
role, and resource-level access control. Operators, agents, and admins
are assigned policies. The policy engine evaluates every access decision
against the policy store.

**Benefits:**
- Maximum flexibility and granularity.
- Future-proof for complex institutional permission hierarchies.
- Enables attribute-based access control (ABAC) patterns.

**Risks:**
- Very high implementation complexity — likely 4–8× more work than Option A.
- Policy store becomes a critical dependency; misconfiguration = data breach.
- Cannot be completed in GL-200B scope; would require multiple issues.
- Premature for current scale; over-engineering risk is high.

**Implementation Complexity:** Very High.
**Migration Cost:** Very High.
**Test Burden:** Very High.
**Suitability for GL-200B:** Low — deferred to GL-200D or later.

---

## Selected Recommended Design

**Recommendation:** Option A baseline with staged Option B readiness.

**GL-200B should implement Option A:** `tenant_id` on all business
resource tables, operator tokens bound to `tenant_id`, API queries
filtered by `tenant_id`, audit events include `tenant_id`, and fail-closed
behavior on missing/ambiguous tenant context.

**Option B (`workspace_id`) is staged:** Schema design should
reserve a `workspace_id` column in the migration (nullable, defaulting
to `NULL`) so workspace support can be added in GL-200C without a
further disruptive schema change. `workspace_id` enforcement is
**not** required in GL-200B.

**Rationale:**
- Unblocks production readiness fastest.
- Minimal schema change with clear migration path.
- Fail-closed by design.
- Leaves clean seam for workspace support in GL-200C.
- Does not over-engineer before scale requires it.

---

## API Boundary Model

### How Tenant Context Enters Requests

Tenant context must enter every API request through the authenticated
operator identity. The recommended approach:

1. **Operator token carries `tenant_id` implicitly** — the operator record
   in the database carries `tenant_id`. When an operator authenticates,
   the auth layer loads their tenant context from the operator record.
2. **No tenant header required from clients** — clients do not send
   a `X-Tenant-ID` header. The tenant is resolved server-side from the
   authenticated operator.
3. **Admin/system actions** — system-level admin operations that require
   cross-tenant access must use an explicit `is_system_admin` flag on the
   operator record and must be separately logged.

### Fail-Closed Behavior

- If the authenticated operator has no `tenant_id` in their record →
  deny the request with `403 tenant_context_missing`.
- If the request is for a resource that belongs to a different tenant →
  deny with `404` (not `403`) to avoid leaking tenant existence.
- If tenant context is ambiguous (e.g., multiple tenants for one operator)
  → deny and require explicit clarification.

### Cross-Tenant Access Denial

- No cross-tenant read, write, or mutation is permitted.
- Cross-tenant denial events must be auditable: write an audit event
  with `approved: false`, `reason: cross_tenant_access_denied`.
- Return `404` (not `403`) on resource-not-found in tenant scope to
  prevent tenant enumeration.

### Admin / System Exceptions

- System admin access (cross-tenant) requires:
  - Operator role `owner` with explicit `is_system_admin: true`.
  - All cross-tenant accesses logged with `scope: system_admin`.
  - No cross-tenant write without explicit intent flag.
- Health (`/health`) and readiness (`/readiness`) endpoints remain public
  by design. They carry no tenant context. They must not return
  tenant-scoped data.

### Demo Endpoint Exceptions

- `/demo/*` endpoints remain intentionally public and unauthenticated
  (GL-190 safety guard maintained).
- Demo endpoints must only ever operate on synthetic/test data.
- Demo endpoints must never be routed to tenant-scoped resources.

### Error Response Safety

- Error responses must never include: raw `tenant_id` values from other
  tenants, resource IDs from other tenants, operator tokens, or secrets.
- Generic error messages must be used for cross-tenant denial.

---

## Auth / Operator / Admin Context Model

### Current State

- Admin token mode: `GRANTLAYER_ADMIN_TOKEN` env var; no tenant context.
- Operator token mode: operator record has `id`, `name`, `role`,
  `token_hash`, `expires_at`; no `tenant_id`.
- Agent permission scopes: globally-scoped within deployment.

### Required Changes for GL-200B

1. **Operator table gains `tenant_id`** — a non-null column binding each
   operator to exactly one tenant.
2. **Operator auth returns tenant context** — `authenticate_operator()`
   returns the operator's `tenant_id` alongside their role.
3. **Admin token mode** — in GL-200B, admin token mode remains a dev/demo
   fallback. When used, it should be bound to a single `dev` tenant context.
   Admin token mode must not be used in production multi-tenant deployments.
4. **Agent permission assignments gain `tenant_id`** — assignments are
   scoped to the operator's tenant. Agents may not access resources outside
   the operator's tenant.

### Minimum GL-200B Enforcement

- `authenticate_operator()` → resolves `tenant_id` from operator record.
- Auth guard injects `tenant_id` into request context.
- All business resource queries include `WHERE tenant_id = ?` clause.
- Operator creation requires `tenant_id` parameter.

### What Should Remain Deferred

- OAuth 2.0 / JWT / SSO per tenant — deferred to production auth issue.
- Workspace-level operator membership — deferred to GL-200C.
- Per-tenant rate limits — deferred.
- Tenant provisioning API — deferred (tenants are pre-provisioned in GL-200B).

---

## Database / Data Model Strategy

### Columns Required (GL-200B Scope)

For each business resource table (`grants`, `grant_requests`,
`grant_executions`, `challenges`, `audit_events`, `operators`,
`agent_permission_assignments`):

```sql
tenant_id TEXT NOT NULL DEFAULT 'unassigned',
workspace_id TEXT DEFAULT NULL
```

`tenant_id` is non-null (defaulting to `unassigned` during migration backfill,
then updated). `workspace_id` is nullable (reserved for GL-200C).

### Backfill Strategy

Existing demo/dev data in any deployment must be backfilled to a single
`dev/demo` tenant:

```
tenant_id = 'demo'  -- for existing dev/demo rows
```

The migration must:
1. Add `tenant_id TEXT DEFAULT 'unassigned'` to each table.
2. `UPDATE <table> SET tenant_id = 'demo' WHERE tenant_id = 'unassigned'`
3. Add `workspace_id TEXT DEFAULT NULL` to each table (reserved for GL-200C).
4. Add index: `CREATE INDEX idx_<table>_tenant_id ON <table>(tenant_id)`.

Migration must be idempotent: re-running must not fail if columns already exist.

### Migration Safety

- Migrations use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (PostgreSQL)
  or `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` pattern (SQLite does not
  support `IF NOT EXISTS` on ALTER; must check column existence first).
- No data is deleted during migration.
- No uniqueness constraints on `tenant_id` alone (composites with ID remain).
- Rollback: remove columns added. No row data is destructive to remove.
- The `audit_events` table gains `tenant_id` but the hash-chain computation
  must be updated to include `tenant_id` in the canonical payload to preserve
  chain integrity post-migration.

### SQLite / PostgreSQL Implications

- SQLite: `ALTER TABLE ADD COLUMN` supported without `IF NOT EXISTS`; must
  check `PRAGMA table_info()` first or use `CREATE TABLE ... AS SELECT`.
- PostgreSQL: `ALTER TABLE ADD COLUMN IF NOT EXISTS` is supported (v9.6+).
- Both backends must produce identical query behaviour via the existing
  `_translate_placeholders` layer in `db.py`.

### Indexes / Constraints

- Add `INDEX idx_grants_tenant_id ON grants(tenant_id)`.
- Add composite `INDEX idx_grants_tenant_subject ON grants(tenant_id, subject_id)`.
- Similar indexes for each scoped table.
- No new UNIQUE constraints needed in GL-200B (IDs remain globally unique UUIDs).

### Audit Immutability Considerations

- The hash-chain in `audit_events` covers a canonical JSON payload. Adding
  `tenant_id` to the payload breaks the existing chain unless handled carefully.
- **Recommended:** New events written after the migration include `tenant_id`
  in the canonical hash payload. Historical events (written before migration)
  retain their original `row_hash` values; a migration-time marker event
  (`scope: tenant_migration_applied`) is appended to the chain to signal the
  boundary.
- Chain verification must handle mixed chains (pre-migration events without
  `tenant_id` in hash, post-migration events with `tenant_id`).

### Rollback / Compatibility

- Rollback of a `tenant_id` migration is low-risk (column drop) as long as
  no non-demo data has been written under tenant context.
- Pre-migration clients (tools, examples) that do not send tenant context
  continue to work via the admin-token / operator-token path (which resolves
  tenant context server-side from the operator record).
- No API-visible breaking change is required for GL-200B if tenant context
  is injected server-side from the operator record.

---

## Audit Design

### Tenant/Workspace Context in Audit Events

Every audit event written after GL-200B implementation must include:

- `tenant_id`: the tenant context of the action.
- `workspace_id`: the workspace context (nullable in GL-200B; required in
  GL-200C if workspace isolation is implemented).
- `scope`: one of `tenant`, `tenant_admin`, `system`, `system_admin`,
  `public` (for unauthenticated endpoints).

System-level events (migration completion, health probes) use
`scope: system`, `tenant_id: NULL`.

### Cross-Tenant Access Denial Audit Events

Every cross-tenant access denial must produce an audit event:

```json
{
  "action": "cross_tenant_access_denied",
  "approved": false,
  "reason": "cross_tenant_access_denied",
  "tenant_id": "<requesting_operator_tenant_id>",
  "scope": "tenant"
}
```

### Immutable Audit Behavior

- Audit events must remain append-only and tamper-evident after GL-200B.
- The hash-chain mechanism is preserved. The migration boundary marker
  event handles the transition.
- `tenant_id` is included in the canonical hash payload for post-migration
  events.

### No Sensitive Data in Audit

- Raw token values must never appear in audit events.
- Raw grant payloads must not be embedded; use `matched_grant_id`.
- No PII (operator names, email addresses) beyond what is already logged.

---

## Permission Model Implications

### Agent Permission Scopes

Current scopes (`evidence:read`, `grant_request:read`, etc.) are
globally-scoped within a deployment. After GL-200B:

- Agent permission assignments carry the operator's `tenant_id`.
- Scope evaluation (`agent_permissions.py`) must receive tenant context
  and verify that the requested resource belongs to the same tenant as
  the assignment.
- The scope vocabulary itself (e.g., `evidence:read`) does not change.
- Wildcard scopes (`*:*`) remain valid but are tenant-bounded.

### Operator Role Model

Operator roles (`owner`, `grant_admin`, `grant_reviewer`, `readonly`,
`auditor`) remain unchanged. Roles are enforced within the tenant context.
Cross-tenant role elevation is forbidden.

### Admin Token Mode (Dev/Demo Only)

In GL-200B, admin token mode may remain as a dev/demo fallback bound to
a single `dev` tenant. It must not be used in production multi-tenant
deployments. Admin token mode must be clearly documented as not
production-safe.

---

## Testing Strategy

The following tests are required before any tenant-isolation claim:

### Cross-Tenant Isolation Tests

| Test ID | Description |
|---------|-------------|
| T-001 | Operator A (tenant_1) cannot read grants belonging to tenant_2 |
| T-002 | Operator A (tenant_1) cannot write grants to tenant_2 |
| T-003 | Operator A (tenant_1) cannot read audit events from tenant_2 |
| T-004 | Operator A (tenant_1) cannot read evidence from tenant_2 |
| T-005 | Operator A (tenant_1) cannot read grant requests from tenant_2 |
| T-006 | Cross-tenant access denial is auditable (audit event written) |
| T-007 | Cross-tenant denial returns `404` (not `403`) for resource endpoints |

### Workspace Isolation Tests (GL-200C)

| Test ID | Description |
|---------|-------------|
| W-001 | Workspace A operator cannot read grants from workspace B within same tenant |
| W-002 | Workspace A operator cannot write grants to workspace B |
| W-003 | Cross-workspace denial is auditable |

### Auth Context Tests

| Test ID | Description |
|---------|-------------|
| A-001 | Missing operator token → `401` (unchanged) |
| A-002 | Invalid operator token → `401` (unchanged) |
| A-003 | Operator with no `tenant_id` → `403 tenant_context_missing` |
| A-004 | Admin token mode resolves to `dev` tenant context |

### Audit Context Tests

| Test ID | Description |
|---------|-------------|
| AU-001 | Post-migration audit events include `tenant_id` |
| AU-002 | System-level events carry `scope: system` |
| AU-003 | Cross-tenant denial events are written to audit log |
| AU-004 | Audit chain verification handles pre/post-migration events |

### Demo Endpoint Safety Tests

| Test ID | Description |
|---------|-------------|
| D-001 | `/demo/*` endpoints remain accessible without auth (GL-190 guard) |
| D-002 | `/demo/*` endpoints serve only synthetic data |
| D-003 | `/demo/*` endpoints do not expose tenant-scoped data |

### Health / Readiness Tests

| Test ID | Description |
|---------|-------------|
| H-001 | `/health` returns `200` without auth (unchanged) |
| H-002 | `/readiness` returns `200` without auth (unchanged) |
| H-003 | Health/readiness responses contain no tenant-scoped data |

### Migration Tests

| Test ID | Description |
|---------|-------------|
| M-001 | Migration adds `tenant_id` to all business resource tables |
| M-002 | Migration backfill sets existing rows to `tenant_id = 'demo'` |
| M-003 | Migration is idempotent (re-run does not fail) |
| M-004 | Existing test fixtures continue to pass post-migration |

### Examples / Determinism Tests

| Test ID | Description |
|---------|-------------|
| E-001 | `examples/grant_lifecycle_evidence_bundle.py` output matches fixture |
| E-002 | `scripts/verify-first-output.sh` passes |
| E-003 | Public examples remain deterministic after implementation |

### Security Boundary Regression Tests

| Test ID | Description |
|---------|-------------|
| S-001 | Anonymous access remains denied where expected |
| S-002 | No raw token/secret leakage in any API response |
| S-003 | Security boundary regression suite passes with no new failures |

---

## Rollout Plan

### Phase 1 — GL-200B: Tenant Isolation Baseline

1. Add `tenant_id` (non-null, backfilled) and `workspace_id` (nullable,
   reserved) columns to all business resource tables via new migration.
2. Update `operators` table: add `tenant_id` column.
3. Update `authenticate_operator()` to return `tenant_id`.
4. Inject tenant context into all business resource queries.
5. Add fail-closed guard: missing `tenant_id` → `403`.
6. Update audit event writer to include `tenant_id`.
7. Update hash-chain canonical payload to include `tenant_id` for
   post-migration events.
8. Write and pass all T-xxx, A-xxx, AU-xxx, M-xxx tests.
9. Update docs: remove "tenant isolation not implemented" only when
   GL-200B is merged and verified.

### Phase 2 — GL-200C: Workspace Isolation Baseline (future)

1. Activate `workspace_id` enforcement on all business resources.
2. Add workspace membership model.
3. Write and pass all W-xxx tests.

### Phase 3 — GL-200D: Policy Engine (future)

1. Implement full RBAC / tenant / workspace policy engine.
2. Replace per-query tenant filter with policy evaluation layer.

### Phase 4 — GL-201: API Contract Update (future)

1. Update `docs/openapi.yaml` to reflect tenant context in API contract.

### Phase 5 — GL-202: Audit Propagation Hardening (future)

1. Harden audit event tenant context; add `workspace_id` to audit.
2. Verify chain integrity across migrations.

### Phase 6 — GL-203: Isolation Regression / Smoke Matrix (future)

1. Add cross-tenant and workspace isolation to public smoke matrix.
2. Verify all T-xxx, W-xxx, AU-xxx tests in CI.

---

## Compatibility Strategy

- **No breaking API change in GL-200B** — tenant context is resolved
  server-side from the operator record; clients do not need to change.
- **Existing examples remain deterministic** — examples use a single
  operator/tenant (demo); no change needed.
- **Existing test fixtures continue to work** — test DB is initialized
  fresh per test; migration runs as part of `init_db()`; all existing
  tests remain valid.
- **SQLite and PostgreSQL parity** — migration must work on both.
- **Admin token dev/demo mode** — remains available as a single-tenant
  fallback for development; must not be used in multi-tenant production.

---

## Production Readiness Criteria

The following must be true before any tenant isolation claim is made
in public documentation or any production SaaS claim is made:

1. **DB schema scoped** — `tenant_id` column exists on all business
   resource tables in production schema.
2. **Request context enforced** — every API request that accesses
   business resources reads and enforces the operator's `tenant_id`.
3. **All sensitive resources scoped** — grants, grant_requests, challenges,
   grant_executions, evidence/executions, audit_events, operators,
   agent_permission_assignments all have `tenant_id` enforced.
4. **Cross-tenant tests pass** — all T-xxx tests pass in CI.
5. **Audit context propagated** — all AU-xxx tests pass; audit events
   include `tenant_id`.
6. **Migration verified** — all M-xxx tests pass; migration is idempotent.
7. **Examples deterministic** — all E-xxx tests pass.
8. **Security boundary regression passes** — all S-xxx tests pass with
   no new failures.
9. **Public docs updated** — `docs/production_readiness_gap_report_v2.md`
   and all public claims about tenant isolation are updated **only after**
   GL-200B is merged and verified, not before.
10. **Security review complete** — any security-sensitive findings
    identified during implementation are routed to GitHub Security
    Advisories before public disclosure.

---

## Implementation Split

### GL-200B — Tenant/Workspace Isolation Implementation Baseline

**Scope:** Implement `tenant_id` on all business resource tables, operator
binding, auth context injection, query filtering, and audit context.
Write all T-xxx, A-xxx, AU-xxx, M-xxx tests.

**Deliverables:**
- New DB migration adding `tenant_id`, `workspace_id` (nullable) to all tables
- Updated `operators` table with `tenant_id`
- Updated `authenticate_operator()` returning tenant context
- Updated resource query functions with `tenant_id` filter
- Updated audit event writer with `tenant_id`
- Updated hash-chain canonical payload
- Full test suite for isolation

### GL-200C — Workspace Isolation Baseline (future)

**Scope:** Activate `workspace_id` enforcement; add workspace membership
model; write W-xxx tests.

### GL-200D — Policy Engine (future)

**Scope:** Implement full RBAC/policy engine replacing per-query tenant filter.

### GL-201 — Tenant/Workspace Isolation API Contract Update (future)

**Scope:** Update `docs/openapi.yaml` to reflect tenant context.

### GL-202 — Tenant/Workspace Isolation Audit Propagation (future)

**Scope:** Harden audit chain tenant context; add `workspace_id` to audit
canonical payload; verify chain integrity across migrations.

### GL-203 — Tenant/Workspace Isolation Regression / Smoke Matrix (future)

**Scope:** Add cross-tenant and workspace isolation to CI smoke matrix.

---

## Risk Register

| Risk ID | Risk | Probability | Impact | Mitigation |
|---------|------|-------------|--------|------------|
| R-001 | Hash-chain breaks after migration | Medium | High | Migration boundary marker event; dual-mode chain verification |
| R-002 | Incomplete backfill leaves unassigned rows | Medium | Critical | Backfill migration + verification step |
| R-003 | Existing tests break due to missing `tenant_id` in fixtures | Medium | Medium | Update test fixtures to supply tenant context |
| R-004 | Demo endpoint accidentally exposed to tenant scope | Low | High | GL-190 guard maintained; demo route does not use tenant-filtered queries |
| R-005 | Admin token mode bypasses tenant enforcement | Medium | Critical | Admin token mode binds to `dev` tenant; blocked in production |
| R-006 | SQLite `ALTER TABLE` dialect mismatch | Medium | Medium | Check `PRAGMA table_info` before alter; test on both backends |
| R-007 | Cross-tenant 404 vs 403 confusion in error handling | Low | Medium | Standardize: resource-not-in-tenant → 404 |
| R-008 | Agent permission assignments not tenant-scoped correctly | Medium | High | Add tenant context to all assignment queries |
| R-009 | Workspace column added but accidentally enforced too early | Low | Medium | `workspace_id` nullable; no enforcement in GL-200B |
| R-010 | Public docs claim tenant isolation before implementation is verified | Low | Critical | Docs update gated on GL-200B merge + test pass |

---

## Findings

### GL-200A-F001

- **id:** GL-200A-F001
- **severity:** critical
- **category:** tenant-isolation
- **summary:** No `tenant_id` column exists on any business resource table.
- **evidence:** `backend/src/migrations/0001_gl032_baseline.py`: `grants`,
  `grant_requests`, `grant_executions`, `challenges`, `audit_events`,
  `operators` tables have no `tenant_id` column. Confirmed by grep:
  zero occurrences of `tenant_id` in `backend/src/`.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes
- **blocking_for_production:** yes
- **recommended_action:** Add `tenant_id` column to all business resource
  tables in a new GL-200B migration. Backfill existing data to `demo` tenant.
- **recommended_issue:** GL-200B

---

### GL-200A-F002

- **id:** GL-200A-F002
- **severity:** critical
- **category:** auth-context
- **summary:** Operator token carries no `tenant_id`; auth layer returns no
  tenant context.
- **evidence:** `backend/src/auth.py`: `check_auth()` returns `operator`
  dict with no `tenant_id` field. `backend/src/operators.py`: operator
  model has no `tenant_id` column. Auth context cannot enforce tenant scope.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes
- **blocking_for_production:** yes
- **recommended_action:** Add `tenant_id` to operator table and record;
  update `authenticate_operator()` to return `tenant_id`; inject into
  request context.
- **recommended_issue:** GL-200B

---

### GL-200A-F003

- **id:** GL-200A-F003
- **severity:** critical
- **category:** API-boundary
- **summary:** All API queries are globally-scoped; no `WHERE tenant_id = ?`
  clause exists in any resource query.
- **evidence:** `backend/src/grants.py`: `list_grants()` = `SELECT * FROM
  grants ORDER BY created_at DESC` — no tenant filter. Similar pattern
  in `grant_requests.py`, `challenges.py`, `grant_executions.py`.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes
- **blocking_for_production:** yes
- **recommended_action:** Update all list/get/create/update/delete query
  functions to accept and apply `tenant_id` parameter.
- **recommended_issue:** GL-200B

---

### GL-200A-F004

- **id:** GL-200A-F004
- **severity:** critical
- **category:** audit-context
- **summary:** Audit events carry no `tenant_id`; audit trail is a single
  global namespace.
- **evidence:** `backend/src/audit_log.py`: `AuditEvent` dataclass and
  hash-chain payload include no `tenant_id`. `audit_events` table schema
  (migration 0001) has no `tenant_id` column.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes
- **blocking_for_production:** yes
- **recommended_action:** Add `tenant_id` to `audit_events` table; update
  `AuditEvent` model; update hash-chain canonical payload to include
  `tenant_id` for post-migration events; handle dual-mode verification.
- **recommended_issue:** GL-200B + GL-202

---

### GL-200A-F005

- **id:** GL-200A-F005
- **severity:** high
- **category:** permission-model
- **summary:** Agent permission assignments are globally-scoped; no tenant
  binding exists.
- **evidence:** `backend/src/agent_permission_assignments.py`: assignments
  table has no `tenant_id` column. Scope evaluation does not check tenant
  context.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes
- **blocking_for_production:** yes
- **recommended_action:** Add `tenant_id` to `agent_permission_assignments`
  table; update scope evaluation to verify tenant context.
- **recommended_issue:** GL-200B

---

### GL-200A-F006

- **id:** GL-200A-F006
- **severity:** high
- **category:** database-migration
- **summary:** Hash-chain canonical payload does not include `tenant_id`;
  adding `tenant_id` to the payload post-migration will break existing
  chain verification unless handled carefully.
- **evidence:** `backend/src/audit_log.py`: `_hash_payload()` computes a
  canonical JSON payload with no `tenant_id`. Adding `tenant_id` post-hoc
  breaks `row_hash` values for historical events.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** no (requires careful implementation)
- **blocking_for_production:** yes (if not handled)
- **recommended_action:** Use dual-mode chain verification: historical events
  (no `tenant_id` in hash) verified with old canonical payload; new events
  verified with `tenant_id`-inclusive payload. Migration boundary marker
  event appended.
- **recommended_issue:** GL-200B + GL-202

---

### GL-200A-F007

- **id:** GL-200A-F007
- **severity:** medium
- **category:** testing
- **summary:** No cross-tenant isolation tests exist in the current test suite.
- **evidence:** `backend/tests/`: no test file contains `cross_tenant` or
  `tenant_id` assertions. Security boundary tests check auth but not
  tenant data isolation.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** yes (tests must be written
  alongside implementation)
- **blocking_for_production:** yes
- **recommended_action:** Write T-001 through T-007 tests as part of GL-200B.
  Add to CI smoke matrix in GL-203.
- **recommended_issue:** GL-200B + GL-203

---

### GL-200A-F008

- **id:** GL-200A-F008
- **severity:** medium
- **category:** production-readiness
- **summary:** Public documentation (README, SECURITY.md, docs/) currently
  states that tenant isolation is not implemented. This is accurate and must
  remain accurate until GL-200B is merged and verified.
- **evidence:** `docs/tenant_workspace_boundary_decision.md` (GL-132):
  "No multi-tenant isolation implemented." `SECURITY.md` section 6 notes
  same. `docs/production_readiness_gap_report_v2.md` confirms not ready.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** no
- **blocking_for_production:** yes (docs must be updated only after
  implementation is real)
- **recommended_action:** Do not update public docs to claim tenant isolation
  until GL-200B is merged, tested, and verified. Then update in GL-200B PR.
- **recommended_issue:** GL-200B

---

### GL-200A-F009

- **id:** GL-200A-F009
- **severity:** low
- **category:** workspace-isolation
- **summary:** `workspace_id` is not in the current schema; design must
  reserve it to avoid a second disruptive migration.
- **evidence:** No `workspace_id` in any migration file. GL-144 design doc
  proposed workspace model but was never implemented.
- **blocking_for_design:** no
- **blocking_for_gl200b_implementation:** no
- **blocking_for_production:** no (workspace isolation is a GL-200C concern)
- **recommended_action:** Add `workspace_id TEXT DEFAULT NULL` to all tables
  in the GL-200B migration to reserve the column. Do not enforce it in GL-200B.
- **recommended_issue:** GL-200B (column reservation) + GL-200C (enforcement)

---

## Decision

**tenant_workspace_design_ready_for_implementation**

---

## Decision Rationale

The design pack is complete. The recommended implementation plan is:

1. **GL-200B** implements Option A baseline: `tenant_id` on all business
   resource tables, operator binding, auth context injection, API query
   filtering, audit context, and fail-closed enforcement.
2. `workspace_id` column is reserved (nullable) in the GL-200B migration
   to avoid a second disruptive schema change.
3. Workspace enforcement is staged to GL-200C.
4. The design is compatible with both SQLite and PostgreSQL backends.
5. The hash-chain audit integrity concern (GL-200A-F006) is addressed via
   dual-mode verification and a migration boundary marker event.
6. All nine findings are actionable and assigned to concrete follow-up issues.
7. No production SaaS claim is made. No real customer/private grant data
   is requested. No exploit details are included.

---

## Recommended Next Issues

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-200A Combined Merge-and-Publish | GL-200A Combined Merge-and-Publish for Tenant/Workspace Isolation Design Pack | Merge GL-200A to main and push public snapshot if appropriate |
| GL-200B | Tenant/Workspace Isolation Implementation Baseline | Implement `tenant_id` on all business resource tables; operator binding; auth context; query filtering; audit context; fail-closed enforcement; migration; full T-xxx/A-xxx/AU-xxx/M-xxx test suite |
| GL-200C | Workspace Isolation Baseline | Activate `workspace_id` enforcement; workspace membership model; W-xxx tests |
| GL-200D | Tenant/Workspace Policy Engine | Full RBAC/policy engine replacing per-query tenant filter |
| GL-201 | Tenant/Workspace Isolation API Contract Update | Update `docs/openapi.yaml` to reflect tenant context |
| GL-202 | Tenant/Workspace Isolation Audit Propagation | Harden audit chain tenant context; dual-mode chain verification; `workspace_id` in audit |
| GL-203 | Tenant/Workspace Isolation Regression/Smoke Matrix | Add cross-tenant and workspace isolation to CI smoke matrix |

---

## Safety Confirmations

| Confirmation | Status |
|-------------|--------|
| no_github_push_performed | confirmed |
| no_visibility_change_performed | confirmed |
| internal_repo_not_pushed_directly_to_github | confirmed |
| no_github_api_label_changes_performed | confirmed |
| no_github_issue_changes_performed | confirmed |
| no_reviewer_outreach_sent | confirmed |
| no_backend_src_changes | confirmed |
| no_openapi_changes | confirmed |
| no_migration_db_dependency_changes | confirmed |
| no_dependency_manifest_changes | confirmed |
| no_sdk_implementation_changes | confirmed |
| no_package_publishing_changes | confirmed |
| no_examples_runtime_changes | confirmed |
| no_frontend_website_design_changes | confirmed |
| no_github_workflow_changes | confirmed |
| no_snapshot_publish_script_behavior_changes | confirmed |
| no_production_saas_claim | confirmed |
| tenant_workspace_isolation_not_claimed_as_implemented | confirmed |
| no_real_customer_data_requested | confirmed |
| no_private_grant_data_requested | confirmed |
| no_secrets_requested | confirmed |
| no_exploit_details_included | confirmed |
| security_sensitive_reports_routed_to_github_security_advisories | confirmed |

This document is **design only**. Tenant/workspace isolation is **not yet implemented** — this design pack defines the architecture for future implementation in GL-200B and later issues. No production SaaS claim is made. No real customer data or private grant data is involved. Security-sensitive findings should be reported via GitHub Security Advisories.

(End of GL-200A Tenant/Workspace Isolation Design Pack)
