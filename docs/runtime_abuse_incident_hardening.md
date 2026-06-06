# GL-208 - Runtime / Abuse / Incident Hardening

**Issue ID:** GL-208
**Title:** Runtime / Abuse / Incident Hardening - Production IAM Baseline
**Status:** Internal / Developer Preview

GL-208 is a runtime/IAM/abuse/incident hardening baseline. It is not a
Production SaaS readiness declaration.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Production SaaS is no-go. Real customer data, private grant data,
and institutional data remain no-go. The internal SDK prototype is not an
official SDK or package. Live PostgreSQL production readiness is not claimed.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.

## Context

GL-200A through GL-207 are merged internally. GL-200 through GL-206 implemented
tenant/workspace and admin/operator baselines, while GL-207 corrected stale
claim wording. Those baselines reduce controlled-preview risk but remain
production-incomplete.

## Scope

- Runtime mode assessment and fail-closed review.
- Production IAM baseline assessment for admin/operator bearer-token behavior.
- Abuse/rate-limit boundary assessment.
- Incident/security reporting baseline.
- Observability and security-event preservation.
- Claim-safe documentation, JSON artifact, and regression tests.

## Non-Goals

- Production SaaS readiness declaration.
- Production IAM completeness, OAuth/JWT/SSO, or broad auth-provider rewrite.
- Full RBAC/policy engine.
- Production deployment system.
- Production-grade DDoS protection.
- Complete incident-management platform.
- Complete production observability stack.
- Frontend, website, design, GitHub workflow, package-publishing, or SDK
  packaging changes.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/claim_safety_controlled_preview_boundary.md | Yes |
| docs/examples/gl207/claim_safety_controlled_preview_boundary.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/live_postgres_backup_observability_baseline.md | Yes |
| docs/examples/gl205/live_postgres_backup_observability_baseline.json | Yes |
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
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
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| backend/src/server.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/config.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/structured_logging.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/migrations/* | Yes |
| backend/tests/* | Yes |
| scripts/* | Yes |
| examples/* | Yes |

## Current State Summary

Runtime configuration already includes production-like fail-closed checks from
GL-201. Admin authentication uses a configured bearer token with constant-time
comparison. Operator authentication uses PBKDF2-SHA256 token hashes with a
lookup hash, active-row filtering, and expiry checks. Admin/operator control
plane routes from GL-206 are admin-only and return safe fields. Tenant context
is server-derived from auth and is not accepted from arbitrary tenant override
headers.

An in-process deterministic rate limiter exists for `auth` and `api` groups.
Structured logging and correlation ID helpers exist, with sensitive field
redaction. These are baselines for controlled preview only.

## Runtime Mode Assessment

| Mode | Assessment |
|---|---|
| local | Allows developer defaults; not production-like. |
| test | Allows deterministic tests and local tokens. |
| demo | Requires admin token by default; still not production. |
| staging | Production-like; unsafe config must fail closed. |
| production | Production-like; unsafe config must fail closed. |
| controlled-preview | Operational posture only, bounded to synthetic/demo data; not a separate production runtime mode. |

Production-like startup rejects missing admin-token enforcement, missing admin
token, missing challenge enforcement, enabled demo endpoints, placeholder or
short admin tokens, and unsafe bootstrap operator tokens. Startup/config errors
do not include raw secret values.

## Runtime Hardening Summary

No broad runtime rewrite was added. Existing GL-201 behavior was verified and
locked with GL-208 tests. Public health/readiness behavior remains public.
Protected resource, demo-action, demo tamper, and admin/operator routes remain
behind their existing guards. CORS remains exact-match allowlist only.

## Production IAM Baseline Assessment

The production IAM baseline is not complete production IAM. It is a controlled
preview bearer-token baseline:

- Admin token: `GRANTLAYER_ADMIN_TOKEN`, constant-time comparison, fail-closed
  when required.
- Operator token: PBKDF2-SHA256 storage, SHA-256 lookup hash, bearer-token
  auth, active-row filtering, token expiry handling.
- Admin/operator distinction: admin-only routes call the admin-token guard;
  operator bearer tokens cannot access admin routes.
- Operator tenant binding: tenant comes from the operator DB row.
- Revoked/inactive operator behavior: inactive operators are denied.

## Admin/Operator IAM Boundary

Admin routes:

- `GET /admin/operators`
- `GET /admin/operators/{id}`
- `POST /admin/operators`
- `POST /admin/operators/{id}/revoke`

These routes require a valid admin bearer token. Operator bearer tokens are not
accepted on admin routes. List/read responses exclude raw tokens, `token_hash`,
`token_lookup_hash`, and `lookup_hash`. The create response may return a raw
token once by design; list/read/revoke paths do not return it.

## Tenant/Workspace Preservation Assessment

GL-208 does not weaken GL-200. Tenant context remains server-derived from the
authenticated operator or the legacy admin `demo` binding. Arbitrary tenant
override headers such as `X-Tenant-ID` remain unsupported. Workspace enforcement
remains reserved/deferred and is not overclaimed.

## Abuse/Rate-Limit Boundary Assessment

GrantLayer already has `backend/src/rate_limiter.py`, a deterministic
in-process sliding-window limiter. It is used by server route groups:

- `auth`: challenge creation, demo-action, demo tamper, and auth-sensitive
  request paths.
- `api`: protected resource, evidence, admin/operator control-plane, and
  higher-risk mutation/read paths.

The limiter is local, in-memory, and testable. It is not production-grade DDoS
protection, does not coordinate across processes, and does not replace edge
rate limiting, WAF controls, or abuse-monitoring infrastructure.

## Incident/Security Reporting Baseline

Security-sensitive reports route to GitHub Security Advisories. Public issues
and public docs must not include exploit details.

Incident categories:

- Admin authentication failure or suspected admin token exposure.
- Operator authentication failure, expiry, revocation failure, or suspicious
  repeated invalid-token attempts.
- Rate-limit/abuse events.
- Runtime config startup failure in a production-like mode.
- Migration failure or migration idempotency failure.
- Backup/restore drill failure.
- Audit hash-chain, evidence integrity, or provenance integrity anomaly.
- Controlled-preview boundary violation, including attempted real
  customer/private grant/institutional data use.

Severity classes:

- P0: suspected credential exposure, audit/evidence integrity compromise,
  production-like startup bypass, or controlled-preview real/private data use.
- P1: repeated auth failures, rate-limit events, migration failure, or
  backup/restore drill failure.
- P2: documentation drift, stale claim, or non-sensitive controlled-preview
  process issue.

There is no real customer/private data process because real data remains no-go.
This incident response baseline is not a complete production incident program.

## Observability/Security-Event Baseline

Existing code supports correlation IDs, safe structured logs, auth failure
events, request rejection events, rate-limit events, and admin/operator
control-plane events. GL-205 already documented migration, backup/restore, and
runtime signal categories.

This is not a complete production observability stack: no external metrics
backend, alerting, distributed tracing, SIEM integration, or production log
retention controls are claimed.

## Logging/Secret-Safety Model

Logs, audit events, docs, and responses must not include:

- Raw Authorization headers.
- Raw admin/operator tokens.
- `token_hash`, `token_lookup_hash`, or lookup hash values in responses.
- DSNs, passwords, passphrases, private keys, signing keys, or API keys.
- Raw request bodies.
- Evidence payloads.
- Real customer data, private grant data, or institutional data.

Safe event fields are bounded to event type, method, normalized path, status
code, reason code, and correlation/request IDs.

## Implementation Summary

GL-208 adds this documentation artifact, a JSON artifact, and a focused test
suite. No backend source change was required because the narrow runtime,
IAM, rate-limit, and logging protections already exist and are better preserved
by regression tests than by a broad rewrite.

## Controlled-Preview Impact

Controlled Preview remains allowed only with strict boundaries and
synthetic/demo data. GL-208 improves review traceability for runtime, IAM,
abuse, incident, and observability baselines. It does not expand data
eligibility or production usage.

## Production Readiness Impact

Production SaaS remains no-go. Real customer/private grant/institutional data
remains no-go. Official SDK/package remains no-go. Live PostgreSQL production
claim remains no-go. Production IAM baseline is not complete production IAM.
Abuse/rate-limit baseline is not production-grade DDoS protection. Incident
response baseline is not a complete production incident program. Observability
baseline is not a complete production observability stack.

## Remaining Blockers

- Production IAM: OAuth/JWT/SSO, rotation workflows, central identity, and
  policy governance remain deferred.
- Workspace enforcement remains deferred.
- Live PostgreSQL validation has not been executed.
- Production deployment hardening remains deferred.
- Production observability, alerting, and log retention remain deferred.
- Production backup/DR automation remains deferred.
- Production-grade abuse controls and edge protection remain deferred.
- Complete incident-management process remains deferred.

## Risk Register

| ID | Risk | Mitigation |
|---|---|---|
| R-001 | Admin token exposure grants broad control-plane access. | Keep admin token out of logs/responses; rotate by environment change; move to production IAM later. |
| R-002 | In-memory rate limiter does not cover multi-process or edge attacks. | Document as baseline only; add production edge controls later. |
| R-003 | Operator tenant misassignment requires revoke/recreate. | Admin can revoke; production tenant admin workflows remain deferred. |
| R-004 | Incident process is too lightweight for production. | Treat as baseline; create production incident program later. |
| R-005 | Observability lacks production alerting. | GL-205/GL-208 document gap; implement stack later. |

## Findings

- Existing rate limiter/helper is deterministic and covered by GL-208 tests.
- Existing admin/operator routes remain protected.
- Operator token cannot access admin-only routes.
- Revoked/inactive operator remains denied.
- Tenant context remains server-derived.
- Raw token/hash leakage is prevented in safe admin list/read responses.
- No OpenAPI, migration, frontend, workflow, SDK package, or website/design
  change was required.

## Decision

`runtime_abuse_incident_hardening_baseline_approved_with_gaps`

## Decision Rationale

GL-208 closes the review and regression gap for runtime, IAM, abuse,
incident, and security-event baselines without broad rewrites. The existing
backend has narrow controls appropriate for Developer Preview / Controlled
Preview with strict boundaries. Remaining production blockers are explicit and
must not be treated as solved.

## Safety Confirmations

- GL-208 is not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict
  boundaries.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Live PostgreSQL production claim remains no-go.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- Production IAM baseline is not complete production IAM.
- Abuse/rate-limit baseline is not production-grade DDoS protection.
- Incident response baseline is not a complete production incident program.
- Observability baseline is not a complete production observability stack.
- Tenant/workspace isolation baseline is not overclaimed as
  production-complete.
- Admin/operator control plane baseline is not overclaimed as
  production-complete.
- Unrelated untracked website files were excluded from GL-208.

## Recommended Next Issues

- GL-208 Merge if ready.
- GL-209 Data Governance & Audit Operations.
- GL-206B Live PostgreSQL Validation Execution when ephemeral PostgreSQL is
  available.
