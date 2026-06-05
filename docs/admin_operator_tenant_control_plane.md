# GL-206 Admin/Operator Tenant Control Plane

**Issue ID:** GL-206
**Branch:** `gl-206-admin-operator-tenant-control-plane`
**Status:** Internal / Developer Preview

---

## Context

GL-200A through GL-205 are merged internally. The GL-200 tenant/workspace
isolation block, GL-201 production auth/secrets/config hardening, GL-202
persistence/PostgreSQL/migration readiness, GL-203 API contract/SDK packaging
decision, GL-203B OpenAPI contract cleanup, GL-203C SDK prototype/packaging
boundary, GL-204 Production Ops / Go-No-Go v3, and GL-205 Live PostgreSQL /
Backup-Restore / Observability Baseline are all represented by clean doc, JSON,
and test artifacts.

GL-204 identified Admin-plane tenant isolation (GL-200D) as remaining blocker
RB-004 (P0): operator management is not cross-tenant-safe and must not be
exposed in production multi-tenant contexts.

GL-206 addresses this gap by:
1. Hardening `backend/src/operators.py` with explicit tenant assignment and safe
   response fields
2. Adding minimal admin-only control-plane HTTP routes for operator CRUD
3. Enforcing that operator tokens cannot override their own tenant context
4. Emitting structured audit events for control-plane operations
5. Documenting the admin/operator model semantics and remaining gaps

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation baseline implemented but not production-complete
- No official SDK/package is claimed or published

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
grant/institutional data is used.

---

## Scope

GL-206 covers:
- Review of the existing admin/operator model in operators.py, auth.py,
  server.py, and audit_log.py
- Hardening: explicit tenant_id required for operator creation
- Hardening: admin-only control-plane HTTP routes (POST /admin/operators,
  GET /admin/operators, GET /admin/operators/{id}, POST /admin/operators/{id}/revoke)
- Safe response fields: token_hash, lookup_hash excluded from list/read responses
- One-time raw token on create (acceptable pattern, documented)
- Fail-closed behavior: revoked/inactive operators cannot authenticate
- Tenant derivation: operator tenant_id is server-assigned, not client-overridable
- Structured log events for operator_created and operator_revoked
- Documentation of remaining gaps and risk register

## Non-Goals

GL-206 is not:
- A production SaaS readiness declaration
- A frontend, website, or design change
- An official SDK/package implementation or publication
- A live PostgreSQL production deployment
- A full RBAC/policy engine
- Production IAM (OAuth/JWT/SSO)
- Workspace enforcement (reserved/deferred)
- A public publish, GitHub push, or visibility change
- Weakening of GL-200 through GL-205 baselines

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|----------|
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
| docs/live_postgres_backup_observability_baseline.md | Yes |
| docs/examples/gl205/live_postgres_backup_observability_baseline.json | Yes |
| docs/sdk_prototype_packaging_boundary.md | Yes |
| docs/examples/gl203c/sdk_prototype_packaging_boundary.json | Yes |
| docs/openapi_api_contract_cleanup.md | Yes |
| docs/examples/gl203b/openapi_api_contract_cleanup.json | Yes |
| docs/api_contract_sdk_packaging_decision.md | Yes |
| docs/examples/gl203/api_contract_sdk_packaging_decision.json | Yes |
| docs/persistence_postgres_migration_readiness.md | Yes |
| docs/examples/gl202/persistence_postgres_migration_readiness.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | Yes |
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| docs/openapi.yaml | Yes |
| backend/src/operators.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/config.py | Yes |
| backend/src/server.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/agent_permissions.py | Yes |
| backend/src/agent_permission_assignments.py | Yes |
| backend/src/migrations/ | Yes |

---

## Current Admin/Operator Model Summary

### Admin Authentication

Admin token authentication (`check_admin_token()` in `auth.py`) uses
`hmac.compare_digest` for constant-time comparison. It fails closed:

- Missing token → 401
- Invalid token → 403
- `GRANTLAYER_REQUIRE_ADMIN_TOKEN=true` and no token configured → 403

Admin token is NEVER included in responses, logs, or error messages. Admin mode
is bound to the `demo` tenant for backward compatibility (`_require_admin()`
returns `{"tenant_id": "demo"}`).

### Operator Authentication

Operator token authentication (`authenticate_operator_with_reason()` in
`operators.py`) uses PBKDF2-SHA256 (600,000 iterations) with a deterministic
lookup hash (SHA-256) for narrowing before PBKDF2 verification.

- Missing/malformed token → reason `"operator_auth_required"`
- Expired token → reason `"operator_token_expired"`
- Inactive operator (`active=0`) → excluded by query (`AND active=1`)

Operator token is never returned in responses (except one-time on create),
never included in logs, and never in audit event data.

### Tenant Context Derivation

Tenant context is server-derived from authentication:
- Operator token → `operator.tenant_id` from DB
- Admin token → `"demo"` (hardcoded, not client-supplied)

No request header (e.g. `X-Tenant-ID`) can override the server-derived
tenant context. This is enforced in `check_auth()` and `_require_operator()`.

### Operator Model Fields

The `operators` table includes:
```
id, name, role, token_hash, token_lookup_hash, active,
created_at, expires_at, rotated_at, tenant_id, workspace_id
```

`to_dict()` on the `Operator` class returns only:
```
operatorId, name, role, active, tenantId
```
Never: `token_hash`, `token_lookup_hash`, `lookup_hash`, raw token.

---

## Tenant Assignment Model

Operator `tenant_id` is:
1. **Set at creation time** by the admin. The `create_operator()` function now
   requires `tenant_id` as an explicit positional argument (no silent default).
2. **Never overridable by the operator** at authentication time. The tenant
   context is read from the DB row, not from any request header.
3. **Visible to admin** via the control-plane read routes.
4. **Not modifiable by operator** — there is no self-service tenant reassignment
   endpoint.

For demo/bootstrap compatibility, `tenant_id="demo"` must be passed explicitly
to `create_operator()`. The bootstrap path uses `tenant_id="demo"`.

---

## Admin Behavior Model

### Authentication

Admin uses the `GRANTLAYER_ADMIN_TOKEN` Bearer token. The `_require_admin()`
method in `server.py` calls `check_admin_token()` from `auth.py`.

Fail-closed behavior:
- No token → 401
- Wrong token → 403
- `REQUIRE_ADMIN_TOKEN=false` in production-like mode → startup error

### Control-Plane Routes (GL-206 additions)

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/admin/operators` | POST | Admin only | Create operator with explicit tenantId |
| `/admin/operators` | GET | Admin only | List all operators (safe fields) |
| `/admin/operators/{id}` | GET | Admin only | Read single operator (safe fields) |
| `/admin/operators/{id}/revoke` | POST | Admin only | Revoke/deactivate operator |

All routes return only safe fields (no token_hash, lookup_hash, raw token).

### What Admin Can Do

- Create operators with any `tenantId`
- List and read all operators across tenants
- Revoke operators (sets `active=0`)
- Access all tenant resources via the `demo` tenant (admin token mode)

### What Admin Cannot Do

- Access real-customer/institutional-data resources (no-go per GL-204)
- Override the operator model for production multi-tenant without GL-200D

---

## Operator Behavior Model

### Authentication

Operator uses a Bearer token. On success, `check_auth()` returns:
```python
{"operator": op.to_dict(), "tenant_id": op.tenant_id}
```

The `tenant_id` in this payload comes from the DB operator row, not from any
request header.

### Tenant Scoping

All resource operations (grants, grant_requests, challenges, audit_events,
grant_executions) are filtered by `tenant_id` derived from the authenticated
operator. An operator cannot see or mutate resources belonging to another tenant.

### What Operators Can Do

- Access resources within their own tenant
- Authenticate via Bearer token
- View their own operator info via `/operators/me`

### What Operators Cannot Do

- Modify their own `tenant_id` (no self-service tenant assignment)
- Access admin control-plane routes (`/admin/operators`)
- Escalate to admin role
- See another tenant's operators or resources

---

## Control-Plane API Behavior

### POST /admin/operators

**Auth:** Admin token required
**Request body:**
```json
{
  "name": "string (required)",
  "role": "string (required)",
  "tenantId": "string (required)"
}
```
**Response (201):**
```json
{
  "operatorId": "uuid",
  "name": "string",
  "role": "string",
  "active": true,
  "tenantId": "string",
  "createdAt": "ISO-8601",
  "expiresAt": "ISO-8601",
  "token": "raw-token-one-time-only"
}
```
The `token` field is returned once on create only. It must be stored securely
by the caller. It is never returned again by list/read routes.

Missing `tenantId` → 400 with explicit error.

### GET /admin/operators

**Auth:** Admin token required
**Response (200):** Array of safe operator dicts (no token/hash fields).

### GET /admin/operators/{id}

**Auth:** Admin token required
**Response (200):** Single safe operator dict (no token/hash fields).
**Not found → 404.**

### POST /admin/operators/{id}/revoke

**Auth:** Admin token required
**Response (200):** `{"ok": true, "operatorId": "...", "revoked": true}`
**Not found → 404.**

---

## Audit Behavior

### Structured Log Events (operator_action)

GL-206 emits structured log events for control-plane operations using the
`operator_action` event type (already defined in `structured_logging.py`):

| Operation | Event | Fields included |
|-----------|-------|-----------------|
| Operator created | `operator_action` | `action="operator_created"`, `operator_id`, `tenant_id` |
| Operator revoked | `operator_action` | `action="operator_revoked"`, `operator_id` |

**Never included in events:** raw token, token_hash, lookup_hash, password_hash.

### Audit Hash-Chain

The `audit_events` hash-chain (in `audit_log.py`) is unchanged. Operator
control-plane events do NOT use the `AuditEvent` model (which is designed for
grant/access approval decisions). This is intentional — the hash-chain is for
access/grant audit immutability, not operator management.

Control-plane events use structured logging (`safe_log`) which is the correct
channel for operational events.

---

## Security Model

### Fail-Closed Behavior

| Scenario | Behavior |
|----------|----------|
| Missing admin token | 401 |
| Invalid admin token | 403 |
| Operator token on admin route | 403 |
| Revoked operator token (`active=0`) | 401 (excluded by query) |
| Expired operator token | 401 (`operator_token_expired`) |
| Missing `tenantId` in create | 400 |

### Token Safety

- Raw token returned ONCE on create only (one-time disclosure pattern)
- Token hash uses PBKDF2-SHA256 (600,000 iterations)
- Lookup hash uses SHA-256 (narrowing only, not auth)
- No token value in list/read responses
- No token value in log events or audit events
- Admin token uses `hmac.compare_digest` (constant-time)

### Tenant Isolation

- Tenant context derived server-side from auth — never from request headers
- Operator cannot override own tenant_id
- Operator cannot access admin routes
- Cross-tenant denial enforced at all resource endpoints (from GL-200A/B/C)

### Cross-Tenant Control-Plane Gap (Remaining)

Admin token mode is bound to `"demo"` tenant. This means admin cannot manage
resources in multiple real tenants via operator token mode. For production
multi-tenant, each tenant must have their own operator hierarchy. Full
multi-tenant operator management (GL-200D) remains deferred.

---

## Production-Mode Implications

This GL does NOT change production readiness posture:
- Admin-plane control-plane is hardened but not production multi-tenant safe
- No OAuth/JWT/SSO: operator model remains PBKDF2/Bearer for controlled preview
- No token rotation UI: operators rotate by creating new operators
- No production IAM: deferred to future issues
- No workspace_id enforcement: deferred

The control-plane routes (`/admin/operators`) are suitable for controlled
preview and developer preview usage with synthetic/demo data. They are NOT
suitable for production multi-tenant deployments without full GL-200D closure.

---

## Controlled-Preview Impact

GL-206 hardening is compatible with the GL-198 controlled preview boundary:
- Admin can create operators for each synthetic/demo tenant
- Operators remain scoped to their assigned tenant
- No real customer data is involved

The admin control-plane routes are additive — they do not weaken any GL-200
through GL-205 guarantees.

---

## Implementation Summary

### Changed files

**`backend/src/operators.py`:**
- `create_operator()`: `tenant_id` is now a required positional argument
  (removes silent `"dev"` default; all existing callers already pass it explicitly)
- `revoke_operator(operator_id)`: new function — sets `active=0`, returns bool
- `_operator_to_safe_dict(op)`: new helper — safe fields only for admin routes
- `list_operators_for_admin()`: new function — returns list of safe dicts
- `get_operator_safe(operator_id)`: new function — returns safe dict or None
- Docstring updated to document GL-206 semantics

**`backend/src/server.py`:**
- Added `import secrets as _secrets_mod`
- Added path normalization entries for `/admin/operators/{id}` and
  `/admin/operators/{id}/revoke`
- GET `/admin/operators` — admin-only list (safe fields)
- GET `/admin/operators/{id}` — admin-only read (safe fields)
- POST `/admin/operators` — admin-only create with explicit `tenantId`
- POST `/admin/operators/{id}/revoke` — admin-only revoke

### Unchanged files

- `backend/src/auth.py` — already fail-closed, no changes needed
- `backend/src/audit_log.py` — hash-chain unchanged; control-plane uses safe_log
- `backend/src/models.py` — no schema additions needed
- Migrations — no new migrations needed (operators table has `active` column)
- `docs/openapi.yaml` — not updated in GL-206 (admin routes are additive/internal)

---

## Remaining Gaps

- **GL-200D full closure**: Operator management is not production multi-tenant
  safe. Admin token binds to `demo` tenant only. Full isolation requires
  per-tenant admin hierarchy.
- **No operator token rotation endpoint**: Manual rotation via create + revoke.
- **workspace_id not enforced**: Reserved column, deferred to future issue.
- **No OAuth/JWT/SSO**: PBKDF2/Bearer is suitable for controlled preview only.
- **No production IAM**: Required before any production SaaS deployment.
- **OpenAPI not updated**: Admin routes are not yet reflected in `docs/openapi.yaml`.
  This is intentional for GL-206 (internal-only, not public API contract yet).
- **Stale claims in README/AGENTS.md**: "Tenant isolation: not implemented"
  remains stale (deferred per GL-204).
- **No TLS, container hardening, or orchestration**: P0 for production.
- **No live PostgreSQL validation executed**: Remains P0 blocker from GL-205.
- **No automated backup or DR runbooks**: Remains P0 blocker from GL-205.

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R-001 | Admin token leaked gives full operator management access | Low | Critical | Keep admin token in environment variable; rotate on suspicion; fail-closed |
| R-002 | Operator created with wrong tenant_id cannot be corrected without revoke+recreate | Low | Medium | Admin can revoke and recreate; document in runbook |
| R-003 | Cross-tenant operator access via admin in multi-tenant production | Medium | High | Do not deploy multi-tenant production without GL-200D full closure |
| R-004 | One-time token on create not captured by caller | Low | Medium | Document token is returned once; caller must store immediately |
| R-005 | Revoked operator re-authenticates if DB has connection issues | Low | Critical | Fail-closed: auth query requires `active=1`; connection failure causes auth failure |

---

## Decision

**APPROVED_WITH_GAPS**

---

## Decision Rationale

1. The existing operator model (operators.py, auth.py) was already mostly
   hardened for controlled preview: PBKDF2 token hashing, fail-closed auth,
   `to_dict()` safe fields, constant-time admin token comparison.

2. GL-206 adds the missing admin control-plane routes, making operator
   lifecycle management (create/list/read/revoke) explicitly admin-gated.

3. `create_operator()` now requires explicit `tenant_id` — the silent `"dev"`
   default is removed. All existing callers already passed `tenant_id`
   explicitly, so this is a non-breaking hardening.

4. The revoke function (`revoke_operator()`) enables admin to deactivate
   operators. Revoked operators fail closed on authentication.

5. Structured log events are emitted for create/revoke. The audit hash-chain
   is not used for control-plane events (by design — it is for grant/access
   audit immutability).

6. Remaining gaps (production multi-tenant isolation, OAuth/JWT, workspace
   enforcement) are documented. None of them block the controlled preview
   posture.

7. No production SaaS claim is made. No real customer data is used.

---

## Safety Confirmations

- GL-206 is not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- Admin/operator tenant control-plane baseline does not mean full production
  tenant management UI exists.
- Tenant/workspace isolation is not claimed as production-complete.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No public publish, push, or visibility change.

---

## Recommended Next Issues

- **GL-206 Merge** — merge `gl-206-admin-operator-tenant-control-plane` to
  internal main after validation.
- **GL-207 Claim Safety & Controlled Preview Boundary** — correct stale
  claims in README/AGENTS.md/SECURITY.md/llms.txt.
- **GL-206B Live PostgreSQL Validation Execution** — requires ephemeral
  PostgreSQL instance; closes RB-001 from GL-205.
