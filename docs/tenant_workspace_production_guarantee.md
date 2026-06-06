# GL-215 - Tenant / Workspace Production Guarantee

**Issue ID:** GL-215
**Title:** Tenant / Workspace Production Guarantee
**Status:** Internal / Developer Preview

GL-215 is tenant/workspace production hardening, not a production SaaS
readiness declaration.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Controlled Preview remains synthetic/demo data only. Production
SaaS remains no-go unless a later production go/no-go gate changes that. Real
customer data, private grant data, and institutional data remain no-go. Official
SDK/package remains no-go. Compliance certification remains no-go. GDPR, SOC2,
ISO, and enterprise readiness are not claimed. Ephemeral live PostgreSQL
validation passed, but production PostgreSQL readiness remains no-go.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.

Unrelated website-design/import files were excluded from GL-215. No
`website-design/` content or similarly named website-design import/report files
are included in this change.

---

## Context

GL-213 identified tenant/workspace isolation as a remaining production blocker
after the GL-200A/B/C tenant baseline and GL-206/GL-214 admin/operator hardening.
GL-215 reviews that model and implements only narrow changes that materially
reduce direct-ID tenant bypass risk without replacing the tenancy model.

## Scope

GL-215 covers tenant derivation, workspace deferral, route-level filtering,
cross-tenant lookup and mutation denial, audit propagation, admin/operator
tenant correctness, unsafe override prevention, and documentation of remaining
production blockers.

## Non-Goals

GL-215 does not implement a broad multi-tenant SaaS platform, workspace UI,
tenant provisioning API, broad RBAC or policy engine rewrite, broad schema or
persistence rewrite, external identity provider, public SDK/package behavior,
public publish, production deployment, compliance certification, or real-data
readiness.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_readiness_gap_report_v4.md | Yes |
| docs/examples/gl213/production_readiness_gap_report_v4.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/public_external_review_readiness_gate_pack.md | Yes |
| docs/examples/gl212/public_external_review_readiness_gate_pack.json | Yes |
| docs/live_postgres_validation_execution_gl206b.md | Yes |
| docs/examples/gl206b/live_postgres_validation_execution_gl206b.json | Yes |
| docs/openapi.yaml | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/server.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/grant_requests.py | Yes |
| backend/src/grants.py | Yes |
| backend/src/evidence_verification.py | Yes |
| backend/src/demo_action.py | Yes |
| backend/tests/ | Yes |
| scripts/ops/ | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |

## Current Tenant/Workspace State Summary

Tenant isolation is application-layer enforced for primary business resources.
Operator authentication derives `tenant_id` from the stored operator row.
Legacy admin-token mode derives the demo tenant server-side. Clients cannot
override tenant context through request headers. Primary grant, grant-request,
challenge, audit-event, and grant-execution list/get/mutation routes filter by
the authenticated tenant and return 404/empty results for cross-tenant direct-ID
lookups.

`workspace_id` exists in the schema as a reserved nullable field. It is not a
production-enforced workspace boundary. Missing or null workspace ID remains
explicitly deferred and does not grant broader tenant access because current
runtime authorization is tenant-scoped, not workspace-scoped.

## Production Tenant/Workspace Gap Assessment

| Area | Current state | GL-215 assessment |
|---|---|---|
| tenant_id derivation | Server-derived from operator/admin auth | Preserved |
| workspace_id derivation | Reserved/nullable, not enforced | Remaining production blocker |
| admin/operator tenant context | Operator tenant stored; admin control plane can assign tenant | Preserved, not production-complete |
| route-level enforcement | Primary routes tenant-filtered | Strengthened for secondary execution-derived routes |
| cross-tenant lookup denial | Primary direct IDs return 404/None | Extended to evidence/provenance/auditor/compliance execution routes |
| cross-tenant mutation denial | Primary mutations tenant-filtered | Demo tamper and evidence verify now have tenant pre-checks |
| audit propagation | Tenant audit events for business and operator actions | Preserved |
| unsafe override prevention | Caller tenant/workspace fields ignored except admin operator creation | Preserved |
| demo/synthetic safety | Demo endpoints synthetic-only and guarded | Demo tamper now tenant-scoped |
| health/readiness | Public, no tenant data | Preserved |
| OpenAPI/API contract | No behavior shape change; 404 denial remains | No OpenAPI change required |
| migration/schema | No schema change | Workspace enforcement remains deferred |

## Implemented Hardening Summary

GL-215 implements two narrow changes:

1. Execution-derived secondary routes now check that the requested
   `execution_id` belongs to the authenticated tenant before building evidence,
   export, verification, provenance, auditor, evidence-completeness, or
   compliance-gap responses.
2. The demo tamper grant helper and route now pass server-derived tenant context
   so a demo operator cannot tamper with another tenant's grant by direct ID.

No migration, schema refactor, new tenancy framework, public publish behavior,
GitHub workflow change, snapshot script change, package metadata, SDK package,
production credential, external hostname, or analytics/tracking integration was
added.

## Tenant ID Derivation Model

Operator mode derives `tenant_id` from the authenticated operator database row.
Admin-token mode derives `tenant_id="demo"` for legacy/demo compatibility.
Business routes use that server-derived value when calling storage helpers.
Request headers and ordinary business request bodies do not establish tenant
context.

## Workspace ID Derivation/Deferred Model

`workspace_id` remains reserved and nullable. GL-215 does not enforce workspace
membership, workspace-scoped queries, workspace assignment, or workspace
provisioning. Null workspace values are accepted only as the current deferred
model and are not a signal for cross-tenant access.

## Cross-Tenant Lookup Denial Behavior

Primary direct-ID resource lookups remain tenant-filtered. GL-215 extends the
same denial behavior to secondary execution-derived routes by requiring
`get_grant_execution(execution_id, tenant_id=caller_tenant)` to succeed before
any secondary builder runs. Wrong-tenant execution IDs return safe 404 responses.

## Cross-Tenant Mutation Denial Behavior

Primary mutations remain tenant-filtered. GL-215 adds tenant scoping to the demo
tamper route and prevents wrong-tenant evidence verification from mutating
verification metadata by checking execution ownership first.

## Admin/Operator Tenant Boundary

Operators remain tenant-bound. Operator tokens cannot override their tenant.
Admin-only operator creation can assign a tenant ID for an operator, but that
admin control plane is still not a full production tenant-management system.
GL-214 role allowlist and durable audit-chain behavior are preserved.

## Route Protection and Filtering Model

Health and readiness remain public and do not include tenant data. Primary
business routes require auth and filter by server-derived tenant. Secondary
execution-derived routes now require auth and a tenant-visible execution before
serving or mutating derived evidence/report state.

## Audit Tenant/Workspace Propagation

Audit events continue to include safe tenant context where applicable and avoid
raw tokens, token hashes, authorization headers, DSNs, private keys, credentials,
customer data, private grant data, and institutional data. Workspace remains
nullable/deferred.

## Unsafe Override Prevention

Business route tenant/workspace fields supplied by callers are ignored rather
than used for tenant derivation. Unsupported workspace override remains
non-operative. The exception is admin-only operator creation, where `tenantId`
is an explicit admin assignment for the new operator and not a self-service
operator override.

## OpenAPI/API Contract Implications

No OpenAPI change was required. GL-215 preserves existing route shapes and
denial semantics. The strengthened behavior is stricter 404 denial before
secondary execution-derived responses.

## Migration/Schema Implications

No migration or schema change was made. Production workspace enforcement,
database row-level security, tenant provisioning, and stronger workspace
constraints remain future work.

## Production-Readiness Impact

GL-215 materially reduces the tenant/workspace production blocker by closing a
direct-ID secondary-route gap and tenant-scoping demo tamper mutation. It does
not make tenant/workspace isolation production-complete and does not change the
Production SaaS no-go decision.

## Controlled-Preview Impact

Controlled Preview may continue only with strict boundaries and synthetic/demo
data. GL-215 improves safety for controlled technical review but does not expand
the allowed data boundary.

## Remaining Tenant/Workspace Blockers

- Workspace enforcement remains deferred and nullable.
- No tenant provisioning or workspace-management API exists.
- No database row-level security is implemented.
- Admin control plane is not a full production tenant-management system.
- Secondary evidence storage helpers are not independently tenant-parameterized;
  HTTP routes now guard them first, but deeper helper-level enforcement remains
  future work.
- Agent permission assignment persistence remains outside a production
  tenant/workspace governance model.
- Production data governance, legal review, incident operations, and compliance
  gates remain incomplete.

## Risk Register

| Risk | Severity | Status |
|---|---|---|
| Workspace-null records cannot prove workspace isolation | P0 | Blocker remains |
| Application-layer-only tenant filtering can regress if future routes omit context | P0 | Reduced by GL-215 tests, not eliminated |
| Admin plane can assign tenants but lacks production tenant lifecycle governance | P0 | Blocker remains |
| Secondary helpers rely on route pre-checks | P1 | Reduced, deeper helper enforcement recommended |
| Controlled-preview claims could be overread as production readiness | P1 | Guarded by docs/tests |

## Findings

GL-215 found no need for a broad tenancy rewrite. It found two narrow route-level
hardening opportunities and implemented them. Remaining production blockers are
documented instead of overbuilt.

## Decision

`ready_for_merge`

## Decision Rationale

The change is bounded, testable, and materially reduces a real cross-tenant
direct-ID risk without changing schema, replacing the tenant model, or
weakening Developer Preview / Controlled Preview boundaries.

## Safety Confirmations

- GL-215 is tenant/workspace production hardening, not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Production SaaS remains no-go.
- Real customer data, private grant data, and institutional data remain no-go.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Compliance certification remains no-go.
- Ephemeral live PostgreSQL validation passed but production PostgreSQL readiness remains no-go.
- Tenant/workspace isolation is materially improved only to the extent implemented and tested here.
- Controlled Preview remains synthetic/demo data only.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- No public publish, public snapshot/export, public GitHub push, visibility change, package publishing, package metadata, GitHub workflow change, or snapshot publish script change was performed.
- Unrelated website-design/import files were excluded.

## Recommended Next Issues

- GL-215 Merge if ready.
- GL-216 Production Operations Hardening Pack.
- GL-217 Production Go/No-Go v5.
