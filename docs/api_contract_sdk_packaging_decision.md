# GL-203 — API Contract / SDK Packaging Decision

**Issue ID:** GL-203
**Branch:** `gl-203-api-contract-sdk-packaging-decision`
**Status:** Internal / Developer Preview

---

## Context

GL-200A, GL-200B, GL-200C, GL-201, and GL-202 are merged internally. The GL-200 tenant/workspace isolation block, the GL-201 production auth/secrets/config hardening, and the GL-202 persistence/PostgreSQL/migration readiness block are all complete.

GL-203 is a decision and review pack. It does not implement an SDK, publish a package, change API behavior, or declare production SaaS readiness.

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation is not overclaimed as production-complete
- No official SDK/package is claimed or published

Security-sensitive reports route to GitHub Security Advisories. No exploit details are included. No real secrets are included.

---

## Scope

GL-203 covers:
- Review of current API contract and OpenAPI alignment after GL-200 through GL-202
- Endpoint/auth boundary assessment
- Tenant/workspace contract implications
- Auth/config contract implications
- Persistence/migration contract implications
- SDK/package options comparison and recommendation
- Agent integration boundary review
- Public claim safety review
- Roadmap split for follow-up implementation issues

## Non-Goals

GL-203 is not:
- SDK implementation
- Package publishing
- API behavior implementation
- Production SaaS readiness declaration
- Public publish, GitHub push, or visibility change
- Website, frontend, or design work
- Auth, secrets, or config implementation
- Persistence or migration implementation
- Tenant/workspace implementation expansion

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
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
| docs/public_safety_scanner_claim_consistency_gate.md | Yes |
| docs/public_smoke_matrix_pack.md | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
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
| backend/src/migrations/* | Yes (contract review only) |
| sdk/python/grantlayer_client.py | Yes (stat only) |
| sdk/python/README.md | Yes |

---

## Current API Contract Summary

GrantLayer exposes an HTTP/REST API served by a stdlib HTTPServer (BaseHTTPRequestHandler). There is no framework dependency. Two auth modes exist and are controlled by `ENABLE_OPERATOR_MODEL`:

**Auth modes:**
- **Legacy mode** (`ENABLE_OPERATOR_MODEL=false`): `Authorization: Bearer <admin-token>` via constant-time `hmac.compare_digest`.
- **Operator mode** (`ENABLE_OPERATOR_MODEL=true`): `Authorization: Bearer <operator-token>` via PBKDF2-HMAC-SHA256 (600,000 iterations) with a SHA-256 lookup-hash pre-filter.

**Tenant context:** Derived entirely server-side. In operator mode, `tenant_id` comes from the operator record. In admin-token mode, `tenant_id` is bound to `"demo"`. Clients cannot supply or override `tenant_id` via headers, path parameters, or request bodies.

**Endpoint categories (post GL-202):**

| Category | Endpoints | Auth |
|---|---|---|
| Public/health | GET /health, GET /readiness, GET / | None |
| Core resource (both auth modes) | GET/POST /grants, GET /grants/{id}, POST /grants/{id}/revoke, GET /audit-events, GET/POST /challenges | LegacyAdminToken or OperatorToken |
| Operator-mode-only | /grant-requests (CRUD), /grant-executions (CRUD), /grants/{id}/executions, /operators (CRUD), /operators/me | OperatorToken only |
| Evidence/provenance/audit chain | /evidence/executions/{id} and sub-paths, /provenance/executions/{id}/summary, /auditor/reports/executions/{id}, /compliance/* | LegacyAdminToken or OperatorToken |
| Agent permission evaluation | /agent-permissions/* | LegacyAdminToken or OperatorToken |
| Approval lifecycle | /approval-rules/evaluate, /approval-requests/{id}/* | LegacyAdminToken or OperatorToken |
| Demo/tamper | POST /demo/tamper-grant/{id} | Blocked unless ENABLE_DEMO_ENDPOINTS=true; returns 403 by default |
| Demo action | POST /demo-action | Auth required regardless of demo flag |

**Error contract:** All error responses follow the GL-030 additive shape:
```json
{"error": "human-readable", "errorCode": "machine-readable", "reason": "detail"}
```

**Security headers on all responses:** X-Content-Type-Options, X-Frame-Options, Cache-Control: no-store, Content-Security-Policy.

**CORS:** Exact-match whitelist only. No wildcard. No reflection of arbitrary origins.

**Rate limiting:** Separate auth and API rate limiters (configurable via env vars).

---

## OpenAPI Alignment Assessment

The OpenAPI document (`docs/openapi.yaml`) is at version `"0.31.0-rc"`, describing the GL-031 state. The actual implementation is now at GL-202.

### What the OpenAPI correctly documents

- GET /health, GET /readiness (public, no auth) — accurate
- GET / (dashboard) — accurate
- GET/POST /grants, GET /grants/{id}, POST /grants/{id}/revoke — accurate shape
- GET /audit-events — accurate
- GET/POST /grant-requests, GET /grant-requests/{id}, POST approve/deny — accurate
- GET /grant-executions, POST /grant-executions, GET /grant-executions/{id} — accurate
- GET /grants/{id}/executions — accurate
- GET/POST /operators, GET /operators/me — accurate
- GET /evidence/executions/{id} and sub-paths — accurate
- GET /challenges, POST /challenges — accurate
- SecuritySchemes (LegacyAdminToken: Bearer, OperatorToken: Bearer) — accurate
- Error response shape (GL-030 additive contract) — accurate

### What the OpenAPI does not document (gaps to address in GL-203B)

- **Implicit tenant context from auth:** OpenAPI does not state that tenant_id is always derived server-side. Clients might incorrectly infer tenant override is possible.
- **workspace_id reserved/nullable:** Not documented in any schema or description.
- **Tenant isolation behavior:** Cross-tenant denial (404/empty list) is not described.
- **Production-mode startup behavior:** GL-201 fail-closed startup checks are not reflected.
- **Many newer endpoints:** Agent permission profiles, approval lifecycle, compliance readiness, provenance v2, institutional auditor export, policy requirements — all added after GL-031; not in OpenAPI.
- **Demo endpoint explicit guard:** /demo/tamper-grant/{id} behavior (403 when flag is off) is not documented.
- **Version mismatch:** Version is "0.31.0-rc" against actual state GL-202+.
- **Grant execution tenant isolation (GL-200C):** Not reflected.
- **Correlation-ID header:** X-Correlation-ID request/response header is not documented.

### Assessment

The OpenAPI is not severely misleading about auth requirements or request/response shapes for the documented endpoints. It is substantially incomplete: significant new surface and cross-cutting behaviors (tenant context, workspace_id, newer endpoints) are absent.

**Recommendation:** Defer comprehensive OpenAPI cleanup to GL-203B. Do not change `docs/openapi.yaml` in GL-203.

---

## Endpoint/Auth Boundary Assessment

| Check | Status |
|---|---|
| Public endpoints (health, readiness) require no auth | VERIFIED — GET /health, GET /readiness are fully public |
| Mutating endpoints require auth | VERIFIED — all mutating endpoints check auth before proceeding |
| Admin-token auth fails closed on missing/blank/placeholder token | VERIFIED — GL-201 hardening; startup rejects placeholder tokens in production-like mode |
| Operator auth uses constant-time comparison with PBKDF2 hashing | VERIFIED — 600,000 PBKDF2 iterations, SHA-256 lookup hash pre-filter |
| tenant_id is always server-derived, never client-supplied | VERIFIED — extracted from operator record or bound to 'demo' for admin-token |
| Cross-tenant lookup denial (no existence leak) | VERIFIED — returns None/404 for ID lookups, empty list for list endpoints |
| Demo tamper endpoint blocked by default | VERIFIED — returns 403 unless ENABLE_DEMO_ENDPOINTS=true |
| /demo-action requires auth (not gated by demo flag) | VERIFIED — auth check runs regardless |
| Rate limiting applied to auth and API paths | VERIFIED — separate limiters configurable via env |
| Security headers on all responses | VERIFIED — X-Content-Type-Options, X-Frame-Options, Cache-Control, CSP |

**Assessment: Auth boundary is sound for Developer Preview. No auth bypass gap was found.**

---

## Tenant/Workspace Contract Implications

### Current state (post GL-200A/B/C)

- `tenant_id` is present on all business resource tables (grants, grant_requests, challenges, grant_executions, evidence_archives, audit_events, operators).
- Tenant context is always server-derived from the auth token. Clients cannot inject or override it.
- All list and ID-lookup endpoints filter by `tenant_id` when derived from auth.
- Cross-tenant mutation (revoke/approve/deny) is blocked via None-lookup chain.
- Audit events carry `tenant_id` from the authenticated context for all new events.
- Pre-migration audit events keep `tenant_id = NULL` (fail-closed; not associated with any tenant).
- `workspace_id` is reserved (nullable), not enforced.

### Implications for OpenAPI contract

- The OpenAPI must be updated (in GL-203B) to document that `tenant_id` is implicit from authentication, not a client-supplied parameter.
- The OpenAPI must document that arbitrary tenant override headers are not supported.
- Cross-tenant denial semantics (403/404 without existence leak) should be documented.
- `workspace_id` should be described as reserved/nullable/deferred.

### What must be completed before public caveats change

- Workspace enforcement (`workspace_id`) must be implemented before workspace isolation can be claimed.
- Admin-plane tenant isolation (GL-200D) must be implemented before cross-tenant operator management can be claimed safe.
- Secondary-path tenant enforcement (evidence/provenance/auditor routes) must be completed.
- Full production-grade database-level row security (RLS) would be needed before production-SaaS multi-tenant claims.

### Stale claims in public docs (finding — to address in GL-203B or narrow follow-up)

README.md, AGENTS.md, SECURITY.md, and llms.txt currently state: **"Tenant isolation is not implemented."**

This is now inaccurate. GL-200A/B/C implemented a tenant isolation baseline: tenant_id is stored and enforced on all business tables via application-layer filtering. However, the isolation is not production-complete (workspace not enforced, secondary paths deferred, no DB-level RLS, admin-plane isolation deferred).

**Recommended correction (not made in GL-203):** Update these claims to: "Tenant isolation baseline implemented but not production-complete. workspace_id is reserved. Full production multi-tenancy requires additional hardening gates." This correction should be part of GL-203B or a narrow companion issue.

---

## Auth/Config Contract Implications

### Production-mode fail-closed behavior (GL-201)

In `staging` or `production` runtime mode:
- Placeholder/demo/weak admin tokens are rejected at startup (server won't start).
- Admin token minimum length is enforced (16 characters).
- Bootstrap operator token is validated.
- CORS localhost origins trigger a startup warning.
- No raw token value ever appears in error messages, logs, or startup output.

### Admin token safety (verified)

- Constant-time comparison via `hmac.compare_digest`.
- Token never leaked in response bodies, logs, or errors.
- Missing token + require=true → 403 (fail-closed).
- Wrong token → 403 (no token value in response).

### Operator token safety (verified)

- PBKDF2-HMAC-SHA256 (600,000 iterations) with random salt.
- SHA-256 lookup hash for O(1) pre-filter before expensive PBKDF2 check.
- Raw token returned once on creation; not retrievable afterward.
- `to_dict()` exposes only safe fields (operatorId, name, role, active, tenantId).
- Expired token → 401 operator_token_expired (reason code only, no token value).

### Implications for OpenAPI contract

- OpenAPI should document that placeholder/weak tokens are rejected in production-like mode (startup behavior).
- OpenAPI should document operator token lifecycle (single issuance, never retrievable).
- No secret values should appear in OpenAPI examples — currently confirmed clean.

### Assessment: Auth/config contract is sound. No changes needed in GL-203.

---

## Persistence/Migration Contract Implications

### SQLite readiness (post GL-202)

- WAL journal mode and foreign keys enabled on every connection.
- 10 migrations, deterministic order, idempotent.
- Migration runner wraps `apply_fn` with version-specific error context.
- `list_pending_migrations()` available for dry-run inspection.
- Audit immutability triggers (SQLite) protect audit_events from UPDATE/DELETE.
- Hash-chain verification is read-only and safe across pre-migration and post-migration events.

**Assessment: READY for controlled SQLite usage within Developer Preview.**

### PostgreSQL readiness (post GL-202)

- Code paths support PostgreSQL via `GRANTLAYER_DATABASE_URL`.
- `executescript` comment-stripping bug fixed (GL-202).
- Connection pool (SimpleConnectionPool) is code-complete but not live-tested.
- No live PostgreSQL test infrastructure available.
- `pg_stat_activity` health probe requires at least `pg_monitor` role.

**Assessment: PostgreSQL code paths are substantially hardened but NOT validated end-to-end without a live instance. PostgreSQL production deployment requires live integration testing before use.**

### API claims impact

- Live PostgreSQL support CANNOT be claimed as production-ready without live validation.
- SQLite mode is suitable for Developer Preview / Controlled Preview.
- Backup/restore/DR is not implemented (no automated rollback for schema changes).
- Pre-migration database snapshot required before any migration in a staging/production deployment.

---

## SDK/Package Options

The current state: `sdk/python/grantlayer_client.py` is a 113-line minimal HTTP client wrapper. It is developer-preview only, not published to PyPI or any package registry. No package metadata for publication exists.

### Option A: No SDK/package; examples only

Keep the focus on runnable examples (`examples/*.py`) and documentation. The minimal SDK in `sdk/python/` continues as developer-adjacent code with no publication or official support claim.

- **Pros:** Zero commitment overhead; no breaking change burden; fits current API contract gap.
- **Cons:** Developer experience is limited to raw HTTP calls; no typed interface.
- **When appropriate:** If the API contract is still unstable or if OpenAPI cleanup hasn't been done.

### Option B: Experimental local SDK prototype later, not published

Develop a more complete internal SDK prototype after GL-203B (contract alignment), but keep it unpublished and clearly marked experimental.

- **Pros:** Improves developer experience; allows testing packaging boundaries safely.
- **Cons:** Requires GL-203B contract work first; engineering time investment.
- **When appropriate:** After GL-203B delivers a stable, documented API contract.

### Option C: Public experimental SDK/package later with clear preview caveats

Publish an experimental SDK to PyPI (or similar) with a `0.x.y.dev` version and explicit Developer Preview / Breaking Changes Expected notices.

- **Pros:** Increases discoverability and developer adoption.
- **Cons:** Creates public API surface that must be maintained; premature before contract stability; OpenAPI contract must be aligned first; packaging tests must exist.
- **When appropriate:** After GL-203B AND GL-203C (packaging boundary verification).

### Option D: Official SDK/package now

Publish an official SDK with a stable versioned release.

- **Pros:** Strong signal of maturity.
- **Cons:** The API contract has not been comprehensively documented or aligned (OpenAPI is at GL-031, state is GL-202+). Publishing an official SDK before contract alignment would create untenable maintenance burden and false maturity signals. Explicitly prohibited by GL-203 scope.
- **Assessment: REJECTED. Not appropriate now. Do not claim or publish.**

### Option E: Defer SDK until OpenAPI/contract cleanup and packaging tests

Make an explicit decision to defer all SDK/packaging work until GL-203B closes the OpenAPI/contract gap, then revisit.

- **Pros:** Responsible sequencing; protects against premature commitment.
- **Cons:** Delays SDK-related developer experience improvements.
- **Assessment: Correct sequencing. Aligns with GL-197 API-first conclusion.**

---

## Selected SDK/Package Recommendation

**Recommendation: Option E — Defer SDK until OpenAPI/contract cleanup (GL-203B), then assess Option B.**

Rationale:
1. The OpenAPI contract is at GL-031 (0.31.0-rc) while the implementation is at GL-202+. Significant surface is undocumented (tenant context, workspace_id, newer endpoints, 30+ endpoints added after GL-031).
2. Publishing any SDK before the contract is stable creates an SDK that diverges from actual behavior.
3. The existing `sdk/python/grantlayer_client.py` covers the health/readiness/grants/audit surface adequately for Developer Preview.
4. GL-197 concluded `api_first_agent_examples_now_sdk_later` — that recommendation remains valid and is reinforced by the contract gaps found in GL-203.
5. An official SDK/package is explicitly not claimed. No package publishing metadata exists. This status must be preserved.

**After GL-203B completes OpenAPI/contract alignment:**
- Revisit Option B (experimental local SDK prototype) as GL-203C.
- Only proceed to Option C (public experimental SDK) after GL-203C verifies packaging boundaries.
- Only consider Option D (official SDK) after a production-ready API contract is verified, which is well beyond the current roadmap.

---

## Agent Integration Implications

### Current agent integration surface

- `AGENTS.md` is the primary agent entry point — accurate, safe, Developer Preview caveats present.
- `llms.txt` — concise summary, safe, accurate caveats.
- `llms-full.txt` — detailed repository map, safe areas and forbidden areas documented.
- `docs/agent_integration_manifest.json` — machine-readable metadata.
- `docs/public_agent_api_walkthrough_refresh.md` — public agent/API walkthrough.
- Agent permission evaluation endpoints (`/agent-permissions/*`) are stateless evaluators — no DB access, no cross-tenant risk.

### Assessment

The agent integration documentation is safe for Developer Preview. The agent entry points correctly document:
- Developer Preview caveats
- No real secrets in examples
- No real customer data
- Not production SaaS
- No tenant isolation claim (though this specific claim is now stale — see Tenant/Workspace section above)

### Stale claim in agent docs (finding)

`AGENTS.md` states: "Tenant isolation is not implemented." This is now a stale claim as of GL-200A/B/C. The baseline was implemented. The claim should be updated to "Tenant isolation baseline implemented but not production-complete" in GL-203B or a narrow companion task. GL-203 does not change `AGENTS.md`.

### Agent integration boundary decision

The agent integration boundaries in AGENTS.md and llms.txt remain safe as-is for GL-203. No changes to these files are required in GL-203. The stale tenant isolation claim is a documentation accuracy issue, not a security boundary issue.

---

## Public Claim Boundary

### Allowed public claims

GrantLayer MAY claim the following publicly:

1. **Developer Preview** — local evaluation and controlled pilot posture.
2. **Controlled Preview with strict boundaries** — no real customer data, no private grant data, no shared multi-tenant infrastructure.
3. **API-first** — REST/HTTP API, no SDK required to integrate.
4. **Deterministic local examples** — `examples/first_verifiable_output.py` and `examples/grant_lifecycle_evidence_bundle.py` produce deterministic, verified output with no backend required.
5. **Grant lifecycle evidence bundle** — verifiable output from the grant lifecycle flow with cryptographic hashes.
6. **Tenant/workspace isolation baseline improved** (not production-complete) — GL-200A/B/C implemented baseline tenant_id tracking and filtering on all business tables; workspace_id is reserved; full production multi-tenancy requires additional gates.
7. **Production auth/secrets/config hardening improved** (not production SaaS) — GL-201 hardened placeholder token rejection, startup fail-closed behavior, and secret leakage prevention.
8. **Persistence/migration readiness improved** (not production data readiness) — GL-202 hardened migration runner, idempotency, and dry-run inspection; PostgreSQL not live-validated.
9. **Open source (Apache 2.0)** — LICENSE file present since GL-153.
10. **Agent-friendly API surface** — agent permission evaluation, audit chain, evidence bundles accessible via REST.
11. **Audit tamper-evidence** — hash-chain verification on audit_events, immutability triggers (SQLite and PostgreSQL).
12. **Minimal SDK available for developer evaluation** — `sdk/python/grantlayer_client.py`, developer-preview only, not published, not official.

### Prohibited public claims

GrantLayer MUST NOT claim the following:

1. **Production SaaS ready** — no production-grade ops, no multi-tenant SaaS deployment.
2. **Ready for real customer data** — examples use synthetic identifiers only; no real customer data is safe to store.
3. **Ready for private grant or institutional data** — no production hardening for data confidentiality.
4. **Official SDK/package available** — `sdk/python/grantlayer_client.py` is developer-preview adjacent code, not a published package.
5. **Complete tenant/workspace isolation production guarantee** — baseline implemented; workspace not enforced; secondary paths deferred; no DB-level RLS.
6. **Live PostgreSQL production readiness** — PostgreSQL code paths are hardened but not live-validated.
7. **Enterprise-ready platform** — no enterprise ops, SLAs, or support guarantees.
8. **Compliance-ready platform** — no regulatory compliance certification or audit.
9. **Workspace enforcement complete** — `workspace_id` is reserved and nullable.
10. **Admin-plane multi-tenant isolation complete** — GL-200D (cross-tenant operator management) is deferred.

---

## Follow-Up Implementation Split

### GL-203B — OpenAPI / API Contract Cleanup (recommended first)

Scope:
- Update `docs/openapi.yaml` version from "0.31.0-rc" to reflect actual state.
- Document implicit tenant context (server-derived from auth, not client-supplied).
- Document workspace_id as reserved/nullable/deferred.
- Document cross-tenant denial semantics (404/empty without existence leak).
- Add missing endpoints (agent permissions, approval lifecycle, compliance readiness, provenance v2, institutional auditor export, policy requirements, demo endpoints).
- Document X-Correlation-ID request/response header.
- Update stale claims in README.md, AGENTS.md, SECURITY.md, llms.txt, llms-full.txt about "Tenant isolation is not implemented" → "Tenant isolation baseline implemented but not production-complete."
- Add OpenAPI tests for alignment.

### GL-203C — SDK Prototype / Packaging Boundary (only if GL-203B supports it)

Scope:
- Only proceed after GL-203B delivers stable contract documentation.
- Design an internal SDK prototype against the aligned contract.
- Define packaging boundary tests (not PyPI publication).
- Decide on experimental public SDK timeline (Option C).

### GL-204 — Production Ops / Go-No-Go v3

Scope:
- Deployment configuration and runtime safety gates.
- Backup/restore minimum drill.
- Live PostgreSQL validation.
- Observability/monitoring baseline.
- Go/no-go decision for first external controlled pilot.

### GL-205+ — Deployment, Runtime, Backup, Observability, Admin Plane

Scope:
- Admin-plane tenant isolation (GL-200D equivalent).
- workspace_id enforcement.
- Production-grade indexes and schema finalization.
- Backup/restore automation.
- Incident response runbook.

---

## Production Readiness Impact

GL-203 is a review/decision/test artifact only. It does not change production readiness.

After GL-203, the production readiness posture is:

| Area | Status |
|---|---|
| API contract | Functional; OpenAPI documentation substantially behind (GL-203B needed) |
| Auth/secrets/config | Hardened for Developer Preview (GL-201); not full production SaaS |
| Persistence/migration | SQLite ready for Developer Preview; PostgreSQL not live-validated |
| Tenant/workspace isolation | Baseline implemented (GL-200A/B/C); not production-complete |
| SDK/package | Developer-preview adjacent; not published; not official |
| Public claims | Bounded by controlled preview; stale claims in public docs need GL-203B correction |
| Follow-up needed | GL-203B (OpenAPI/contract), GL-204 (production ops), GL-205+ (admin-plane/workspace) |

GrantLayer **remains** Developer Preview / Controlled Preview with strict boundaries.

---

## Risk Register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Stale "not implemented" tenant isolation claims in README/AGENTS/llms mislead developers about actual baseline | Low-Medium | Document in GL-203; correct in GL-203B or narrow companion task |
| R2 | OpenAPI version "0.31.0-rc" vs actual state GL-202+ creates contract confusion | Medium | Document gap; defer correction to GL-203B |
| R3 | PostgreSQL not live-validated; deployment risk if used in production without testing | High | Document; block PostgreSQL production deployment until GL-204 live validation |
| R4 | Premature SDK publication before contract stability creates breaking-change burden | High | Defer all SDK publication to after GL-203B; Option E selected |
| R5 | workspace_id deferred enforcement creates future migration complexity | Low-Medium | Tracked in GL-200C/GL-203B; column reserved and nullable |
| R6 | Secondary-path tenant enforcement (evidence/provenance) deferred | Low-Medium | Execution IDs are already tenant-scoped at create; direct access requires known ID |
| R7 | Admin-plane isolation (cross-tenant operator management) deferred (GL-200D) | Medium | Documented; do not promote to production multi-tenant use until GL-200D |

---

## Decision

**dispose: ready_for_merge**

**Decision: Defer SDK/packaging; proceed to GL-203B for OpenAPI/contract cleanup.**

The GL-203 analysis confirms:
1. The API contract is functional and the auth boundary is sound for Developer Preview.
2. The OpenAPI document is substantially incomplete relative to the current implementation state.
3. No SDK/package should be published or claimed as official until after GL-203B.
4. All allowed public claims are bounded and safe; prohibited claims are clearly defined.
5. The agent integration surface is safe with the noted stale-claim finding.
6. GL-203B is the required next step before any SDK or packaging work.

---

## Decision Rationale

- GL-197 concluded `api_first_agent_examples_now_sdk_later`. GL-203 reinforces this: the API contract gap is larger than expected (OpenAPI at GL-031, implementation at GL-202+). No SDK publication is appropriate until the contract is documented.
- GL-201 and GL-202 successfully hardened auth/secrets/config and persistence/migration. These are preserved. No regression.
- The tenant/workspace baseline (GL-200A/B/C) is functionally correct but not yet reflected in public documentation — this is a documentation gap, not a security gap.
- The SDK decision (Option E → B) is the correct responsible sequencing given the contract gap.
- Production SaaS readiness is not affected by this decision; GrantLayer remains Developer Preview.

---

## Safety Confirmations

- No production SaaS readiness claim made.
- Tenant/workspace isolation not overclaimed as production-complete.
- No real customer/private grant data readiness claimed.
- Security-sensitive reports must route to GitHub Security Advisories (per SECURITY.md).
- No exploit details included in this document.
- No real secrets included in this document, tests, or JSON artifact.
- GL-201 auth/secrets/config hardening is fully preserved.
- GL-200A/B/C tenant/workspace isolation is fully preserved.
- GL-202 migration/persistence readiness is fully preserved.
- No official SDK/package is claimed or published.
- No package publishing metadata exists or is created.
- No backend/src changes.
- No API behavior changes.
- No OpenAPI changes (cleanup deferred to GL-203B).
- No frontend/website/design changes.
- No GitHub workflow changes.
- No public publish or visibility change.
- No force push.
- No Paperclip references or status updates.

---

## Recommended Next Issues

- **GL-203 Merge** — merge `gl-203-api-contract-sdk-packaging-decision` to internal main after validation.
- **GL-203B — OpenAPI / API Contract Cleanup** — update OpenAPI version, document tenant context as implicit, add missing endpoints, correct stale tenant isolation claims in README/AGENTS/llms.
- **GL-203C — SDK Prototype / Packaging Boundary** — only after GL-203B; design internal SDK prototype against aligned contract; define packaging boundary tests; decide experimental public SDK timeline.
- **GL-204 — Production Ops / Go-No-Go v3** — live PostgreSQL validation, backup/restore minimum drill, observability baseline, go/no-go decision for first external controlled pilot.
- **GL-205+ — Deployment / Runtime / Backup / Observability / Admin-Plane** — workspace_id enforcement, admin-plane tenant isolation, production-grade indexes, incident response runbook.
