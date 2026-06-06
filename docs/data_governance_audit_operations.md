# GL-209 - Data Governance & Audit Operations

**Issue ID:** GL-209
**Title:** Data Governance & Audit Operations
**Status:** Internal / Developer Preview

GL-209 is a data-governance and audit-operations baseline. It is not a
Production SaaS readiness declaration.

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

GL-200A through GL-208 are merged internally. The repository now has
tenant/workspace, auth/secrets/config, persistence/migration, API contract,
operations, admin/operator, claim-safety, and runtime/IAM/abuse/incident
baselines. Those baselines are useful for controlled preview with synthetic/demo
data only, but they are not production-complete.

## Scope

- Data classification and allowed data boundary.
- Retention, deletion, and redaction policy baseline.
- Audit export, auditor-report, and hash-chain operations baseline.
- Audit immutability preservation.
- Backup/restore governance alignment.
- Evidence/export secret-safety checks.
- Controlled-preview data-handling rules.
- Claim-safe documentation, JSON artifact, regression tests, and a read-only
  audit export check script.

## Non-Goals

- Production SaaS readiness.
- Real customer/private grant/institutional data readiness.
- Compliance certification or GDPR/SOC2/ISO readiness.
- Broad compliance platform.
- Broad deletion, retention, legal-hold, or redaction subsystem.
- Destructive deletion against `audit_events`.
- Source audit redaction mutation.
- Production backup storage, cloud integration, or external credentials.
- Frontend, website, design, GitHub workflow, snapshot publishing, package
  publishing, SDK package, or public marketing changes.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
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
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/migrations/* | Yes |
| backend/tests/* | Yes |
| scripts/ops/* | Yes |
| scripts/* | Yes |
| examples/* | Yes |

## Current State Summary

Audit events are append-only and hash-chained. SQLite and PostgreSQL migration
baselines include immutability triggers that prevent `UPDATE` and `DELETE` on
`audit_events`. Audit hash-chain verification and auditor-readable verification
reports are read-only. Evidence bundle examples are deterministic and synthetic.
GL-205 provides safe backup/restore dry-run, plan, and synthetic SQLite drill
patterns; live PostgreSQL execution remains gated and unexecuted without an
ephemeral database.

## Data Classification Baseline

| Data category | Current status |
|---|---|
| synthetic/demo data | Allowed in Developer Preview / Controlled Preview. |
| developer/test data | Allowed when synthetic and local/ephemeral. |
| audit events | Append-only, secret-safe, tenant-aware where applicable. |
| evidence bundles | Synthetic/demo only unless future gates approve otherwise. |
| operator/admin metadata | Allowed for controlled preview; tokens and hashes are sensitive. |
| tenant/workspace identifiers | Allowed as baseline identifiers; not production-complete isolation. |
| runtime/config metadata | Safe summaries only; raw secret values are forbidden. |
| secrets/tokens/credentials | Never stored in docs, artifacts, logs, or derived exports. |
| customer data | No-go. |
| private grant/institutional data | No-go. |

## Controlled-Preview Data Boundary

Controlled Preview remains limited to synthetic/demo data. No production data
imports are allowed. No public uploads of private data are allowed. Examples,
fixtures, docs, reports, and exported artifacts must not contain real secrets,
real personal data, real customer data, private grant data, or institutional
data. First external controlled pilot activity remains synthetic/demo only until
future data-governance, legal, security, and operations gates approve otherwise.

## Retention Policy Baseline

Source audit history must remain append-only and immutable. Controlled-preview
synthetic/demo data can be reset or destroyed in ephemeral environments. Real
customer/private grant/institutional retention schedules remain deferred because
real data is no-go. Legal hold, regulatory retention, retention automation,
backup retention, and destruction certificates are production blockers.

## Deletion Policy Baseline

`audit_events` must not be destructively deleted or rewritten. Operational
non-audit data deletion remains a future controlled feature unless already
implemented by existing domain behavior. Secret rotation or removal must not
require audit history mutation. Any future destructive operation must be
explicitly scoped, authorized, tested, and limited to non-audit data or
ephemeral synthetic environments.

## Redaction Policy Baseline

Redaction applies to derived exports, views, reports, and diagnostics, not to
source audit mutation. Derived outputs must omit raw Authorization headers, raw
admin/operator tokens, token hashes, lookup hashes, DSNs, passwords, private
keys, signing keys, raw request bodies, evidence payloads, customer data,
private grant data, and institutional data. Source audit history remains
immutable.

## Audit Immutability Model

The source audit table is the immutable record. SQLite and PostgreSQL
immutability migrations preserve no-update/no-delete behavior. Audit hash-chain
helpers verify row integrity and chain continuity without mutation. Failed
verification is an incident signal and must be investigated; the source history
must not be repaired by destructive rewrite.

## Audit Export Operations Baseline

GL-209 adds `scripts/ops/gl209_audit_export_check.py`, a read-only audit export
check script. It supports `--plan`, `--dry-run`, and `--sample`. The script
emits a derived manifest/check summary only, uses synthetic/demo sample data,
does not open a database by default, does not mutate source audit rows, and
refuses secret-like derived manifest content.

Full production audit export workflows remain deferred. Future work must add
authorization, approval, retention, encryption, access logging, tenant scoping,
and legal/compliance review before real data is eligible.

## Audit Hash-Chain Operations

Baseline procedure:

1. Run read-only hash-chain verification before any derived audit export.
2. Treat invalid chain status as an incident and stop export.
3. Review failures without exposing secrets or evidence payloads.
4. Preserve source rows unchanged.
5. Export only derived safe summaries until production export governance exists.

## Evidence Bundle Operations

Evidence bundle examples remain synthetic/demo only. Evidence exports must be
deterministic, integrity-checkable, and secret-safe. Raw evidence payloads must
not appear in logs or broad operational manifests. Evidence integrity anomalies
are audit/security incidents and should be routed through the GL-208 incident
baseline.

## Backup/Restore Governance Alignment

GL-205 backup/restore dry-run and plan modes remain the baseline. Synthetic
SQLite drill flow may reset/destroy ephemeral data. Backup artifacts must not
contain secrets or real customer/private grant/institutional data. Restore drills
must verify audit hash-chain integrity and tenant/workspace separation where
applicable.

## PostgreSQL Backup/Restore Status

PostgreSQL backup/restore remains manual checklist only for ephemeral/synthetic
instances. Production backup scheduling, encryption, offsite retention, access
control, restore RTO/RPO, and DR runbooks are not implemented and remain
production blockers.

## Live PostgreSQL Validation Status

Live PostgreSQL validation remains not executed unless a safe ephemeral instance
is explicitly available and env-gated. Live PostgreSQL production readiness is
not claimed.

## Data Governance Risk Register

| ID | Risk | Mitigation |
|---|---|---|
| R-001 | Derived exports could leak sensitive fields. | Export only safe manifests; redact/refuse secret-like content. |
| R-002 | Operators may try to satisfy deletion by mutating audit history. | Keep source audit immutable; redaction is derived-only. |
| R-003 | Backup artifacts could include private data in future pilots. | Real/private data remains no-go; add production backup governance later. |
| R-004 | Hash-chain failure could be mishandled as a repair task. | Treat as incident; investigate without destructive rewrite. |
| R-005 | Compliance readiness could be overclaimed from baseline docs. | Explicitly state no compliance certification or GDPR/SOC2/ISO readiness. |

## Compliance / Non-Goals

GL-209 does not claim compliance certification, GDPR readiness, SOC2 readiness,
ISO readiness, production retention compliance, legal hold, eDiscovery, DSR
automation, or complete audit export governance. These are blockers before real
customer/private grant/institutional data.

## Implementation Summary

GL-209 adds this documentation artifact, a JSON artifact, a focused regression
test suite, and a read-only audit export check script. No backend source,
OpenAPI contract, migration/schema, frontend/website/design, workflow,
snapshot-publish, SDK package, or package publishing change was required.

## Controlled-Preview Impact

Controlled Preview remains limited to synthetic/demo data. GL-209 improves
traceability for data classification, retention/deletion/redaction policy,
audit operations, and backup governance without expanding data eligibility.

## Production Readiness Impact

Production SaaS remains no-go. Real customer/private grant/institutional data
remains no-go. Official SDK/package remains no-go. Live PostgreSQL production
claim remains no-go. Backup/restore production readiness is not claimed.
Compliance certification is not claimed.

## Remaining Blockers

- Production data governance policy and approval workflow.
- Legal/compliance retention and deletion review.
- Real-data DSR/legal-hold/eDiscovery process.
- Production audit export authorization, encryption, and access logging.
- Production backup encryption, retention, offsite storage, and restore RTO/RPO.
- Live PostgreSQL validation execution against an ephemeral instance.
- Production observability and incident response program.
- Production IAM, tenant administration, and workspace enforcement.

## Findings

- Existing audit hash-chain verification is read-only.
- Existing migrations preserve audit immutability.
- Redaction belongs in derived exports/reports, not source audit mutation.
- GL-205 backup/restore governance remains synthetic/ephemeral.
- No destructive audit deletion or source audit redaction mutation was added.
- No OpenAPI, migration, backend source, frontend, workflow, package, SDK, or
  public publish change was required.

## Decision

`data_governance_audit_operations_baseline_approved_with_gaps`

## Decision Rationale

GL-209 establishes a bounded data-governance and audit-operations baseline for
Developer Preview / Controlled Preview. It documents the no-go real/private
data boundary, preserves immutable audit source history, adds a safe derived
audit export check, and records remaining blockers without claiming production
or compliance readiness.

## Safety Confirmations

- GL-209 is not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict
  boundaries.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Live PostgreSQL production claim remains no-go.
- Compliance certification is not claimed.
- Backup/restore production readiness is not claimed.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- Audit source history remains immutable.
- Redaction is for derived exports/reports, not source audit mutation.
- No destructive audit deletion was added.
- Tenant/workspace isolation baseline is not overclaimed as production-complete.
- Admin/operator control plane baseline is not overclaimed as production-complete.
- Controlled preview expansion remains limited to synthetic/demo data.
- Unrelated untracked website files were excluded from GL-209.

## Recommended Next Issues

- GL-209 Merge if ready.
- GL-210 Website Track.
- GL-206B Live PostgreSQL Validation Execution when ephemeral PostgreSQL is
  available.
