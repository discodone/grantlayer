# GL-200B: Tenant/Workspace Isolation Implementation Baseline

**Issue:** GL-200B
**Status:** Baseline complete — GL-200C (workspace enforcement) and GL-200D (admin-plane) are pending
**Branch:** `gl-200b-tenant-workspace-isolation-implementation-baseline`
**Prerequisite:** GL-200A (design pack, merged)

## Summary

This document describes the GL-200B baseline implementation of tenant and workspace isolation in GrantLayer. It implements Option A from the GL-200A design pack: `tenant_id` is added to all business resource tables, operators are bound to a tenant, and the HTTP layer injects tenant context from auth payloads into all resource operations.

This is a **baseline**, not a complete multi-tenant solution. Workspace enforcement (`workspace_id`) is reserved for GL-200C, and admin-plane isolation (cross-tenant operator management) is reserved for GL-200D.

## What GL-200B Implements

### 1. Database Migration (0010_gl200b_tenant_workspace_isolation)

- Adds `tenant_id` to: `grants`, `grant_requests`, `challenges`, `grant_executions`, `evidence_archives`, `audit_events`, `operators`
- Adds `workspace_id TEXT DEFAULT NULL` (nullable, reserved for GL-200C) to all above tables
- Adds `scope TEXT DEFAULT NULL` to `audit_events`
- Backfill defaults: all tables (business resources + operators + audit_events) → `'demo'` for backward compatibility
- `audit_events.tenant_id` is **nullable** — system and legacy events (pre-migration) do not have a tenant
- Migration is idempotent: safe to re-run; each `ALTER TABLE` is guarded by a column-existence check
- Performance indexes: `idx_{table}_tenant_id` on each table; `idx_grants_tenant_subject` composite

### 2. Operator Tenant Binding (`operators.py`)

- `Operator` carries `tenant_id` field (default `'dev'`)
- `_row_to_operator()` reads `tenant_id` from DB row
- `bootstrap_operator_if_needed()` inserts with `tenant_id='dev'`
- New `create_operator()` function for test and future provisioning use

### 3. Auth Tenant Context (`auth.py`)

- `check_auth()` in operator mode returns `{"operator": ..., "tenant_id": op.tenant_id}` in payload
- `check_auth()` in admin-token mode injects `{"tenant_id": "demo"}` — backward-compatible dev/demo mode (consistent with legacy resource defaults)
- Clients never send `X-Tenant-ID`; tenant context is resolved server-side from the auth token

### 4. Resource Functions (tenant filtering)

All resource functions now accept an optional `tenant_id` parameter:

| Module | Functions updated |
|---|---|
| `grants.py` | `list_grants`, `get_grant`, `create_grant`, `revoke_grant` |
| `challenges.py` | `create_challenge`, `get_challenge`, `list_challenges` |
| `grant_requests.py` | `create_grant_request`, `get_grant_request`, `list_grant_requests`, `approve_grant_request`, `deny_grant_request`, `revoke_grant_request` |

When `tenant_id=None`, no tenant filter is applied (backward compat for internal/test use). When provided, all queries include `AND tenant_id = ?` — cross-tenant lookups return `None`/404 without leaking resource existence.

### 5. HTTP Server (`server.py`)

- `_require_admin()` now returns `True, {"tenant_id": "dev"}`
- New `_get_tenant_id(auth_payload)` helper extracts tenant from auth context
- All major routes updated: GET/POST /grants, /grant-requests, /challenges, /audit-events, and mutation endpoints now pass `tenant_id` to resource functions

### 6. Audit Log Tenant Context (`audit_log.py`)

- `AuditEvent` model extended with `tenant_id`, `workspace_id`, `scope` fields
- `append_event()` stores `tenant_id`, `workspace_id`, `scope` in DB
- `list_events(limit, tenant_id=None)` supports optional tenant filter
- **Dual-mode hash chain**: `_hash_payload()` includes `tenant_id` in the canonical hash payload only when non-None. Pre-migration events retain their original hashes; new events include tenant context in the chain. This is backward-compatible.

## What GL-200B Does NOT Implement

- **Workspace enforcement**: `workspace_id` column is added and nullable; enforcement is GL-200C scope
- **Multi-tenant operator creation**: Operators are provisioned manually or via `create_operator()`; no self-service tenant onboarding yet
- **Admin-plane isolation**: Cross-tenant operator management (GL-200D)
- **Tenant provisioning API**: No `/tenants` endpoint — GL-200C/D scope
- **Row-level security at DB layer**: Filtering is application-layer only
- **Production SaaS readiness**: This baseline is suitable for controlled developer preview, not general SaaS deployment

## Safety Confirmations

- No public GitHub push performed
- No production SaaS claim made
- No frontend/design/public-snapshot changes
- No GitHub workflow changes
- No force push, no --no-verify bypass

## Test Coverage

`backend/tests/test_gl200b_tenant_workspace_isolation_baseline.py` covers:

- Migration column existence and idempotency
- Cross-tenant list filtering (grants, challenges, grant_requests)
- Cross-tenant lookup denial (get returns None for wrong tenant)
- Cross-tenant mutation denial (revoke/approve/deny fail for wrong tenant)
- Audit event tenant context storage and filtering
- Dual-mode hash chain integrity (legacy events, tenant events, mixed)
- Operator tenant context (field, to_dict, auth payload)
- Admin-token dev tenant binding
- Legacy backfill default isolation
- Health/readiness endpoints have no tenant data
- Workspace_id reserved (nullable, not enforced)
- Audit event tenant propagation through grant_request workflows
- Documentation artifacts exist and have correct claims
- Scope guards: no false production claims

## Next Steps

- **GL-200C**: Workspace enforcement — `workspace_id` NOT NULL, workspace-scoped query filters
- **GL-200D**: Admin-plane isolation — per-tenant operator management, tenant provisioning API
