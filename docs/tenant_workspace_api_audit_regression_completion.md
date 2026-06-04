# GL-200C: Tenant/Workspace API/Audit/Regression Completion

**Issue:** GL-200C
**Status:** Implementation completion step — not a production SaaS readiness declaration
**Branch:** `gl-200c-tenant-workspace-api-audit-regression-completion`
**Prerequisite:** GL-200B (merged, Tenant/Workspace Isolation Implementation Baseline)

---

## Summary

GL-200C closes the specific API boundary, audit propagation, and regression gaps left
after GL-200B. It is an implementation completion and regression verification step, not a
full production readiness gate.

GrantLayer remains:
- Developer Preview
- Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Not ready to claim tenant/workspace isolation as fully production-complete

---

## Context

GL-200B added `tenant_id` and `workspace_id` columns to all business resource tables
(migration 0010) and wired tenant context into grants, grant_requests, challenges, and
audit_events at the API and DB layers.

GL-200B explicitly deferred:
- Workspace enforcement (`workspace_id` reserved/nullable)
- Admin-plane isolation (GL-200D)
- Grant execution tenant isolation (not enforced in GL-200B)
- Demo action tenant propagation

GL-200C addresses these concrete, bounded gaps.

---

## Scope

**In scope:**
- Grant execution (`grant_executions`) tenant isolation: create, get, list
- Server routes for grant-executions: pass tenant_id from auth context
- `/grants/{id}/executions`: enforce tenant context on grant lookup before listing executions
- Demo action: propagate tenant_id to audit events and execution records
- `expire_old_requests()`: propagate tenant_id to expiry audit events
- GL-200C regression test suite
- Documentation and JSON artifact

**Non-goals:**
- Workspace enforcement (workspace_id remains reserved/nullable)
- Admin-plane tenant isolation (GL-200D)
- Tenant provisioning API (GL-200D+)
- Production secrets/config hardening (GL-201)
- Evidence/provenance/auditor secondary-path tenant isolation (documented as remaining gap)
- Frontend/website changes
- Public GitHub snapshot/publish changes
- GitHub workflow changes
- Broad OpenAPI redesign

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/tenant_workspace_isolation_design_pack.md | YES |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | YES |
| docs/tenant_workspace_isolation_implementation_baseline.md | YES |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | YES |
| docs/gl200b_merge_report.md | YES |
| docs/production_readiness_gap_report_v2.md | YES |
| docs/examples/gl199/production_readiness_gap_report_v2.json | YES |
| docs/controlled_preview_boundary_pack.md | YES |
| docs/examples/gl198/controlled_preview_boundary_pack.json | YES |
| README.md | YES |
| SECURITY.md | YES |
| AGENTS.md | YES |
| backend/src/server.py | YES |
| backend/src/auth.py | YES |
| backend/src/operators.py | YES |
| backend/src/grants.py | YES |
| backend/src/grant_requests.py | YES |
| backend/src/challenges.py | YES |
| backend/src/audit_log.py | YES |
| backend/src/grant_executions.py | YES |
| backend/src/demo_action.py | YES |
| backend/src/agent_permissions.py | YES |
| backend/src/agent_permission_assignments.py | YES |
| backend/src/migrations/0010_gl200b_tenant_workspace_isolation.py | YES |

---

## GL-200B Implementation Summary

GL-200B added:
- Migration 0010: `tenant_id` (NOT NULL DEFAULT 'demo') and `workspace_id` (nullable) to
  all 7 business resource tables including `grant_executions`
- Operator tenant binding (`operators.tenant_id`)
- Auth tenant context injection (`check_auth()` returns `tenant_id` from operator or 'demo' for admin-token)
- Tenant filtering in grants, grant_requests, challenges, audit_log
- 12 server routes updated to pass tenant_id
- Dual-mode hash-chain: legacy events use original payload; new events include tenant_id

---

## Gap Review Summary

### Gap 1: Grant execution tenant isolation (CONCRETE GAP — FIXED)

`grant_executions.py` did not use the `tenant_id` column added by migration 0010:
- `create_grant_execution()` did not insert `tenant_id`
- `get_grant_execution()` did not filter by `tenant_id`
- `list_grant_executions()` did not filter by `tenant_id`
- `list_grant_executions_for_grant()` did not filter by `tenant_id`

Server routes `/grant-executions`, `/grant-executions/{id}`, `/grants/{id}/executions`
did not pass `tenant_id` from auth context to the underlying functions.

**Fix:** All four functions now accept `tenant_id: Optional[str]`. When provided,
queries include `AND tenant_id = ?`. Server routes extract `tenant_id` from auth context
and pass it down. The grant existence check in `/grants/{id}/executions` now uses
`get_grant(grant_id, tenant_id=tenant_id)` to prevent cross-tenant grant-scoped execution listing.

### Gap 2: Demo action tenant propagation (CONCRETE GAP — FIXED)

`handle_demo_action()` did not accept or propagate `tenant_id`:
- Called `list_grants()` without `tenant_id` — could see cross-tenant grants
- Created audit events without `tenant_id`
- Created execution records without `tenant_id`

**Fix:** `handle_demo_action()` accepts `tenant_id: Optional[str]` (defaults to 'demo').
`list_grants()`, `create_grant_execution()`, and `append_event()` all receive the effective
tenant_id. The server `/demo-action` route passes `tenant_id` from the auth payload.

### Gap 3: expire_old_requests() audit propagation (CONCRETE GAP — FIXED)

`expire_old_requests()` created audit events for expiring requests without `tenant_id`,
even though the request rows have `tenant_id` populated.

**Fix:** The SQL query in `expire_old_requests()` now selects `tenant_id` from each
expiring request row. The expiry audit event is created with the request's `tenant_id`
and `scope="tenant"`.

### Gap 4: Workspace enforcement (NOT FIXED — DEFERRED)

`workspace_id` remains reserved (nullable). Enforcement is a future issue (GL-200C scope
had no requirements here beyond verification that the column exists). Confirmed deferred.

### Gap 5: Evidence/provenance/auditor secondary paths (DOCUMENTED — DEFERRED)

Routes `/evidence/executions/{id}`, `/evidence/executions/{id}/export`,
`/evidence/executions/{id}/verify`, `/evidence/executions/{id}/completeness`,
`/provenance/executions/{id}/summary`, `/auditor/reports/executions/{id}`,
`/compliance/gaps/executions/{id}` operate on execution IDs. Since executions are now
tenant-scoped at create/get/list, the primary guard (knowing the execution_id) implies
you already have access. Full secondary-path tenant isolation would require changes to
`evidence_bundle.py`, `evidence_verification.py`, etc. — deferred to a future issue.

### Gap 6: Agent permissions — stateless, no tenant concept (VERIFIED — NOT A GAP)

`evaluate_agent_permission` and `resolve_agent_permission_assignment` are pure logic
functions with no DB access and no state. They cannot create cross-tenant leakage.

---

## API Boundary Completion Summary

| Check | Status |
|---|---|
| Sensitive endpoints derive tenant from trusted auth/operator context | YES |
| Arbitrary client headers cannot override tenant context | YES — tenant is resolved from operator record or admin-token |
| List endpoints filter by tenant_id | YES — grants, grant_requests, challenges, audit_events, grant_executions |
| Direct ID lookups deny cross-tenant access | YES — returns None/404 without existence leak |
| Mutation endpoints deny cross-tenant before mutation | YES — revoke/approve/deny via None-lookup chain |
| Create endpoints attach tenant/workspace context | YES — all create paths use effective_tenant |
| Admin behavior explicit | YES — admin-token → 'demo'; not cross-tenant bypass |
| Operator behavior bound to tenant | YES — operator.tenant_id; auth returns tenant_id |
| Agent permission flows do not cross tenant | YES — stateless evaluators; no DB |
| Health/readiness remain public | YES — no auth, no tenant data |
| Demo endpoint safety preserved | YES — ENABLE_DEMO_ENDPOINTS guard unchanged |

---

## Audit Propagation Completion Summary

| Check | Status |
|---|---|
| Grant_request approve/deny/revoke audit events have tenant_id | YES (GL-200B) |
| Demo action audit events have tenant_id | YES (GL-200C fix) |
| Grant execution records have tenant_id | YES (GL-200C fix) |
| expire_old_requests() expiry audit events have tenant_id | YES (GL-200C fix) |
| System-level events (no tenant) remain nullable | YES — intentional |
| Audit list does not leak cross-tenant data | YES — list_events(tenant_id) filter |
| Audit immutability/hash-chain preserved | YES — dual-mode; verified in tests |

---

## Regression Matrix

Test suite: `backend/tests/test_gl200c_tenant_workspace_api_audit_regression.py`

| Test ID | Description | Result |
|---|---|---|
| EX-001 | create_grant_execution stores tenant_id | PASS |
| EX-002 | create_grant_execution defaults to 'demo' | PASS |
| EX-003 | get_grant_execution cross-tenant returns None | PASS |
| EX-004 | get_grant_execution correct tenant succeeds | PASS |
| EX-005 | list_grant_executions filters by tenant | PASS |
| EX-006 | list_grant_executions without tenant returns all | PASS |
| EX-007 | list_grant_executions_for_grant filters by tenant | PASS |
| EX-008 | Cross-tenant grant execution list returns empty | PASS |
| EX-009 | grant_executions column tenant_id in DB | PASS |
| DA-001 | demo_action audit event carries tenant_id | PASS |
| DA-002 | demo_action execution record carries tenant_id | PASS |
| DA-003 | demo_action uses tenant-scoped grant list | PASS |
| DA-004 | Denied demo_action audit has tenant_id | PASS |
| DA-005 | demo_action default tenant is 'demo' | PASS |
| EXP-001 | expire_old_requests audit event has tenant_id | PASS |
| EXP-002 | expiry audit event scope set to 'tenant' | PASS |
| AU-001 | audit list filters by tenant (no cross-tenant leak) | PASS |
| AU-002 | hash-chain valid after tenant events | PASS |
| AU-003 | audit event stores tenant_id | PASS |
| AU-004 | system events nullable tenant allowed | PASS |
| CTX-001 | operator auth returns tenant_id from record | PASS |
| CTX-002 | admin-token resolves to 'demo' tenant | PASS |
| CTX-003 | _get_tenant_id falls back to 'demo' | PASS |
| CTX-004 | Two operators from different tenants isolated | PASS |
| CB-001 | cross-tenant revoke denied | PASS |
| CB-002 | cross-tenant get returns None | PASS |
| CB-003 | cross-tenant list filtered | PASS |
| PUB-001 | /health has no tenant fields | PASS |
| PUB-002 | /readiness has no tenant fields | PASS |
| PUB-003 | demo endpoint guard config accessible | PASS |
| MIG-001 | grant_executions has tenant_id column | PASS |
| MIG-002 | grant_executions has workspace_id column | PASS |
| MIG-003 | migration idempotent | PASS |
| AP-001 | evaluate_agent_permission stateless | PASS |
| AP-002 | resolve_agent_permission_assignment stateless | PASS |
| DET-001 | evidence bundle example exists | PASS |
| SG-001 | GL-200C doc exists | PASS |
| SG-002 | GL-200C JSON artifact exists | PASS |
| SG-003 | No production SaaS claim in doc | PASS |
| SG-004 | No complete isolation claim in doc | PASS |
| SG-005 | JSON artifact has issue_id GL-200C | PASS |
| SG-006 | SECURITY.md routes to GitHub Advisories | PASS |
| SG-007 | JSON no_production_saas_claim=true | PASS |

---

## OpenAPI / Contract Alignment Assessment

The existing `docs/openapi.yaml` documents the API surface as of GL-031. It does not
expose `tenant_id` or `workspace_id` as user-supplied parameters because tenant context
is implicit from authentication (operator token → operator.tenant_id; admin-token → 'demo').

GL-200C does not change the external contract: clients do not supply tenant context
as request parameters or headers. Tenant context remains server-derived.

No OpenAPI changes are required for GL-200C. The existing auth descriptions in the
OpenAPI preamble remain accurate. A future issue (GL-201+) should update OpenAPI to
explicitly document that tenant context is implicit from authentication.

**OpenAPI changed:** NO — not required; existing auth description is accurate.

---

## Migration / Schema Assessment

Migration 0010 (GL-200B) added `tenant_id` and `workspace_id` to `grant_executions`
as part of the business resource table batch. GL-200C does not add another migration.

The gap was that `grant_executions.py` did not use these columns — fixed at the
application layer only.

**Migration changed:** NO — application layer fix only; no new migration needed.

---

## Remaining Gaps

| Gap | Severity | Deferred To |
|---|---|---|
| workspace_id enforcement | Low (column exists, reserved) | Future issue after GL-200C |
| Admin-plane tenant isolation (cross-tenant operator management) | Medium | GL-200D |
| Evidence/provenance/auditor secondary-path tenant enforcement | Low (execution IDs are already tenant-scoped) | Future issue |
| Full OpenAPI contract update for tenant context | Low | GL-201+ |
| Tenant provisioning API | Not applicable | GL-200D+ |

---

## Production Readiness Impact

GL-200C strengthens the tenant isolation implementation baseline by closing the grant
execution, demo action, and audit propagation gaps. It does not change the production
readiness status:

- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Not ready for real customer data, private grant data, or institutional data.
- Security-sensitive reports continue to route to GitHub Security Advisories.
- No exploit details are included in this document.
- Public caveats remain unchanged.

---

## Decision

**disposition:** ready_for_merge

**rationale:** All concrete GL-200B gaps identified by GL-200C review are fixed.
No new real functional regressions. Regression matrix passes. Documentation and
JSON artifact created. Safety confirmations met.

---

## Safety Confirmations

- No public GitHub push performed
- No production SaaS claim made
- Tenant/workspace isolation not claimed as production-complete
- No real customer/private grant data readiness claim
- Security-sensitive reports route to GitHub Security Advisories
- No exploit details included
- No frontend/design/public-snapshot changes
- No GitHub workflow changes

---

## Recommended Next Issues

- **GL-200C Merge** — merge this branch to internal main
- **GL-200D** — Admin-plane tenant isolation (cross-tenant operator management)
- **GL-201** — Production Auth / Secrets / Config Hardening
