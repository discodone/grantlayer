# GL-221 - Workspace Enforcement & Final Go/No-Go v6

**Issue ID:** GL-221
**Title:** Workspace Enforcement & Final Go/No-Go v6
**Branch:** `gl-221-workspace-enforcement-final-go-no-go-v6`
**Status:** Internal / Developer Preview

GL-221 is workspace enforcement assessment and final Go/No-Go v6, not an
automatic production release.
GL-221 is not an automatic production release.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Production SaaS remains NO-GO. Real customer data, private grant
data, and institutional data remain NO-GO. Official SDK/package remains NO-GO.
Compliance certification remains NO-GO. Live PostgreSQL production readiness
remains NO-GO. Public snapshot/export and public website publish remain
separate-gate only.
Developer Preview / Controlled Preview with strict boundaries remains the
current posture.
Public snapshot/export and public website publish remain separate-gate only.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.
No exploit details are included.
No real secrets are included.
No real customer/private data is used.

Unrelated website-design/import files were excluded from GL-221.

## Context

GL-218 preserved public/export safety boundaries. GL-219 documented identity and
access hardening without adding production OAuth/OIDC/JWT readiness. GL-220
documented runtime/infrastructure hardening without adding production
infrastructure. GL-215 remains the authoritative tenant/workspace runtime
baseline: tenant context is server-derived and enforced at application level;
`workspace_id` is reserved/nullable and not production-enforced.
workspace_id is reserved/nullable and not production-enforced.

The known GL-220 post-merge full suite baseline is 8988 tests, 43 failures, 3
errors, 253 skipped, and 0 real regressions. GL-221 does not treat stale scope
guards or claim scanners as production evidence.

## Scope

- Assess current workspace enforcement state and remaining gaps.
- Preserve GL-214 IAM/operator-control, GL-215 tenant/workspace, GL-218
  public/export, GL-219 identity/access, and GL-220 runtime/infrastructure
  boundaries.
- Add local documentation, machine-readable artifact, focused tests, and a
  local-only dry-run/plan gate.
- Produce final readiness matrix v6.

## Non-Goals

GL-221 does not implement a full workspace RBAC engine, policy engine rewrite,
schema migration, broad persistence rewrite, frontend, external workspace
provider, production deployment, public snapshot/export, public publish,
official package release, production OAuth/OIDC/JWT rollout, or live PostgreSQL
production gate.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/production_runtime_infrastructure_hardening_pack.md | Yes |
| docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json | Yes |
| docs/production_identity_access_hardening_pack.md | Yes |
| docs/examples/gl219/production_identity_access_hardening_pack.json | Yes |
| docs/public_external_review_export_safety_pack.md | Yes |
| docs/examples/gl218/public_external_review_export_safety_pack.json | Yes |
| docs/production_operations_hardening_pack.md | Yes |
| docs/examples/gl216/production_operations_hardening_pack.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/tenant_workspace_data_model_design.md | Yes |
| docs/examples/gl144/tenant_workspace_data_model_design.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/openapi.yaml | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/server.py | Yes |
| backend/src/config.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/identity_access.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/grants.py | Yes |
| backend/src/grant_requests.py | Yes |
| backend/tests/ | Yes |
| scripts/ops/gl216_production_operations_gate.py | Yes |
| scripts/ops/gl218_public_export_safety_scan.py | Yes |
| scripts/ops/gl219_identity_access_gate.py | Yes |
| scripts/ops/gl220_runtime_infrastructure_gate.py | Yes |
| scripts/ops/gl205_live_postgres_validation.py | Yes |
| scripts/ops/gl205_backup_restore_drill.py | Yes |
| scripts/ops/gl209_audit_export_check.py | Yes |
| scripts/run-full-backend-suite.sh | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |

## Current Workspace Enforcement State Summary

Tenant isolation is application-layer enforced for primary business resources.
Operator authentication derives `tenant_id` from the stored operator row.
Legacy admin-token mode derives `tenant_id="demo"` server-side. Business routes
do not trust arbitrary tenant headers or ordinary body fields for tenant
context.

`workspace_id` exists in schema/model surfaces as a reserved nullable field.
It is not a production workspace boundary. Current server routes do not derive a
trusted workspace from auth, do not maintain workspace membership, and do not
perform workspace-scoped filtering.

## Workspace Enforcement Gap Assessment

| Area | Current state | Remaining gap |
|---|---|---|
| workspace_id derivation | Reserved/nullable; no trusted runtime derivation | No server-derived workspace identity or membership model |
| tenant_id / workspace_id relationship | Tenant is enforced; workspace is not linked to tenant | No tenant-owned workspace table or lifecycle |
| server-derived workspace context | None beyond nullable field propagation in audit model | No authenticated workspace context |
| unsafe header/body override prevention | Tenant override ignored on business routes; workspace body override is non-operative | No explicit production workspace override rejection because workspace is deferred |
| cross-workspace lookup denial | Not claimed | Requires workspace-scoped resource ownership and query filters |
| cross-workspace mutation denial | Not claimed | Requires workspace-scoped ownership and mutation predicates |
| grants/evidence/provenance/audit/compliance propagation | Tenant propagates through routes and audit events; workspace remains nullable | Evidence/provenance/archive tables need ownership propagation before real data |
| demo/synthetic flows | Tenant-scoped and synthetic/demo bounded | No production workspace semantics |
| admin/operator routes | Admin can assign tenant for operators; workspace assignment not exposed | No production workspace admin/member workflow |
| controlled external review | Synthetic/demo only, separate export gate | No public/export workspace readiness claim |

## Implemented Hardening Summary

No backend source hardening was implemented in GL-221. The inspected gaps require
workspace identity, ownership, persistence, and authorization design work that is
too broad for this issue and would require schema/migration and RBAC decisions.
GL-221 adds documentation, JSON evidence, a local-only dry-run/plan gate, and
tests that lock the conservative no-go posture.

## workspace_id Derivation/Trust Model

There is currently no trusted `workspace_id` derivation model. Clients do not
establish workspace trust through headers or normal body fields. A future gate
must derive workspace context from authenticated operator membership or a
trusted provider claim after signature, issuer, audience, expiry, and
tenant/workspace mapping validation.

## Tenant/Workspace Relationship Model

Current runtime treats tenant as the enforced boundary and workspace as reserved
metadata. A production model must make every workspace belong to exactly one
tenant and must bind every customer-owned resource to tenant plus workspace.

## Unsafe Workspace Override Prevention

Current business create routes ignore caller-supplied `tenantId`/`workspaceId`
for resource ownership. Because no server-derived workspace context exists,
GL-221 does not add a partial workspace override mechanism. Future work should
reject unsupported workspace override fields once a real workspace model exists.

## Cross-Workspace Lookup Denial Posture

Cross-tenant direct-ID lookup denial exists for primary and GL-215 secondary
execution-derived routes. Cross-workspace lookup denial is not claimed because
resource rows are not workspace-scoped by runtime authorization.

## Cross-Workspace Mutation Denial Posture

Cross-tenant mutation denial exists for primary mutations and demo tamper.
Cross-workspace mutation denial is not claimed. Production SaaS remains blocked
until mutations include workspace ownership predicates and tests.

## Workspace Propagation Into Audit/Evidence/Provenance/Compliance

Audit events have nullable `workspace_id` storage, but current audit append
flows normally carry tenant and scope, not a trusted workspace. Evidence,
provenance, auditor, and compliance builders are protected at HTTP entry points
by tenant-visible execution checks, but their persistence helpers are not a
standalone workspace enforcement boundary.

## Admin/Operator Workspace Boundary

Admin/operator routes preserve tenant assignment and safe audit events. They do
not implement workspace membership, workspace operator assignment, or production
tenant administration. Admin operations are not proof of production workspace
readiness.

## Demo/Synthetic Workspace Boundary

Demo and synthetic flows remain allowed only for Developer Preview / Controlled
Preview. Demo tamper is tenant-scoped after GL-215. No demo flow is approved for
real customer, private grant, or institutional data.

## Controlled External Review Workspace Boundary

Controlled external technical review remains GO with strict boundaries:
synthetic/demo data only, no public export unless a separate explicit gate
approves it, no exploit details, no real secrets, and no production claims.

## Production-Readiness Impact

Workspace enforcement remains a final consolidated blocker before Production
SaaS or real-data use. GL-221 does not remove that blocker.

## Controlled Preview Impact

Developer Preview and controlled technical review can continue because current
tenant-derived controls, claim-safety boundaries, and synthetic/demo data rules
remain intact.

## Final Readiness Matrix v6

| Tier | Decision |
|---|---|
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Snapshot Preparation | CONDITIONAL - separate explicit gate required |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

## Production SaaS Decision

NO-GO. Remaining blockers include workspace enforcement, production IAM,
database/RLS posture, live PostgreSQL readiness, operations ownership,
monitoring/alerting, backup/restore/DR, incident process, and compliance/legal
review.

## Real Customer Data Decision

NO-GO. Real customer data requires workspace enforcement, data governance,
legal/security review, retention/deletion workflows, production IAM, and
production operations evidence.

## Private Grant/Institutional Data Decision

NO-GO. Private grant and institutional data require stronger access controls,
workspace ownership, audit/export governance, and compliance review.

## Controlled External Review Decision

GO with strict boundaries. Review is synthetic/demo only, security-sensitive
reports route to GitHub Security Advisories, and public issue content must not
include exploit details or secrets.

## Public Snapshot/Public Publish Decision

Public snapshot/export remains CONDITIONAL and separate-gate only. Public
website publish remains DEFER / NO-GO unless a later explicit publish gate
approves it.

## Official SDK/Package Decision

NO-GO. The internal/minimal SDK prototype is not an official SDK or package.
No package publishing metadata is added.

## Live PostgreSQL Production Readiness Decision

NO-GO. Prior PostgreSQL validation was ephemeral/synthetic and does not prove a
live production topology, backup, restore, failover, or operations model.

## IAM/Identity Decision After GL-219

Improved but not production-ready. Static admin token and hashed operator-token
model remain controlled-preview controls. External IdP/OAuth/OIDC/JWT
production readiness is not claimed.

## Runtime/Infrastructure Decision After GL-220

Improved documentation and local gate coverage, but no real TLS, reverse proxy,
process supervisor, cloud deployment, monitoring, production secrets, or
production infrastructure readiness is claimed.

## Public/Export Decision After GL-218

Public/export safety boundaries are documented. No public snapshot/export,
public GitHub push, visibility change, or public publish is authorized by
GL-221.

## Remaining P0/P1/P2 Blockers

| Severity | Blocker | Status | Mitigation | Remaining work |
|---|---|---|---|---|
| P0 | Production SaaS readiness | Open | Keep Developer Preview / Controlled Preview only | Complete production IAM, workspace, DB, ops, compliance gates |
| P0 | Real customer/private/institutional data | Open | Synthetic/demo-only boundary | Legal/security/data-governance approval and production controls |
| P0 | Live PostgreSQL production readiness | Open | Ephemeral validation only | Production topology, backups, restore, failover, monitoring |
| P1 | Workspace enforcement | Open | Tenant-scoped app controls preserved | Workspace identity, membership, ownership, query/mutation enforcement |
| P1 | Production IAM | Open | GL-219 fail-closed unsupported IdP config | Real IdP/JWT validator, MFA/SSO, deprovisioning, rotation |
| P1 | Audit/evidence/provenance workspace propagation | Open | Tenant-visible route prechecks | Persisted workspace ownership and export governance |
| P2 | Public snapshot preparation | Conditional | Separate gate required | Candidate export review and approval |
| P2 | Official SDK/package | Open | Keep prototype boundary | Packaging policy, metadata, versioning, support decision |

## Risk Register v6

| Risk | Severity | Status | Mitigation | Remaining work |
|---|---|---|---|---|
| Workspace boundary overclaim | P0 | Open | Explicit no-go language and tests | Implement workspace model and verification |
| Real-data misuse in preview | P0 | Open | Synthetic/demo-only docs and gates | Data governance and legal approval |
| Public/export leakage | P1 | Controlled | GL-218 separate gate and scans | Manual export candidate review |
| Static/admin token production use | P1 | Open | Fail-closed production-like config | Production IAM rollout |
| Runtime/infrastructure gap | P1 | Open | GL-220 local gate | Real deployment architecture and ops ownership |

## Compact Next Roadmap

1. GL-222: Workspace identity, membership, and ownership design/implementation
   plan.
2. GL-223: Workspace-scoped query/mutation enforcement with focused tests.
3. GL-224: Evidence/provenance/audit workspace propagation and export scoping.
4. GL-225: Production IAM provider gate design.
5. GL-226: Live PostgreSQL production-readiness gate.

## Decision

`workspace_enforcement_final_go_no_go_v6_ready_for_merge_with_blockers`

## Decision Rationale

GL-221 confirms current tenant enforcement remains useful for Developer Preview
and controlled synthetic/demo evaluation, but workspace enforcement is not
production-complete. The correct final v6 posture is GO / CONTINUE for
Developer Preview, GO with strict boundaries for controlled external technical
review, CONDITIONAL for synthetic/demo pilot, and NO-GO for production SaaS,
real/private/institutional data, official SDK/package, compliance
certification, and live PostgreSQL production readiness.

## Findings

- No real workspace enforcement implementation exists beyond reserved nullable
  fields and route-level tenant prechecks.
- Current cross-tenant denial behavior is preserved.
- Cross-workspace lookup and mutation denial are not claimed.
- No backend change was safe within GL-221 scope without broader schema/RBAC
  work.

## Safety Confirmations

- GL-221 is not production release.
- Developer Preview / Controlled Preview boundaries remain.
- Public snapshot/export remains separate-gate only.
- Public website publish remains separate-gate only.
- No public push, public publish, or visibility change was performed.
- No package metadata, setup.py, SDK pyproject.toml, package.json, or
  package-lock.json was added.
- No GitHub workflow or snapshot publish script was changed.
- No migration, dependency, deployment, cloud, Kubernetes, Terraform, Helm, TLS
  certificate, or private-key file was added.
- No exploit details, real secrets, real customer data, private grant data, or
  institutional data are included.

## Recommended Next Issues

- GL-222 Workspace identity/membership/ownership implementation plan.
- GL-223 Workspace-scoped lookup and mutation enforcement.
- GL-224 Workspace propagation for evidence, provenance, audit, compliance, and
  export surfaces.
- GL-225 Production identity provider readiness gate.
- GL-226 Live PostgreSQL production readiness gate.
