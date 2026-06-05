# GL-203B — OpenAPI / API Contract Cleanup

**Issue ID:** GL-203B
**Branch:** `gl-203b-openapi-api-contract-cleanup`
**Status:** Internal / Developer Preview

---

## Context

GL-200A, GL-200B, GL-200C, GL-201, GL-202, and GL-203 are merged internally.
GL-203 concluded that `docs/openapi.yaml` is substantially stale relative to
the actual implementation (OpenAPI at GL-031 state; implementation at GL-202+)
and that OpenAPI / API contract cleanup is required before any SDK work.

GL-203B is a documentation and contract cleanup issue. It does not change API
behavior, backend implementation, or publish anything.

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation baseline implemented but not production-complete
- No official SDK/package is claimed or published

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included.

---

## Scope

GL-203B covers:
- Updating `docs/openapi.yaml` version from "0.31.0-rc" to "0.203b.0-developer-preview"
- Updating OpenAPI info description to remove stale GL-031 references
- Adding Developer Preview / Controlled Preview caveats to OpenAPI description
- Documenting tenant context as server-derived (not client-supplied) in OpenAPI
- Documenting workspace_id as reserved/nullable/deferred in OpenAPI
- Documenting X-Correlation-ID request/response header
- Documenting cross-tenant denial semantics (404/empty, no existence leak)
- Fixing GET /grant-requests security to reflect both auth modes accurately
- Updating /operators/me response schema to include actual fields (active, tenantId)
- Updating AuditEvent schema to include GL-200B tenant/workspace fields
- Adding missing ComplianceReadinessSummary schema (referenced but undefined)
- Updating security scheme descriptions to note tenant context derivation
- Adding contract tests for the updated OpenAPI and claim boundaries

## Non-Goals

GL-203B is not:
- API behavior implementation
- Backend/src changes
- SDK implementation
- Package publishing
- Production SaaS readiness declaration
- Public publish, GitHub push, or visibility change
- Frontend, website, or design work
- Migration or DB/schema changes
- Dependency changes
- Changing stale tenant isolation claim in AGENTS.md/llms.txt/llms-full.txt
  (those files have many existing test dependencies on specific claim wording;
  updating them requires coordinated test changes beyond GL-203B scope)

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|----------|
| docs/api_contract_sdk_packaging_decision.md | Yes |
| docs/examples/gl203/api_contract_sdk_packaging_decision.json | Yes |
| docs/openapi.yaml (pre-update) | Yes |
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
| docs/api_sdk_agent_value_decision_pack.md | Yes |
| docs/examples/gl197/api_sdk_agent_value_decision_pack.json | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/server.py | Yes (contract review only) |
| backend/src/auth.py | Yes (contract review only) |
| backend/src/operators.py | Yes (contract review only) |
| backend/src/grants.py | Yes (contract review only) |
| backend/src/grant_requests.py | Yes (contract review only) |
| backend/src/challenges.py | Yes (contract review only) |
| backend/src/audit_log.py | Yes (contract review only) |
| backend/src/db.py | Yes (contract review only) |
| backend/src/models.py | Yes (contract review only) |
| backend/src/agent_permissions.py | Yes (contract review only) |
| backend/src/agent_permission_assignments.py | Yes (contract review only) |
| backend/src/compliance_readiness.py | Yes (contract review only) |

---

## OpenAPI Drift Summary

The OpenAPI document was at version `"0.31.0-rc"` (GL-031 state) while the
implementation was at GL-202+. Key drift areas identified:

| Drift Area | Severity | Resolution |
|---|---|---|
| Version "0.31.0-rc" vs actual GL-202+ state | Medium | Updated to "0.203b.0-developer-preview" |
| Info description references GL-031 and GL-030 stale baseline | Medium | Updated with GL-203B Developer Preview caveats |
| No tenant context documentation | Medium | Added: server-derived, not client-supplied |
| No workspace_id documentation | Low | Added: reserved/nullable/deferred |
| No X-Correlation-ID documentation | Low | Added to info description |
| No cross-tenant denial semantics documented | Medium | Added to info description and endpoint descriptions |
| GET /grant-requests shows OperatorToken only; impl allows both | Low | Fixed to LegacyAdminToken or OperatorToken |
| /operators/me response schema missing active and tenantId fields | Low | Added both fields |
| AuditEvent schema missing GL-200B tenant_id, workspace_id, scope, row_hash, prev_hash | Medium | Added all fields |
| ComplianceReadinessSummary schema referenced but undefined | High | Added complete schema definition |
| Security scheme descriptions missing tenant context notes | Low | Updated both scheme descriptions |
| No Developer Preview caveat in OpenAPI info | Medium | Added to info description |

---

## Endpoint / Auth Boundary Cleanup Summary

| Endpoint | Pre-GL-203B | Post-GL-203B |
|---|---|---|
| GET /health, GET /readiness | Public (correct) | Public (unchanged) |
| GET / (dashboard) | No auth (correct) | No auth (unchanged) |
| GET/POST /grants | LegacyAdminToken or OperatorToken (correct) | Unchanged |
| GET /grants/{id} | LegacyAdminToken or OperatorToken (correct) | Unchanged |
| POST /grants/{id}/revoke | LegacyAdminToken or OperatorToken (correct) | Unchanged |
| GET /audit-events | LegacyAdminToken or OperatorToken (correct) | Unchanged |
| GET/POST /challenges | LegacyAdminToken or OperatorToken (correct) | Unchanged |
| GET /operators/me | Both (correct; returns 404 if operator model disabled) | Schema updated |
| GET /grant-requests | OperatorToken only (INACCURATE; impl allows both) | Fixed to both |
| POST /grant-requests | OperatorToken (correct; impl gates on ENABLE_OPERATOR_MODEL) | Unchanged |
| All evidence/provenance/audit endpoints | Both (correct) | Unchanged |
| All agent-permission endpoints | Both (correct) | Unchanged |
| POST /demo-action | Both (correct; auth always required) | Unchanged |
| POST /demo/tamper-grant/{id} | Both (correct; 403 if ENABLE_DEMO_ENDPOINTS=false) | Unchanged |

**Assessment:** Auth boundary is sound. One auth mode mismatch corrected
(GET /grant-requests). No auth bypass gap exists.

---

## Tenant/Workspace Contract Cleanup Summary

The following tenant/workspace documentation was added to the OpenAPI:

1. **Info description**: Explicit statement that `tenant_id` is always server-derived
   from authentication. Clients cannot supply or override it. Cross-tenant ID lookups
   return HTTP 404; list endpoints return an empty list without leaking existence.

2. **workspace_id**: Documented as reserved, nullable, and not currently enforced.
   workspace_id is present in the data model but workspace-level isolation is
   deferred to a future release.

3. **Security scheme descriptions**: Both `LegacyAdminToken` and `OperatorToken`
   schemes now explicitly state how tenant context is derived server-side.

4. **AuditEvent schema**: Added `tenant_id`, `workspace_id`, `scope` fields reflecting
   GL-200B implementation. Added documentation that `tenant_id` is null for pre-migration
   or system-scope events.

**Stale claim in AGENTS.md / llms.txt / llms-full.txt:**
These files still state "Tenant isolation is not implemented." This is now
inaccurate since GL-200A/B/C implemented the baseline. However, updating these
files would break numerous existing test assertions that check for this exact phrase.
Coordinated correction with simultaneous test updates is required — this is tracked
as a remaining gap for a subsequent cleanup issue.

---

## Auth/Config Contract Cleanup Summary

The OpenAPI info description and security scheme descriptions were updated to
document:

1. **Production-mode fail-closed startup**: In staging/production runtime mode,
   placeholder/weak admin tokens are rejected at startup (GL-201).

2. **Admin token safety**: Validated via constant-time HMAC comparison. Tenant
   context is bound to "demo" for legacy mode.

3. **Operator token safety**: Validated via PBKDF2-HMAC-SHA256 (600,000 iterations)
   with SHA-256 lookup-hash pre-filter. Tokens issued once at operator creation,
   not retrievable afterward. Tenant context derived from operator record.

4. **Security headers**: Documented in info description that all responses include
   X-Content-Type-Options, X-Frame-Options, Cache-Control: no-store,
   Content-Security-Policy.

No secret values appear in OpenAPI examples. Auth contract verified clean.

---

## Audit/Error Response Contract Cleanup Summary

1. **AuditEvent schema**: Updated to add GL-200B fields (`tenant_id`, `workspace_id`,
   `scope`) and hash-chain fields (`row_hash`, `prev_hash`).

2. **Error contract**: GL-030 additive error shape retained in info description.
   All documented 400/401/403/404/409/422/500 responses continue to reference
   the `ErrorResponse` schema.

3. **No exploit details**: No cross-tenant existence details, internal state
   details, or exploit guidance included.

---

## SDK-Readiness Impact

GL-203B brings the OpenAPI to a state where SDK prototype work could begin:
- The API contract is now accurately documented
- Tenant context handling is documented
- Auth requirements are accurate
- Schema gaps (ComplianceReadinessSummary) are filled
- Missing fields (AuditEvent GL-200B fields, operator tenantId) are documented

**Remaining blockers before SDK prototype (GL-203C):**
- workspace_id enforcement not yet implemented (deferred)
- Admin-plane tenant isolation (GL-200D) deferred
- PostgreSQL not live-validated (GL-204)
- Stale tenant isolation claims in AGENTS.md/llms.txt require coordinated correction

No SDK code is implemented in GL-203B. No package publishing metadata is created.

---

## Files Changed

| File | Type | Change |
|---|---|---|
| docs/openapi.yaml | Updated | Version, description, tenant docs, schemas |
| docs/openapi_api_contract_cleanup.md | Created | This document |
| docs/examples/gl203b/openapi_api_contract_cleanup.json | Created | JSON artifact |
| backend/tests/test_gl203b_openapi_api_contract_cleanup.py | Created | Contract tests |

---

## Remaining Gaps

1. **Stale tenant isolation claims in AGENTS.md, llms.txt, llms-full.txt, README.md,
   SECURITY.md**: These files still say "Tenant isolation is not implemented."
   The baseline (GL-200A/B/C) is implemented. Updating these requires simultaneous
   test updates (many existing tests assert on exact claim wording). Deferred to
   next cleanup issue.

2. **workspace_id enforcement**: Still deferred. workspace_id column is reserved
   and nullable. Full workspace isolation requires a separate implementation issue.

3. **Admin-plane tenant isolation (GL-200D)**: Cross-tenant operator management
   isolation is deferred. Do not promote to production multi-tenant use until
   GL-200D is complete.

4. **PostgreSQL live validation**: Code paths are hardened (GL-202) but not
   live-validated against a real PostgreSQL instance. Blocked until GL-204.

5. **Secondary-path tenant enforcement**: Evidence/provenance/auditor routes
   derive tenant context from execution IDs which are already tenant-scoped at
   creation. Full secondary-path enforcement is deferred.

6. **X-Correlation-ID formal header spec**: Currently documented in description only.
   Future improvement: add as a formal `parameters` entry on all endpoints.

---

## Production Readiness Impact

GL-203B is a documentation and contract cleanup issue. It does not change
production readiness.

After GL-203B, production readiness posture:

| Area | Status |
|---|---|
| API contract documentation | Aligned with GL-202+ implementation |
| Auth/secrets/config | Hardened (GL-201); not full production SaaS |
| Persistence/migration | SQLite ready for Developer Preview; PostgreSQL not live-validated |
| Tenant/workspace isolation | Baseline implemented (GL-200A/B/C); not production-complete |
| SDK/package | Developer-preview adjacent; not published; not official |
| Public claims | Bounded by controlled preview; some stale claims remain in non-OpenAPI docs |
| Follow-up needed | Stale claim correction, GL-203C (SDK), GL-204 (production ops) |

GrantLayer **remains** Developer Preview / Controlled Preview with strict boundaries.

---

## Decision

**dispose: ready_for_merge**

**Decision: OpenAPI / API contract cleanup complete. Proceed to GL-203C (SDK Prototype)
only after GL-203B is merged. GL-204 (Production Ops) should follow as a parallel track.**

---

## Decision Rationale

1. The OpenAPI drift assessment confirmed significant but non-critical gaps: the
   documented endpoints were functionally accurate; what was missing was cross-cutting
   behavior (tenant context, workspace_id, newer schema fields).
2. The missing ComplianceReadinessSummary schema was the highest-severity gap (a broken
   $ref in the document).
3. The GET /grant-requests auth mode mismatch was minor but corrected for accuracy.
4. The AuditEvent schema GL-200B fields (tenant_id, workspace_id, scope, row_hash,
   prev_hash) were missing and are now added.
5. The stale tenant isolation claims in AGENTS.md/llms.txt/llms-full.txt require
   coordinated test updates and are deferred.
6. No API behavior was changed. No backend/src files were modified.
7. After GL-203B, the OpenAPI is suitable as a basis for GL-203C SDK prototype work.

---

## Safety Confirmations

- No production SaaS readiness claim made.
- Tenant/workspace isolation not overclaimed as production-complete.
- No real customer/private grant data readiness claimed.
- Security-sensitive reports route to GitHub Security Advisories (per SECURITY.md).
- No exploit details included in this document or in the updated OpenAPI.
- No real secrets included in this document, tests, or JSON artifact.
- GL-201 auth/secrets/config hardening fully preserved.
- GL-200A/B/C tenant/workspace isolation fully preserved.
- GL-202 migration/persistence readiness fully preserved.
- No official SDK/package claimed or published.
- No package publishing metadata created.
- No backend/src changes.
- No API behavior changes.
- No migrations/DB/schema changes.
- No dependency changes.
- No SDK/package implementation.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No public publish or visibility change.
- No force push.
- No Paperclip references or status updates.

---

## Recommended Next Issues

- **GL-203B Merge** — merge `gl-203b-openapi-api-contract-cleanup` to internal main
  after validation.
- **GL-203C — SDK Prototype / Packaging Boundary** — only after GL-203B merge; design
  internal SDK prototype against the aligned contract; define packaging boundary tests;
  decide on experimental public SDK timeline.
- **GL-204 — Production Ops / Go-No-Go v3** — live PostgreSQL validation, backup/restore
  minimum drill, observability baseline, go/no-go decision for first external controlled
  pilot. Can proceed in parallel with GL-203C.
- **Stale claim correction issue** — update AGENTS.md, llms.txt, llms-full.txt,
  README.md tenant isolation claim with coordinated test updates.
