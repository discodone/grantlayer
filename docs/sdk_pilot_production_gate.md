# GL-211 - SDK / Pilot / Production Gate

**Issue ID:** GL-211
**Title:** SDK / Pilot / Production Gate
**Status:** Internal / Developer Preview

GL-211 is a gate/decision baseline. It is not a Production SaaS readiness
declaration, not an SDK release, not a public snapshot, and not a public website
publish.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Production SaaS is no-go. Real customer data, private grant data,
and institutional data remain no-go. The internal SDK prototype is not an
official SDK or package. Experimental public SDK/package work remains deferred
unless a future projection gate explicitly passes. Live PostgreSQL production
readiness is not claimed. Compliance certification is not claimed. GDPR, SOC2,
ISO, and enterprise readiness are not claimed.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.

## Context

GL-200A through GL-210 are merged internally. The current internal main includes
tenant/workspace isolation, auth/secrets/config, persistence/PostgreSQL
migration readiness, API contract, SDK prototype boundary, production ops,
live PostgreSQL/backup/observability baseline, admin/operator tenant control
plane, claim safety, runtime/IAM/abuse/incident, data governance/audit
operations, and static website baselines.

Those baselines support local evaluation and bounded review with synthetic/demo
data only. They do not make GrantLayer production SaaS, do not approve real
customer/private grant/institutional data, do not create an official SDK or
package, and do not publish the static website.

## Scope

- Decide the SDK/package posture after GL-200A through GL-210.
- Decide the controlled external review and first external pilot posture.
- Decide the Production SaaS and real/private data posture.
- Decide the public snapshot and website publication posture.
- Record blockers before stronger external claims.
- Add structured documentation, a JSON artifact, an internal-only pilot gate
  checklist, and regression tests.

## Non-Goals

- SDK packaging, package metadata, package registry release, or GL-203D.
- Public GitHub push, public snapshot work, public website publish, or
  repository visibility change.
- Production SaaS enablement or production deployment configuration.
- Live PostgreSQL validation execution.
- Backend/src changes, API behavior changes, migrations, DB/schema changes, or
  dependency changes.
- GitHub workflow changes, snapshot publish script changes, frontend/website
  changes, analytics, tracking, external service credentials, or data collection
  forms.
- Reviewer outreach, public pilot invitation text, release metadata, or
  compliance certification claims.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/website_track.md | Yes |
| docs/examples/gl210/website_track.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
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
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| website/index.html | Yes |
| website/styles.css | Yes |
| website/README.md | Yes |
| examples/sdk_prototype/python/grantlayer_client.py | Yes |
| scripts/ops/gl205_live_postgres_validation.py | Yes |
| scripts/ops/gl205_backup_restore_drill.py | Yes |
| scripts/ops/gl209_audit_export_check.py | Yes |

## Current State Summary

GrantLayer is an API-first Developer Preview with controlled-preview boundaries.
The codebase has useful baseline controls, documentation, and tests, but the
production control plane is incomplete. Tenant/workspace isolation baseline
exists but is not production-complete. Admin/operator tenant control-plane
baseline exists but is not production-complete. Runtime, IAM, abuse, and
incident hardening baseline exists but is not production-complete. Data
governance/audit operations baseline exists but is not production-complete.

The static website baseline remains internal and unpublished by this repository.
The internal SDK prototype exists as an internal prototype only. Live PostgreSQL
validation remains pending until an explicitly ephemeral PostgreSQL instance is
available.

## SDK Gate Decision

SDK gate result: official SDK/package is no-go; experimental public SDK/package
is deferred; internal SDK prototype remains allowed only as an internal
prototype.

## Official SDK/Package Decision

Official SDK/package: **NO-GO**.

GrantLayer must not claim an official SDK or package, must not publish a package
registry release, and must not add package publishing metadata in GL-211.

## Experimental SDK/Package Decision

Experimental public SDK/package: **DEFERRED / CONDITIONAL NO-GO**.

GL-203D remains deferred unless a future projection gate explicitly allows it
after the required blockers are cleared. GL-211 does not implement GL-203D and
does not turn the internal SDK prototype into an official or public package.

## Internal SDK Prototype Boundary

The internal SDK prototype may continue to exist for internal Developer Preview
assessment. It may be referenced only as a prototype. It is not official, not
published, not production-ready, and not a support commitment. SDK docs may
describe prototype status only.

## Package Publishing Boundary

Package publishing is no-go. GL-211 adds no package metadata, no `setup.py`, no
SDK `pyproject.toml`, no `package.json`, no `package-lock.json`, no release
metadata, and no registry publish flow.

## Pilot Gate Decision

First external controlled pilot: **CONDITIONAL**, synthetic/demo data only.

The pilot gate allows internal demo, Developer Preview review, controlled
external technical review, and a first external controlled pilot only if every
participant and artifact stays within strict synthetic/demo-data boundaries.
The pilot must not imply Production SaaS, real data readiness, compliance
readiness, official SDK availability, public website publish, or public package
availability.

## Pilot Tier Matrix

| Tier | Decision | Data Boundary | Claim Boundary |
|---|---|---|---|
| Internal demo | Allowed | Synthetic/demo only | Developer Preview only |
| Developer preview review | Allowed | Synthetic/demo only | Controlled Preview with strict boundaries |
| Controlled external technical review | Conditional | Synthetic/demo only | No production, compliance, official SDK, or real data claims |
| First external controlled pilot | Conditional | Synthetic/demo only | No Production SaaS or real/private data readiness claims |
| Controlled preview expansion | Conditional | Synthetic/demo only | Future explicit gate required for any broader claim |
| Real data pilot | NO-GO | Real customer/private grant/institutional data forbidden | No real data readiness claim |
| Production pilot | NO-GO | Production-like data import forbidden | No Production SaaS claim |

## Controlled External Review Boundary

Controlled external technical review is allowed only with synthetic/demo data,
safe local or ephemeral environments, and claim-safe instructions. Reviewer
instructions must prohibit real secrets, real customer data, private grant data,
institutional data, production-like imports, and exploit details in public
channels. Security-sensitive reports route to GitHub Security Advisories.

## First External Controlled Pilot Boundary

A first external controlled pilot is conditional and synthetic/demo data only.
It must not require public website publish, public GitHub push, a public SDK
package, package installation from a registry, production credentials, external
hostnames, analytics, tracking, or forms collecting user data. It must not be
represented as Production SaaS, compliance readiness, enterprise readiness, or
approval for real customer/private grant/institutional data.

## Production Gate Decision

Production SaaS: **NO-GO**.

Real customer data: **NO-GO**.

Private grant/institutional data: **NO-GO**.

Compliance certification: **NO-GO**.

Enterprise readiness: **NO-GO**.

Live PostgreSQL production claim: **NO-GO**.

Complete DR/backup/restore claim: **NO-GO**.

Complete production observability claim: **NO-GO**.

Complete tenant isolation claim: **NO-GO**.

Complete production IAM claim: **NO-GO**.

## Production No-Go Rationale

Production remains no-go because live PostgreSQL validation has not been
executed, production backup/restore automation is incomplete, production
observability/alerting is incomplete, production IAM is incomplete,
admin/operator production controls are incomplete, tenant/workspace production
guarantees are incomplete, data retention/deletion/redaction implementation is
not production-complete, external security validation is not complete, and
support/incident processes are not mature enough for Production SaaS claims.

## Real Data No-Go Rationale

Real customer data, private grant data, and institutional data remain no-go
because data governance, retention, deletion, redaction, backup, restore,
incident response, access control, tenant/workspace guarantees, legal review,
and external validation are not production-complete. No production-like data
import is allowed under GL-211.

## Live PostgreSQL Blocker Status

GL-206B Live PostgreSQL Validation Execution remains pending until an ephemeral
PostgreSQL instance is available. GL-211 does not start GL-206B. Live PostgreSQL
production readiness is not claimed.

## Website / Public Snapshot Gate

Public GitHub push is no in GL-211. Public publish is no in GL-211. Website
public deployment is no in GL-211. Public snapshot update is deferred to a
separate issue if explicitly approved later. The existing static website
baseline remains internal until a separate publish gate. Any future public
update must preserve GL-207 and GL-210 claim boundaries.

## Public Claim Boundary Preservation

Public-facing copy and reviewer-facing instructions must preserve these
boundaries:

- Developer Preview / Controlled Preview with strict boundaries.
- Controlled Preview expansion limited to synthetic/demo data.
- Production SaaS is no-go.
- Real customer/private grant/institutional data is no-go.
- Official SDK/package is no-go.
- Experimental public SDK/package remains deferred unless a future projection
  gate passes.
- Live PostgreSQL production claim is no-go.
- Compliance certification, GDPR, SOC2, ISO, and enterprise readiness are not
  claimed.
- Tenant/workspace isolation, admin/operator control plane,
  runtime/IAM/abuse/incident hardening, and data governance/audit operations are
  not production-complete.

## Remaining Blockers

- GL-206B Live PostgreSQL Validation Execution with an ephemeral PostgreSQL
  instance.
- Production backup/restore automation.
- Production observability and alerting stack.
- Production IAM completion.
- Admin/operator production controls.
- Tenant/workspace production guarantees.
- Data retention, deletion, and redaction implementation.
- Security review and external validation.
- Support and incident process maturity.
- SDK/package release gate if pursued.
- Public publish gate if pursued.
- Packaging security review.
- External compatibility matrix.
- Release/versioning policy.
- Official support policy.

## Risk Register

| Risk | Status | Mitigation |
|---|---|---|
| SDK prototype is mistaken for official SDK/package | Open | Keep official SDK/package no-go and test for no package metadata. |
| Experimental SDK is published before projection gate | Open | Keep GL-203D deferred and package publishing no-go. |
| Controlled pilot drifts into real/private data | Open | Require synthetic/demo data only and prohibit production-like imports. |
| Pilot copy implies production or compliance readiness | Controlled | GL-211 documents explicit no-go claims and adds regression tests. |
| Public website or snapshot is published without gate | Open | Public publish and public snapshot are deferred to a separate issue. |
| Security-sensitive details are disclosed publicly | Controlled | Route sensitive reports to GitHub Security Advisories and prohibit exploit details in public channels. |

## Findings

- Official SDK/package is not allowed now.
- Experimental public SDK/package remains deferred unless a future projection
  gate explicitly passes.
- Internal SDK prototype remains allowed only as an internal prototype.
- First external controlled pilot is conditional and synthetic/demo data only.
- Production SaaS, real customer data, private grant data, institutional data,
  compliance certification, enterprise readiness, live PostgreSQL production
  readiness, complete DR, complete observability, complete tenant isolation, and
  complete production IAM remain no-go.
- Public GitHub push, public publish, website deployment, and public snapshot
  update are out of scope for GL-211.
- Unrelated website-design files remain excluded from GL-211.

## Recommended Next Issues

- GL-211 Merge if ready.
- GL-206B Live PostgreSQL Validation Execution when ephemeral PostgreSQL is
  available.
- GL-212 Public Snapshot / External Review Gate only if explicitly approved
  later.

## Decision

Decision: `sdk_pilot_production_gate_approved_with_gaps`.

## Decision Rationale

GL-211 allows continued internal Developer Preview work and conditional
controlled external technical review or first external controlled pilot with
synthetic/demo data only. It rejects official SDK/package availability now,
defers experimental public SDK/package work, rejects Production SaaS and
real/private data readiness, and defers public snapshot/website publish work to
future explicit gates.

## Safety Confirmations

- GL-211 is a gate/decision baseline, not a Production SaaS readiness
  declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict
  boundaries.
- Production SaaS is no-go.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Experimental public SDK/package remains deferred unless a future projection
  gate passes.
- Internal SDK prototype boundary is documented.
- Package publishing boundary is documented.
- Live PostgreSQL production claim remains no-go.
- Public website publish remains no-go in this issue.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- No compliance certification is claimed.
- Tenant/workspace isolation is not production-complete.
- Admin/operator tenant control plane is not production-complete.
- Runtime/IAM/abuse/incident hardening is not production-complete.
- Data governance/audit operations is not production-complete.
- Unrelated website-design files are excluded.
