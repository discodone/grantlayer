# GL-210 - Website Track

**Issue ID:** GL-210
**Title:** Website Track
**Status:** Internal / Developer Preview

GL-210 creates a claim-safe website baseline. It does not publish a website,
does not push to public GitHub, and does not change repository visibility.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Production SaaS is no-go. Real customer data, private grant data,
and institutional data remain no-go. The internal SDK prototype is not an
official SDK or package. Live PostgreSQL production readiness is not claimed.
Compliance certification is not claimed. GDPR, SOC2, and ISO readiness are not
claimed.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.

## Context

GL-200A through GL-209 are merged internally. The repository now has
tenant/workspace, auth/secrets/config, persistence/migration, API contract,
operations, admin/operator, claim-safety, runtime/IAM/abuse/incident, and data
governance/audit operations baselines. Those baselines support local evaluation
and bounded Controlled Preview with synthetic/demo data only, but they are not
production-complete.

GL-210 defines what a public-facing website may safely say and adds a small
static website baseline for future review. Public publish remains out of scope.

## Scope

- Review GL-200A through GL-209 claim-safety inputs and public entry docs.
- Inspect the pre-existing untracked website-design material without blindly
  adopting it.
- Define website allowed and prohibited claims.
- Add a minimal static `website/` baseline using local assets only.
- Produce this document, a structured JSON artifact, and regression tests that
  block website overclaims and unsafe website mechanics.

## Non-Goals

- Public website publish, public GitHub push, or visibility change.
- Deployment automation, hosting config, GitHub workflow changes, or snapshot
  publish script changes.
- Backend/src changes, API behavior changes, migrations, DB/schema changes, or
  dependency changes.
- JavaScript app, build system, package metadata, analytics, tracking, cookies,
  external assets, external API calls, or forms.
- Production SaaS, enterprise readiness, compliance certification, official SDK
  package, live PostgreSQL production readiness, or real/private data readiness
  claims.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/claim_safety_controlled_preview_boundary.md | Yes |
| docs/examples/gl207/claim_safety_controlled_preview_boundary.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
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
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| docs/website_design_workspace_import_report.md | Yes, inspection only |
| docs/website_design_workspace_import_report_dirty_stop.md | Yes, inspection only |
| website-design/ | Yes, inspection only |

## Existing Website-Design Inspection Result

The untracked `website-design/` tree contains only `README.md` and
`IMPORT_CHECKLIST.md`. The expected design files, pages, scripts, styles, and
deck files were not present. The import reports state that no design files were
found locally or on the reachable Nextcloud VM and no files were imported.

The `website-design/README.md` also contains stale or broad positioning such as
`MVP`, `pilot-readiness hardening`, and `production readiness in progress`.
Because the tree is incomplete, untracked, and not a working static website, no
files from `website-design/` are adopted by GL-210. The material remains
excluded for future intentional review.

The prompt referenced `docs/website_design_workspace_import_dirty_stop.md`; that
exact path is absent in this worktree. The present stop report,
`docs/website_design_workspace_import_report_dirty_stop.md`, was inspected.

## Website Claim Boundary

The website may describe the current Developer Preview posture and controlled
preview boundaries only. It must use caveated language for every baseline that
is not production-complete. It must not imply public availability, hosting,
production operation, enterprise readiness, compliance certification, official
SDK/package availability, or approval for real/private data.

## Allowed Website Claims

- GrantLayer is an API-first Developer Preview.
- GrantLayer is a verification, audit, and compliance-support layer for agentic
  grant workflows.
- Controlled Preview is possible with strict boundaries.
- Controlled Preview expansion is synthetic/demo data only.
- Tenant/workspace isolation baseline is implemented, but not
  production-complete.
- Admin/operator tenant control-plane baseline exists, but not
  production-complete.
- Runtime/IAM/abuse/incident hardening baseline exists, but not
  production-complete.
- Data governance/audit operations baseline exists, but not production-complete.
- Internal SDK prototype exists, but no official SDK/package is available.
- Live PostgreSQL validation remains pending unless an ephemeral validation has
  actually been executed.
- Security-sensitive reports route to GitHub Security Advisories.

## Prohibited Website Claims

- Production SaaS ready.
- Enterprise ready.
- Compliance certified.
- GDPR/SOC2/ISO ready.
- Ready for real customer data.
- Ready for private grant/institutional data.
- Official SDK available.
- Public SDK package available.
- Production-ready SDK.
- Live PostgreSQL production ready.
- Complete tenant/workspace production isolation.
- Complete production admin/operator tenant-management plane.
- Complete production observability stack.
- Complete production backup/restore/DR readiness.
- Complete incident response program.

## Static Website Implementation Summary

GL-210 adds a small static website baseline under `website/`.

The implementation uses plain HTML and CSS only. It has no JavaScript, no build
system, no package metadata, no external fonts, no external images, no external
scripts, no external API calls, no analytics, no tracking, no cookies, and no
forms. Links point only to local repository documents.

The page states Developer Preview / Controlled Preview with strict boundaries,
not production SaaS, no real customer/private grant/institutional data
readiness, no official SDK/package, no live PostgreSQL production readiness
claim, and no compliance certification claim.

## Website File List

- `website/index.html`
- `website/styles.css`
- `website/README.md`

## Public Publish Status

Not published. GL-210 is an internal branch baseline only.

## No-Public-Publish Confirmation

No public publish occurred. No public GitHub push occurred. Repository
visibility was not changed.

## No Analytics / Tracking / Forms Confirmation

The static website baseline includes no analytics, tracking, cookies,
JavaScript, external scripts, external assets, external API calls, or forms.

## Security Reporting Model

Website copy and documentation route security-sensitive reports to GitHub
Security Advisories. Public reports must not include exploit details, secrets,
real customer data, private grant data, or institutional data.

## Controlled-Preview Boundary

Controlled Preview remains limited to strict boundaries and synthetic/demo data
only. Real customer data, private grant data, and institutional data remain
no-go. Public website copy must preserve those boundaries.

## Production Readiness Impact

GL-210 does not advance production readiness. It only documents claim boundaries
and adds a static Developer Preview website baseline. Production SaaS remains
no-go until future security, data, operations, legal, live PostgreSQL,
backup/restore, observability, and pilot gates are completed.

## Remaining Blockers

- Public publish review and approval remain future work.
- Website design system, content review, accessibility audit, and brand review
  remain future work.
- Live PostgreSQL validation remains pending unless an ephemeral validation is
  executed in a future issue.
- Official SDK/package publication remains no-go.
- Real customer/private grant/institutional data readiness remains no-go.
- Compliance certification and GDPR/SOC2/ISO readiness remain no-go.

## Risk Register

| Risk | Status | Mitigation |
|---|---|---|
| Website copy overclaims production readiness | Controlled | GL-210 tests scan website copy and JSON/doc boundaries. |
| Incomplete untracked website-design material is adopted accidentally | Controlled | GL-210 explicitly excludes the tree and documents why. |
| Static page gains tracking, forms, or external calls | Controlled | GL-210 tests reject those mechanics. |
| Security reporting text becomes too public or detailed | Controlled | Copy routes sensitive reports to GitHub Security Advisories without exploit details. |
| Future public publish happens before review | Open | Public publish remains prohibited and requires a future issue. |

## Decision

`website_track_baseline_approved_with_gaps`

## Decision Rationale

The safe path is to exclude the incomplete untracked `website-design/` material
and add a small static baseline with explicit claim boundaries. This produces a
reviewable website track without importing stale design placeholders, adding
dependencies, collecting user data, or implying production readiness.

## Findings

- Website claim boundary is now documented for Developer Preview / Controlled
  Preview only.
- Static website baseline is intentionally small and dependency-free.
- Existing website-design material was inspected but not adopted.
- Public publish remains prohibited and did not occur.

## Safety Confirmations

- Production SaaS readiness is not claimed.
- Enterprise readiness is not claimed.
- Compliance certification is not claimed.
- GDPR/SOC2/ISO readiness is not claimed.
- Real customer data readiness is not claimed.
- Private grant/institutional data readiness is not claimed.
- Tenant/workspace isolation is not overclaimed.
- Admin/operator control plane is not overclaimed.
- Runtime/IAM/abuse/incident hardening is not overclaimed.
- Data governance/audit operations are not overclaimed.
- No official SDK/package is claimed.
- Live PostgreSQL production readiness is not claimed.
- Controlled Preview expansion is limited to synthetic/demo data.
- No analytics, tracking, cookies, forms, external assets, or external API calls
  were added.
- No backend/src, API behavior, migrations, DB/schema, dependency, GitHub
  workflow, or snapshot publish script changes were made.
- No package publishing metadata was added.
- No exploit details, real secrets, real customer data, private grant data, or
  institutional data are included.
- Security-sensitive reports route to GitHub Security Advisories.
- No public GitHub push, public publish, or visibility change occurred.

## Recommended Next Issues

- GL-210 Merge if ready.
- GL-211 SDK / Pilot / Production Gate.
- GL-206B Live PostgreSQL Validation Execution when ephemeral PostgreSQL is
  available.
