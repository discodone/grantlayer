# GL-144 Tenant / Workspace Data Model Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Status

This document is the **GL-144 Tenant / Workspace Data Model Design**. It defines
proposed entities, relationships, ownership boundaries, isolation rules,
auth/permission implications, migration sequencing, risk register, validation
gates, non-goals, and follow-up issues.

| Field | Value |
|-------|-------|
| Issue | GL-144 |
| Status | design-only |
| Production code changed | **No** |
| Tenant implementation added | **No** |
| Workspace implementation added | **No** |
| Production SaaS readiness claimed | **No** |

This is **NOT implementation.**  
This is **NOT a migration.**  
This is **NOT API work.**  
This is **NOT auth redesign.**  
This is **NOT production SaaS enablement.**

---

## 2. Current Posture

GrantLayer has **no production tenant/workspace isolation implemented yet**.
The following posture statements apply:

- **Tenant isolation is not implemented** — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers.
- **Shared production SaaS for unrelated customers remains blocked** until
  explicit tenant/workspace boundaries are designed, implemented, and verified.
- All grants, grant requests, grant executions, evidence, audit events, and
  provenance records share a **single namespace** within a deployment.
- **GL-132 boundary decision remains authoritative**: no multi-tenant claims are
  permitted, no shared SaaS environment is approved for unrelated customers, and
  no tenant or workspace model exists in production code.
- Operator roles and named ownership currently provide the only implicit
  boundary (operator-bounded workspace model under GL-132 Option B).

---

## 3. Definitions

### 3.1 Tenant

A **tenant** is a logical boundary that isolates one customer's data, grants,
evidence, audit records, and operator identities from another customer's.
A tenant is the top-level organizational boundary for a GrantLayer deployment.

### 3.2 Workspace

A **workspace** is a scoped operating context within a tenant, typically mapping
to a team, department, or organizational unit that shares grants and evidence
but remains isolated from other workspaces within the same tenant.

### 3.3 Operator

An **operator** is an authenticated individual or service identity that performs
actions within a tenant/workspace boundary.

### 3.4 Admin

An **admin** is an operator with elevated privileges (typically `owner` or
`grant_admin` role) who can manage tenant/workspace configuration, membership,
and boundary policies.

### 3.5 Membership

A **membership** is an explicit association between an operator identity and a
tenant or workspace, including a role/scope that defines what the operator may
access within that boundary.

### 3.6 Resource Ownership

**Resource ownership** is the assignment of a grant, grant request, grant
execution, evidence artifact, audit event, or provenance event to a specific
workspace (and by extension, a specific tenant). Every customer-owned resource
must have an explicit ownership path.

### 3.7 Grant Request

A **grant request** is a structured request for a grant, submitted by an
operator, subject to approval workflow. In a tenant-aware model, grant requests
must belong to a workspace.

### 3.8 Grant Execution

A **grant execution** is a record of a protected action attempt. In a
tenant-aware model, executions must belong to the same workspace as the grant
and grant request that produced them.

### 3.9 Evidence Archive / Artifact

An **evidence archive** (or evidence bundle/artifact) is an immutable persisted
record of execution data. In a tenant-aware model, evidence must be scoped to
the workspace that produced it.

### 3.10 Audit Event

An **audit event** is a tamper-evident record of an action. In a tenant-aware
model, audit events should carry tenant/workspace context for scoping and
redaction purposes.

### 3.11 Provenance Event

A **provenance event** is an append-only record for decision tracing. In a
tenant-aware model, provenance events should preserve the resource ownership
context of the workspace that generated them.

---

## 4. Proposed Data Model

### 4.1 tenants

Proposed entity to represent a top-level customer boundary.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID / string | Primary key, stable identifier |
| `slug` | string | URL-safe unique identifier |
| `name` | string | Display name |
| `display_name` | string | Human-readable label |
| `status` | enum | e.g. `active`, `suspended`, `pending_deletion` |
| `created_at` | ISO-8601 timestamp | Immutable |
| `updated_at` | ISO-8601 timestamp | Updated on mutation |

### 4.2 workspaces

Proposed entity to represent a scoped operating context within a tenant.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID / string | Primary key |
| `tenant_id` | UUID / string | Foreign key to tenants.id (required) |
| `slug` | string | URL-safe, unique within tenant |
| `name` | string | Display name |
| `display_name` | string | Human-readable label |
| `status` | enum | e.g. `active`, `archived`, `pending_deletion` |
| `created_at` | ISO-8601 timestamp | Immutable |
| `updated_at` | ISO-8601 timestamp | Updated on mutation |

### 4.3 tenant_memberships

Proposed entity to associate operators with tenants.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID / string | Primary key |
| `tenant_id` | UUID / string | Foreign key to tenants.id |
| `operator_id` | string | Reference to operators.operator_id |
| `role` | string | Scoped role within the tenant |
| `status` | enum | e.g. `active`, `revoked` |
| `created_at` | ISO-8601 timestamp | Immutable |
| `updated_at` | ISO-8601 timestamp | Updated on mutation |

### 4.4 workspace_memberships

Proposed entity to associate operators with workspaces.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID / string | Primary key |
| `workspace_id` | UUID / string | Foreign key to workspaces.id |
| `operator_id` | string | Reference to operators.operator_id |
| `role` | string | Scoped role within the workspace |
| `status` | enum | e.g. `active`, `revoked` |
| `created_at` | ISO-8601 timestamp | Immutable |
| `updated_at` | ISO-8601 timestamp | Updated on mutation |

### 4.5 operator_scope / operator_workspace_access

Proposed junction or scope record that defines what workspaces an operator may
access within a tenant. May be merged into `workspace_memberships` or kept as a
separate capability record depending on implementation design later.

| Field | Type | Notes |
|-------|------|-------|
| `operator_id` | string | Reference to operators.operator_id |
| `tenant_id` | UUID / string | Tenant scope |
| `workspace_id` | UUID / string | Workspace scope (optional; null = all workspaces in tenant) |
| `scope_type` | enum | e.g. `all_workspaces`, `specific_workspace` |
| `created_at` | ISO-8601 timestamp | Immutable |

### 4.6 grant_requests ownership fields

Proposed additions to the `GrantRequest` model (design level only — **not**
implemented in GL-144):

| Field | Type | Notes |
|-------|------|-------|
| `tenant_id` | UUID / string | Owning tenant |
| `workspace_id` | UUID / string | Owning workspace |

### 4.7 grant_executions ownership fields

Proposed additions to the `GrantExecution` model (design level only):

| Field | Type | Notes |
|-------|------|-------|
| `tenant_id` | UUID / string | Owning tenant |
| `workspace_id` | UUID / string | Owning workspace |

### 4.8 evidence / archive ownership fields

Proposed additions to the `EvidenceBundle` model (design level only):

| Field | Type | Notes |
|-------|------|-------|
| `tenant_id` | UUID / string | Owning tenant |
| `workspace_id` | UUID / string | Owning workspace |

### 4.9 audit / provenance tenant/workspace context

Proposed additions to the `AuditEvent` and `ProvenanceEvent` models
(design level only):

| Field | Type | Notes |
|-------|------|-------|
| `tenant_id` | UUID / string | Contextual tenant |
| `workspace_id` | UUID / string | Contextual workspace |

These fields would be used for scoping, filtering, and redaction. They must not
break the hash-chain immutability guarantee.

---

## 5. Proposed Fields Summary

### 5.1 Tenant fields

- `id` — stable primary key
- `slug` — URL-safe unique name
- `name` — short display name
- `display_name` — human-readable label
- `status` — lifecycle state
- `created_at` / `updated_at` — timestamps

### 5.2 Workspace fields

- `id` — stable primary key
- `tenant_id` — parent tenant reference
- `slug` — URL-safe unique name within tenant
- `name` — short display name
- `display_name` — human-readable label
- `status` — lifecycle state
- `created_at` / `updated_at` — timestamps

### 5.3 Membership fields

- `id` — stable primary key
- `tenant_id` / `workspace_id` — boundary reference
- `operator_id` — operator identity reference
- `role` — scoped role
- `status` — membership state
- `created_at` / `updated_at` — timestamps

### 5.4 Ownership references

- `tenant_id` on every customer-owned resource
- `workspace_id` on every customer-owned resource
- System-scoped resources (e.g., global audit events without a workspace) may
  use a sentinel workspace or NULL with explicit system scope.

### 5.5 Indexes and unique constraints (design level only)

- `tenants.slug` — unique index
- `workspaces(tenant_id, slug)` — unique composite index
- `tenant_memberships(tenant_id, operator_id)` — unique composite index
- `workspace_memberships(workspace_id, operator_id)` — unique composite index
- `grant_requests(workspace_id, status)` — index for filtering
- `grant_executions(workspace_id, executed_at)` — index for filtering
- `audit_events(workspace_id, timestamp)` — index for scoping queries

These indexes are **proposed for future implementation**, not created in GL-144.

---

## 6. Relationship Model

```
Tenant 1───────* Workspace
   │ 1              │ 1
   │                │
   │*               │*
TenantMembership  WorkspaceMembership
   │                │
   │*               │*
Operator ◄─────────┘
```

Rules:

1. **Tenant has many workspaces** — a tenant may contain zero or more workspaces.
2. **Workspace belongs to one tenant** — a workspace must have exactly one parent
   tenant; no cross-tenant workspace sharing.
3. **Operators receive explicit membership/scope** — an operator has no implicit
   access to a tenant or workspace. Every access path must be explicit.
4. **Grant resources belong to one workspace** unless explicitly system-scoped.
   A grant, grant request, grant execution, and evidence bundle must be owned by
   exactly one workspace (and by extension, one tenant).
5. **Audit/provenance entries carry tenant/workspace context** where applicable.
   System-level audit events (e.g., infrastructure health) may use a sentinel
   system scope.

---

## 7. Isolation Rules

1. **Customer-owned resources must be tenant/workspace scoped** — no unscoped
   customer data may exist in a tenant-aware deployment.
2. **No cross-tenant reads by default** — any query for customer data must
   include an explicit tenant filter. Default queries without tenant scope must
   return empty or raise an error.
3. **No cross-workspace access without explicit scope** — an operator with
   membership in workspace A must not read or mutate data in workspace B unless
   explicitly granted cross-workspace scope.
4. **Admin legacy mode is not SaaS tenant isolation** — the existing admin-token
   and operator-token paths remain unchanged in GL-144. Future tenant-aware auth
   must not conflate legacy admin access with tenant-scoped access.
5. **Background/system operations must have explicit system scope** — background
   jobs, migrations, and system-level audit events must declare whether they are
   system-scoped or tenant-scoped. No implicit global access.

---

## 8. Auth / Permission Implications

1. **Operator token lookup remains secure** — the existing PBKDF2-HMAC-SHA256
   token verification path is not modified in GL-144. Future tenant-aware auth
   must preserve the same token hashing and lookup semantics.
2. **Future permissions must include tenant/workspace scope** — any permission
   check must validate that the authenticated operator has an active membership
   in the target tenant/workspace with a role that permits the action.
3. **Explicit deny-by-default for missing scope** — if an operator does not have
   an explicit membership for a tenant/workspace, access is denied.
4. **No implicit global access except designated system/admin flows** — system
   admin flows (e.g., health checks, runtime gates) may bypass tenant/workspace
   checks, but this must be explicit and audited.
5. **Current GL-141 default operator model remains preserved** —
  `ENABLE_OPERATOR_MODEL` defaults to `True`. No auth semantics are changed in
   GL-144.

---

## 9. Audit/Provenance/Logging Implications

1. **Audit events should include tenant/workspace context later** — the
   `AuditEvent` model should carry contextual `tenant_id` and `workspace_id` for
   scoping and filtering. These fields must be included in the deterministic
   hash payload or excluded consistently; changing the hash payload requires a
   migration/versioning plan.
2. **Provenance chains should preserve resource ownership context** —
   `ProvenanceEvent` records should reference the workspace that generated them
   so that provenance summaries can be scoped correctly.
3. **Logs should include safe tenant/workspace identifiers, not secrets** —
   structured logs may include tenant slug and workspace slug for operational
   debugging, but must never include tokens, raw credentials, or internal UUIDs
   that could be used for inference attacks.
4. **Hash-chain immutability must be preserved** — any addition of
   tenant/workspace fields to the `AuditEvent` canonical hash payload must be
   done carefully to avoid invalidating existing chain events. A versioning
   strategy or backward-compatible canonicalization is required.

---

## 10. Migration Sequencing

GL-144 is **design only**. No schema migration is implemented. The following
sequence is proposed for future issues:

1. **GL-144 (this issue):** Design only — define entities, relationships,
   isolation rules, auth implications, audit implications, risks, gates, and
   follow-up issues.
2. **Schema migration plan (GL-144A):** Design the exact migration files,
   column types, constraints, and index definitions.
3. **Migration implementation (GL-144B):** Create migration scripts that add
   `tenants`, `workspaces`, `tenant_memberships`, and `workspace_memberships`
   tables without modifying existing resource tables.
4. **Backfill strategy (GL-144D):** Define how existing grants, grant requests,
   grant executions, evidence, audit events, and provenance events receive
   default tenant/workspace assignments. Must be deterministic and reversible.
5. **Endpoint authorization enforcement (GL-144E):** Update auth boundary to
   require tenant/workspace scope on protected actions.
6. **Audit/provenance scoping (GL-144F):** Add tenant/workspace context fields
   to audit and provenance models with hash-chain compatibility.
7. **Public SaaS claim (future):** Only after all validation gates pass and
   cross-tenant access prevention tests are green.

---

## 11. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Partial tenant isolation** | High | Do not claim SaaS readiness until all resource paths enforce scope. |
| **Missing filters** | High | Every read and write query must include explicit tenant/workspace filter. |
| **Cross-tenant leakage** | Critical | Automated tests must verify that no endpoint leaks data across tenants. |
| **Audit ambiguity** | Medium | Audit events without tenant/workspace context must not be trusted for scoped reporting. |
| **Operator/admin confusion** | Medium | Legacy admin mode and tenant-scoped admin must be clearly distinguished. |
| **Migration/backfill corruption** | High | Backfill must be reversible; test on a full copy of production data before applying. |
| **Performance/indexing risk** | Medium | Proposed indexes must be validated against realistic data volumes before deployment. |
| **OpenAPI drift** | Medium | Any API addition (e.g., `X-Tenant-Id` header) must be reflected in `docs/openapi.yaml`. |
| **Test gaps** | High | Add cross-tenant isolation tests before claiming any SaaS readiness. |

---

## 12. Validation Gates

Before any tenant/workspace implementation issue is considered complete, the
following gates must pass:

- **GL-132 tenant/workspace boundary decision** — the boundary posture, non-claims,
  and pilot go/no-go criteria remain authoritative.
- **GL-139 audit hash-chain write lock** — the `threading.RLock` around audit
  hash-chain append must remain present and effective.
- **GL-140 ThreadingHTTPServer** — `run()` must continue to instantiate
  `ThreadingHTTPServer`; no extraction must reintroduce plain `HTTPServer`.
- **GL-141 operator model default** — `ENABLE_OPERATOR_MODEL` defaults to `True`.
  Legacy admin-token path remains available but is not the default.
- **GL-142 request parsing cleanup** — `_read_json` contains no
  `isinstance(self.rfile, BytesIO)` branch.
- **GL-143 route decomposition plan** — accepted plan guides safe extraction;
  tenant/workspace implementation must not conflict with decomposition.
- **Security boundary regression** — `backend/tests/test_security_boundary_regression.py`
  passes with zero failures.
- **Full backend suite on main** — all backend tests pass on `main` before any
  tenant/workspace implementation branch is created.

---

## 13. Explicit Non-Goals

The following are **explicitly out of scope** for GL-144:

- **No implementation** — no code is written for tenant/workspace behavior.
- **No schema/migration** — no database migration or schema change is implemented.
- **No API/OpenAPI change** — no endpoint behavior or OpenAPI specification is changed.
- **No auth redesign** — no authentication or authorization semantics are modified.
- **No endpoint enforcement** — no tenant/workspace scope enforcement is added to endpoints.
- **No frontend/website/design work** — no UI, signup flow, or branding changes.
- **No production SaaS readiness claim** — this design does not make the backend
  production SaaS complete.
- **No shared SaaS approval** — unrelated customers must not share a deployment
  until implementation and validation are complete.
- **No dependency additions** — no new packages or version changes.
- **No production code changes** (`backend/src/`).
- **No `.claude/*` changes**.

---

## 14. Proposed Follow-Up Issues

| Issue | Title | Purpose |
|-------|-------|---------|
| **GL-144A** | Tenant/Workspace Schema Migration Plan | Design exact migration files, column types, constraints, and indexes for tenant/workspace tables. |
| **GL-144B** | Tenant/Workspace Persistence Model | Implement `tenants`, `workspaces`, `tenant_memberships`, and `workspace_memberships` tables and models. |
| **GL-144C** | Membership/Scope Model | Implement operator-to-tenant and operator-to-workspace membership logic with scoped roles. |
| **GL-144D** | Resource Ownership Backfill Strategy | Define deterministic backfill of existing data to default tenant/workspace assignments. |
| **GL-144E** | Endpoint Authorization Enforcement Plan | Design how tenant/workspace scope is injected into auth boundary and enforced on every protected action. |
| **GL-144F** | Audit/Provenance Tenant Scoping Plan | Design how tenant/workspace context is added to audit and provenance events without breaking hash-chain integrity. |
| **GL-144G** | OpenAPI Contract Update Plan | Design API additions (headers, path parameters, response fields) for tenant/workspace awareness. |

---

## 15. Go / No-Go Criteria

An implementation issue is **go** only when **all** of the following are true:

1. **No behavior change until design accepted** — GL-144 design must be reviewed
   and accepted before any implementation branch is created.
2. **Every resource ownership path identified** — all grants, grant requests,
   grant executions, evidence, audit events, and provenance events must have a
   clear ownership path to a workspace and tenant.
3. **Migration/backfill plan reviewed** — the migration sequence and backfill
   strategy must be reviewed for reversibility and safety.
4. **Auth/scope model reviewed** — the scoped permission model must be reviewed
   for deny-by-default correctness and legacy auth compatibility.
5. **Audit/provenance implications reviewed** — hash-chain immutability and
   log safety must be reviewed before any audit model changes.
6. **Full-suite gate defined** — the full backend test suite must pass before
   and after every incremental implementation step.

An implementation issue is **no-go** if any of the following occur:

- Any auth failure path changes its status code or error payload shape.
- Any request parsing error changes its status code or error code.
- `ThreadingHTTPServer` is replaced or bypassed.
- The audit hash-chain write lock is removed or weakened.
- Rate-limit behavior changes for any client.
- Structured logging or correlation ID propagation stops working.
- The security boundary regression suite fails.
- A multi-tenant SaaS readiness claim is made before validation gates pass.

---

## 16. Next Issue

**GL-145 Developer Adoption Strategy Intake**

After the tenant/workspace data model design is accepted, the next architectural
planning issue is the developer adoption strategy intake. This is a separate
planning issue and does not overlap with GL-144 scope.

---

> GL-144 documents a **proposed tenant/workspace data model** for future
> implementation. It does **not** add any production code, schema, migration,
> API change, auth change, or SaaS readiness claim. It explicitly preserves
> all existing gates (GL-132, GL-139, GL-140, GL-141, GL-142, GL-143) and
> mandates that no shared SaaS deployment for unrelated customers is approved
> until follow-up implementation issues are completed and validation gates pass.
