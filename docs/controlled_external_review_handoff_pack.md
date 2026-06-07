# GL-222 — Controlled External Technical Review Handoff Pack

**Issue ID:** GL-222
**Title:** Controlled External Technical Review Handoff Pack
**Branch:** `gl-222-controlled-external-review-handoff-pack`
**Status:** Internal / Developer Preview

GL-222 is an internal controlled-review handoff pack, not reviewer outreach.
GL-222 does not create a public export.
GL-222 does not publish to public GitHub.
GL-222 does not change repository visibility.
GL-222 does not approve public snapshot/export/publish.
GL-222 does not contact or invite reviewers.

Controlled External Technical Review is GO only with strict boundaries.
Review materials remain synthetic/demo only.
Production SaaS remains NO-GO.
Real customer/private grant/institutional data remains NO-GO.
Official SDK/package remains NO-GO.
Compliance certification remains NO-GO.
Live PostgreSQL production readiness remains NO-GO.
Security-sensitive reports route to GitHub Security Advisories.
No exploit details are included.
No real secrets are included.
No real customer/private data is included.

Unrelated website-design/import files (`website-design/`,
`docs/website_design_workspace_import_report.md`,
`docs/website_design_workspace_import_report_dirty_stop.md`,
and similarly named files) are excluded from GL-222.

---

## Context

GL-214 through GL-221 are merged internally. The final readiness matrix v6 from
GL-221 shows:

| Tier | Decision |
|---|---|
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Snapshot Preparation | CONDITIONAL — separate explicit gate required |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

Main branch after GL-221 merge: `382ac17`

Full suite baseline after GL-221:
- 9004 tests / 43 failures / 3 errors / 253 skipped / 0 real regressions

The Controlled External Technical Review gate (GO with strict boundaries) has
been authorised since GL-217 and confirmed through GL-218, GL-219, GL-220, and
GL-221 without change. GL-222 prepares the internal handoff documentation that
would be used to brief a reviewer, but does not initiate that review.

---

## Scope

GL-222 covers:
- Documenting the current allowed review posture and strict boundaries.
- Answering the ten required handoff questions.
- Specifying eligible and prohibited review materials.
- Specifying allowed and prohibited claims.
- Documenting known limitations and NO-GO areas.
- Documenting known full-suite false-positive classes.
- Providing reviewer-safe reproduction commands.
- Specifying security-sensitive report routing.
- Specifying the approval boundary for any future public/export/publish action.
- Adding a local-only dry-run/plan handoff gate script.
- Adding a machine-readable JSON artifact and focused tests.

---

## Non-Goals

GL-222 does not:
- Contact, invite, or outreach to any external reviewer.
- Create a public export directory or public snapshot worktree.
- Push to public GitHub or change repository visibility.
- Approve public snapshot/export/publish — that requires a separate explicit gate.
- Implement product features, workspace enforcement, or production infrastructure.
- Add migrations, schema changes, or dependency updates.
- Change `backend/src/`, GitHub workflows, or snapshot publish scripts.
- Add production deployment config, cloud integration, or TLS certificates.
- Claim production SaaS readiness, compliance certification, or official SDK availability.
- Include exploit details, real secrets, or real customer/private data.

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/workspace_enforcement_final_go_no_go_v6.md | Yes |
| docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json | Yes |
| docs/production_runtime_infrastructure_hardening_pack.md | Yes |
| docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json | Yes |
| docs/production_identity_access_hardening_pack.md | Yes |
| docs/examples/gl219/production_identity_access_hardening_pack.json | Yes |
| docs/public_external_review_export_safety_pack.md | Yes |
| docs/examples/gl218/public_external_review_export_safety_pack.json | Yes |
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/production_operations_hardening_pack.md | Yes |
| docs/examples/gl216/production_operations_hardening_pack.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
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
| backend/src/server.py | Yes (reference only) |
| backend/src/config.py | Yes (reference only) |
| backend/src/auth.py | Yes (reference only) |
| backend/src/identity_access.py | Yes (reference only) |
| backend/src/operators.py | Yes (reference only) |
| backend/src/audit_log.py | Yes (reference only) |
| backend/src/db.py | Yes (reference only) |
| backend/src/models.py | Yes (reference only) |
| backend/src/grants.py | Yes (reference only) |
| backend/src/grant_requests.py | Yes (reference only) |
| backend/tests/* | Yes (reference only) |
| scripts/ops/gl216_production_operations_gate.py | Yes (reference only) |
| scripts/ops/gl218_public_export_safety_scan.py | Yes (reference only) |
| scripts/ops/gl219_identity_access_gate.py | Yes (reference only) |
| scripts/ops/gl220_runtime_infrastructure_gate.py | Yes (reference only) |
| scripts/ops/gl221_workspace_go_no_go_gate.py | Yes (reference only) |
| scripts/ops/gl205_live_postgres_validation.py | Yes (reference only) |
| scripts/ops/gl205_backup_restore_drill.py | Yes (reference only) |
| scripts/ops/gl209_audit_export_check.py | Yes (reference only) |
| scripts/run-full-backend-suite.sh | Yes (reference only) |
| examples/grant_lifecycle_evidence_bundle.py | Yes (reference only) |
| examples/grant_lifecycle_evidence_bundle.json | Yes (reference only) |
| examples/first_verifiable_output.json | Yes (reference only) |

---

## Current Controlled External Review Posture

| Property | Value |
|---|---|
| Posture | Developer Preview / Controlled Preview with strict boundaries |
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Snapshot Preparation | CONDITIONAL — separate explicit gate required |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

---

## Handoff Package Purpose

This pack answers the ten required questions for a future controlled external
technical review:

1. **What may be shared with an external technical reviewer under strict boundaries?**
   See [Eligible Review Materials](#eligible-review-materials) below.

2. **What must not be shared?**
   See [Prohibited Materials](#prohibited-materials) below.

3. **What exact claims are allowed and prohibited?**
   See [Allowed Claims](#allowed-claims) and [Prohibited Claims](#prohibited-claims) below.

4. **What review scope should a reviewer inspect?**
   See [Reviewer Scope](#reviewer-scope) below.

5. **What known limitations and NO-GO areas must be explicit?**
   See [Known Limitations](#known-limitations) and the individual NO-GO boundaries below.

6. **What commands can reproduce the core verification locally?**
   See [Reviewer-Safe Verification Commands](#reviewer-safe-verification-commands) below.

7. **What known full-suite false positives should be disclosed without hiding them?**
   See [Known Full-Suite False-Positive Classes](#known-full-suite-false-positive-classes) below.

8. **What security-sensitive findings must route to GitHub Security Advisories?**
   See [Security-Sensitive Reporting Instructions](#security-sensitive-reporting-instructions) below.

9. **What approval is required before any public snapshot/export/publish?**
   See [Public Snapshot / Export / Publish Boundary](#public-snapshot--export--publish-boundary) below.

10. **What are the next issues after the controlled review handoff?**
    See [Recommended Next Issues](#recommended-next-issues) below.

---

## Reviewer Scope

A controlled external technical reviewer may inspect:

- **Auth baseline**: fail-closed startup, operator token hashing, tenant binding,
  challenge-response auth, token expiry, rotation model.
- **Audit log baseline**: append-only hash-chain, tamper-evidence, immutability
  triggers, hash-chain verification helper.
- **Tenant isolation baseline**: server-derived tenant context, application-layer
  tenant-scoped routing, absence of cross-tenant data leakage in test suite.
- **API contract**: `docs/openapi.yaml` endpoints, request/response shapes, error
  semantics.
- **Grant lifecycle**: create/approve/deny/revoke grant and grant-request flows
  with synthetic/demo data.
- **Rate-limit baseline**: request rate limiting, structured logging, correlation ID.
- **Runtime hardening**: JSON body enforcement, query parameter validation, CORS
  origin hardening, private key file permissions.
- **Identity/access posture**: static admin token baseline, absence of production
  OAuth/OIDC/JWT, identity gap documentation (GL-219).
- **Infrastructure posture**: ephemeral/local-only SQLite and optional PostgreSQL,
  dry-run backup/restore, no production infrastructure (GL-220).
- **Workspace posture**: `workspace_id` reserved/nullable, not production-enforced,
  gap documentation (GL-221).
- **Test suite**: full backend test suite structure, known false-positive classes,
  absence of real regressions.
- **Verification scripts**: local-only dry-run/plan gate scripts; grant lifecycle
  evidence bundle; first verifiable output helper.

---

## Excluded Scope

A reviewer must not inspect or receive:

- Real customer data, real grant applications, or real institutional data.
- Real credentials, tokens, DSNs, private keys, or auth headers.
- Internal Forgejo URLs, private IP addresses, private hostnames, or private
  filesystem paths.
- Internal CI/CD configuration referencing private services.
- The `website-design/` directory or any website-design import/report files.
- Any `setup.py`, SDK `pyproject.toml`, `package.json`, `package-lock.json`,
  or package publishing metadata.
- Production deployment configuration (Kubernetes, Terraform, Helm, cloud
  provider integration).
- TLS certificates or private key files.
- GitHub workflow files without a separate review gate.
- Snapshot publish scripts unless separately reviewed and approved.
- Any public release branches, public release tags, or public export directories.
- Database dumps, backup files, or operational logs with real data.
- The `.git/` directory, venvs, `__pycache__/`, or build artifacts.

---

## Eligible Review Materials

The following materials are eligible for a controlled external technical review,
subject to per-file secret/claim scanning before any future export:

**Documentation and contracts:**
- `README.md` (claim-safe after GL-207)
- `SECURITY.md` (routes to GitHub Security Advisories)
- `AGENTS.md` (claim-safe)
- `llms.txt` (claim-safe)
- `llms-full.txt` (claim-safe)
- `docs/openapi.yaml` (API contract, no real credentials)
- Reviewed `docs/` artifacts for resolved issues (no internal-infrastructure references)

**Examples and verification helpers:**
- `examples/first_verifiable_output.py` (local-only, synthetic only)
- `examples/first_verifiable_output.json` (synthetic reference artifact)
- `examples/grant_lifecycle_evidence_bundle.py` (local-only, synthetic/demo only)
- `examples/grant_lifecycle_evidence_bundle.json` (synthetic evidence bundle)
- `scripts/verify-first-output.sh` (local-only verification helper)

**Gate scripts (dry-run/plan only, no real credentials):**
- `scripts/ops/gl205_live_postgres_validation.py`
- `scripts/ops/gl205_backup_restore_drill.py`
- `scripts/ops/gl209_audit_export_check.py`
- `scripts/ops/gl216_production_operations_gate.py`
- `scripts/ops/gl218_public_export_safety_scan.py`
- `scripts/ops/gl219_identity_access_gate.py`
- `scripts/ops/gl220_runtime_infrastructure_gate.py`
- `scripts/ops/gl221_workspace_go_no_go_gate.py`
- `scripts/ops/gl222_controlled_review_handoff_gate.py`

**Backend source (reference, no real secrets, subject to per-file scan):**
- `backend/src/server.py`, `backend/src/config.py`, `backend/src/auth.py`
- `backend/src/identity_access.py`, `backend/src/operators.py`
- `backend/src/audit_log.py`, `backend/src/db.py`, `backend/src/models.py`
- `backend/src/grants.py`, `backend/src/grant_requests.py`

**Test suite:**
- `backend/tests/` (synthetic/demo data only, known false-positive classes disclosed)

---

## Prohibited Materials

The following must not be included in any controlled review handoff:

- `.env*` files with real credentials
- Raw PostgreSQL DSNs with real hostnames or passwords
- Raw tokens, auth headers, or Bearer tokens
- PEM private key blocks (RSA, OPENSSH, EC, DSA)
- Real admin tokens or operator tokens
- Real SMTP, S3, or cloud credentials
- Real customer data, real grant applications, real institutional data, real PII
- Real private grant data or private attachments
- Database dumps, backup files, or logs containing real data
- Internal Forgejo URLs, private IPs, private hostnames, internal filesystem paths
- `website-design/` directory and all contents
- `docs/website_design_workspace_import_report.md` and similarly named files
- `setup.py`, SDK `pyproject.toml`, `package.json`, `package-lock.json`
- Analytics/tracking integrations or data collection forms
- `.github/workflows/` files without separate review
- Snapshot publish scripts unless separately reviewed
- Production deployment config (Kubernetes, Terraform, Helm, cloud)
- Release metadata, public release branches, public release tags
- Data directories with real operational data
- `.git/`, caches, venvs, `__pycache__/`

---

## Allowed Claims

A reviewer may be told the following:

- "GrantLayer is Developer Preview / Controlled Preview with strict boundaries."
- "Local evaluation and controlled pilot with synthetic/demo data only."
- "Tenant/workspace isolation: baseline implemented, not production-complete."
- "Ephemeral live PostgreSQL validation passed with synthetic/demo data (GL-206B)."
- "Fail-closed auth baseline implemented; not production-grade IAM."
- "Append-only hash-chained audit baseline implemented."
- "Operator token hashing and tenant binding implemented."
- "Structured logging and rate-limit baseline implemented."
- "Controlled external technical review allowed only with strict boundaries and synthetic/demo data."
- "All examples use synthetic identifiers only."
- "All tokens and keys in examples are placeholders."
- "Security-sensitive reports route to GitHub Security Advisories."
- "Production SaaS is not claimed and not supported."
- "Real customer/private grant/institutional data is not ready."
- "Official SDK/package is not published."
- "workspace_id is reserved/nullable and not production-enforced."
- "Identity/access posture: static admin token baseline; no OIDC/SAML/SSO/MFA."
- "Runtime/infrastructure: ephemeral/local-only; no production infrastructure."
- "Public snapshot/export requires a later explicit approval gate."

---

## Prohibited Claims

A reviewer must not be told:

- "Production SaaS ready / production-grade / enterprise ready."
- "Ready for real customer data / private grant data / institutional data."
- "Compliance certification achieved (GDPR, SOC2, ISO, or any other)."
- "Official SDK available / official package published."
- "Live PostgreSQL production ready."
- "Independent security audit completed / penetration test passed."
- "Multi-tenant production isolation guaranteed / database RLS enforced."
- "OIDC / SAML / SSO / MFA implemented."
- "Public website is a production marketing launch."
- "Any claim implying a support SLA or uptime guarantee."
- "Any claim that implies real customer deployments are running."
- "workspace_id enforcement is production-complete."

---

## Data Boundary: Synthetic / Demo Only

Review materials are strictly synthetic/demo data only. This means:
- All example outputs use synthetic grant IDs, tenant IDs, and applicant names.
- No real applicant records, real grant applications, or real funding decisions.
- No real institutional records or personal data.
- No real private grant data or private attachments.
- Any database fixture in the test suite uses synthetic identifiers only.
- Reviewer must not supply real data to the local test environment.

---

## Real Customer / Private Grant / Institutional Data Boundary

Real customer data, private grant data, and institutional data are NO-GO for
this controlled review. Any engagement that would involve real data requires:
- Separate data governance and legal approval.
- Production-grade security controls (not yet implemented).
- Compliance certification relevant to the jurisdiction and data type (not yet
  achieved).
- Explicit owner sign-off beyond GL-222.

---

## Production SaaS Boundary

Production SaaS is NO-GO. GrantLayer does not support:
- Live customer-facing grant management operations.
- Production SLAs or uptime guarantees.
- Production incident response in a customer environment.
- Production scaling or multi-region deployment.

Any claim of production SaaS readiness is prohibited.

---

## Public Snapshot / Export / Publish Boundary

Any public snapshot, export, or publish requires:
- A separate explicit gate issue (not GL-222).
- All items in the GL-218 safety scan checklist to pass.
- Per-file secret scanning and claim-safety scanning of the candidate export.
- Explicit owner approval for the specific export candidate.
- No forbidden files (secrets, real data, internal infrastructure references,
  forbidden path types) in the export candidate.
- Manual human review of the export candidate before any push.

GL-222 does not approve, initiate, or constitute any public export or publish.

---

## Official SDK / Package Boundary

Official SDK/package is NO-GO. The internal SDK prototype (`backend/sdk/`)
is a local reference implementation only. It is not published to PyPI, npm,
or any package registry. No `setup.py`, SDK `pyproject.toml`, `package.json`,
or `package-lock.json` is added by GL-222. Official SDK/package availability
is not claimed.

---

## Compliance Certification Boundary

Compliance certification is NO-GO. GrantLayer has not achieved and does not
claim GDPR, SOC2, ISO, or any other compliance certification. Security-sensitive
reports route to GitHub Security Advisories, not to a compliance body.

---

## Live PostgreSQL Production Readiness Boundary

Live PostgreSQL production readiness is NO-GO. GL-206B validated an ephemeral
live PostgreSQL connection with synthetic/demo data only. No production
PostgreSQL deployment is in place. No production database credentials, DSNs,
or connection strings are present in review materials.

---

## Identity / Access Status After GL-219

GL-219 documented the identity and access hardening posture:
- Static admin token baseline: implemented.
- Operator token hashing and tenant binding: implemented.
- Token expiry and rotation model: implemented.
- OIDC / SAML / SSO / MFA: not implemented; explicitly NO-GO for production.
- External identity provider integration: not implemented.
- Production-grade IAM: not achieved.

A reviewer may inspect the identity/access posture documentation but must be
told that this is a Developer Preview baseline only, not a production-grade
identity solution.

---

## Runtime / Infrastructure Status After GL-220

GL-220 documented the runtime and infrastructure hardening posture:
- SQLite (ephemeral/dev): default runtime backend.
- PostgreSQL (optional): validated with synthetic/demo data in ephemeral mode.
- No production infrastructure: no production database, no production cloud
  provider, no production Kubernetes/Terraform/Helm deployment.
- Structured logging, rate limiting, and health/readiness endpoints: baseline only.
- No production observability stack.
- No production backup/restore automation.

A reviewer may inspect the runtime/infrastructure posture documentation but
must be told this is a local/ephemeral baseline only.

---

## Workspace Status After GL-221

GL-221 confirmed:
- `workspace_id` is reserved/nullable and not production-enforced.
- Tenant context is server-derived and enforced at application level.
- Cross-workspace lookup and mutation denial: not yet claimed.
- Trusted workspace context derivation: not implemented.
- Workspace identity/membership/ownership model: not implemented.

A reviewer may inspect the workspace posture documentation and test suite but
must be told explicitly that workspace enforcement is a known gap.

---

## Public / Export Safety Status After GL-218

GL-218 documented:
- No public export directory created.
- No public snapshot worktree created.
- No public GitHub push performed.
- No repository visibility change performed.
- Safety scan helper (`gl218_public_export_safety_scan.py`) is local-only.
- Any future export requires all GL-218 checklist items and explicit approval.

---

## Known Limitations

| Limitation | Severity | Status |
|---|---|---|
| `workspace_id` reserved/nullable — not production-enforced | P1 | Open |
| Cross-workspace lookup/mutation denial not implemented | P1 | Open |
| Static admin token — no OIDC/SAML/SSO/MFA | P1 | Open (Developer Preview acceptable) |
| No production database RLS or row-level isolation | P1 | Open |
| No production infrastructure (PostgreSQL, cloud, Kubernetes) | P1 | Open |
| No production observability stack | P1 | Open |
| No production backup/restore automation | P1 | Open |
| Tenant lifecycle (suspend/terminate/archive) not implemented | P1 | Open |
| Workspace propagation for audit/evidence/provenance not complete | P1 | Open |
| No compliance certification (GDPR, SOC2, ISO) | P0 | Open |
| No independent security audit | P1 | Open |
| No official SDK/package | P0 | Open |

---

## Known Full-Suite False-Positive Classes

The full backend test suite after GL-221 has 43 failures and 3 errors, all
classified as pre-existing or scope-guard false positives. No real regressions
exist. The known false-positive classes are:

| Class | Description |
|---|---|
| Stale/branch-only scope guards | Tests checking that certain branch-only changes are absent from main; trigger on branches that introduce new docs/scripts. |
| Scanner/meta/path false positives | Tests scanning for forbidden file patterns that match legitimate test or script names. |
| Public/readiness stale wording false positives | Tests checking for stale readiness language that match updated documentation wording. |
| Stale migration-count guards | Tests asserting a specific migration count that becomes stale when new migrations are added. |
| Pre-existing GL-172 publish-worktree errors | Errors from the publish-worktree path that pre-date GL-214 and are unresolved pre-existing issues. |
| Unrelated pre-existing website-design import false positives | Failures from unrelated `website-design/` import test scope that existed before GL-214. |
| Pre-existing GRANTLAYER env errors | Errors triggered by missing `GRANTLAYER_*` environment variables in bare test runs. |

GL-222 may add new branch-only scope-guard false positives for
`docs/controlled_external_review_handoff_pack.md`,
`docs/examples/gl222/controlled_external_review_handoff_pack.json`,
`scripts/ops/gl222_controlled_review_handoff_gate.py`, and
`backend/tests/test_gl222_controlled_external_review_handoff_pack.py`.
These are expected and are not real regressions.

---

## Reviewer-Safe Verification Commands

The following commands reproduce core verification locally. They require no
real credentials and produce no destructive side effects. All use synthetic
or demo data only.

```bash
# Core test suites
python3 -m unittest backend.tests.test_gl222_controlled_external_review_handoff_pack -v
python3 -m unittest backend.tests.test_gl221_workspace_enforcement_final_go_no_go_v6 -v
python3 -m unittest backend.tests.test_gl220_production_runtime_infrastructure_hardening_pack -v
python3 -m unittest backend.tests.test_gl219_production_identity_access_hardening_pack -v
python3 -m unittest backend.tests.test_gl218_public_external_review_export_safety_pack -v
python3 -m unittest backend.tests.test_gl217_production_go_no_go_v5 -v
python3 -m unittest backend.tests.test_gl216_production_operations_hardening_pack -v
python3 -m unittest backend.tests.test_gl215_tenant_workspace_production_guarantee -v
python3 -m unittest backend.tests.test_gl214_production_iam_operator_control_completion -v
python3 -m unittest backend.tests.test_security_boundary_regression -v
python3 -m unittest backend.tests.test_gl089_auth_default_fail_closed_startup -v

# First verifiable output
scripts/verify-first-output.sh

# Grant lifecycle evidence bundle (synthetic/demo only)
python3 examples/grant_lifecycle_evidence_bundle.py \
  --output /tmp/grantlayer_review_grant_lifecycle_check.json
diff -u examples/grant_lifecycle_evidence_bundle.json \
  /tmp/grantlayer_review_grant_lifecycle_check.json

# Dry-run/plan gate scripts (no real credentials required)
python3 scripts/ops/gl205_live_postgres_validation.py --dry-run
python3 scripts/ops/gl205_live_postgres_validation.py --plan
python3 scripts/ops/gl205_backup_restore_drill.py --dry-run
python3 scripts/ops/gl205_backup_restore_drill.py --plan
python3 scripts/ops/gl209_audit_export_check.py --dry-run
python3 scripts/ops/gl209_audit_export_check.py --plan
python3 scripts/ops/gl216_production_operations_gate.py --dry-run
python3 scripts/ops/gl216_production_operations_gate.py --plan
python3 scripts/ops/gl218_public_export_safety_scan.py --plan
python3 scripts/ops/gl219_identity_access_gate.py --dry-run
python3 scripts/ops/gl219_identity_access_gate.py --plan
python3 scripts/ops/gl220_runtime_infrastructure_gate.py --dry-run
python3 scripts/ops/gl220_runtime_infrastructure_gate.py --plan
python3 scripts/ops/gl221_workspace_go_no_go_gate.py --dry-run
python3 scripts/ops/gl221_workspace_go_no_go_gate.py --plan

# GL-222 handoff gate (local-only, dry-run/plan only)
python3 scripts/ops/gl222_controlled_review_handoff_gate.py --dry-run
python3 scripts/ops/gl222_controlled_review_handoff_gate.py --plan

# Full backend test suite (optional, ~9004 tests)
scripts/run-full-backend-suite.sh
```

---

## Security-Sensitive Reporting Instructions

Security-sensitive findings must be reported via:

**GitHub Security Advisories** — use the private security disclosure mechanism
on the GrantLayer GitHub repository.

Do **not** file security findings as public GitHub issues. Do **not** share
exploit details in public channels, pull request comments, or public forums.
Do **not** include real credentials, tokens, private keys, or customer data
in any security report.

Exploit details are excluded from all GL-222 materials. This policy is
consistent with SECURITY.md and has been in place since GL-153.

---

## Optional Handoff Gate Script Summary

`scripts/ops/gl222_controlled_review_handoff_gate.py` is a local-only,
dry-run/plan-only gate script. It:

- Verifies that `docs/controlled_external_review_handoff_pack.md` exists.
- Verifies that `docs/examples/gl222/controlled_external_review_handoff_pack.json`
  exists and is valid JSON.
- Verifies that the JSON contains `issue_id: GL-222`.
- Checks for forbidden file patterns (public export dirs, snapshot worktrees,
  setup.py, SDK pyproject.toml, package.json, deployment/cloud/Kubernetes files,
  TLS cert/key files, GitHub workflow changes for GL-222).
- Scans GL-222 documentation and artifact content for obvious secret-like text
  patterns, redacting any findings in output.
- Explicitly states in output that it is not approval to publish and not a full
  security audit.
- Does not create public export directories.
- Does not copy files to a public snapshot.
- Does not contact external services or require credentials.
- Does not run destructive commands.
- Does not modify repository files.

---

## Production-Readiness Impact

GL-222 has no impact on production readiness. It is documentation and
tooling only. All NO-GO decisions from GL-221 remain in force.

---

## Controlled-Preview Impact

GL-222 confirms that the Controlled External Technical Review posture remains
GO with strict boundaries. It provides the internal handoff documentation that
would be used if and when a review is initiated. It does not change the
controlled preview scope or the synthetic/demo-only data boundary.

---

## Remaining Blockers

| ID | Severity | Category | Description | Status |
|---|---|---|---|---|
| P0-production-saas | P0 | Production SaaS | No production SaaS readiness | Open |
| P0-real-data | P0 | Data | No real customer/private/institutional data readiness | Open |
| P0-compliance | P0 | Compliance | No compliance certification achieved | Open |
| P1-workspace | P1 | Workspace | workspace_id not production-enforced | Open |
| P1-iam | P1 | IAM | No OIDC/SAML/SSO/MFA; static admin token only | Open (Dev Preview OK) |
| P1-infra | P1 | Infrastructure | No production database or cloud infra | Open |
| P1-audit-workspace | P1 | Audit | Workspace propagation in audit/evidence not complete | Open |
| P1-cross-workspace | P1 | Isolation | Cross-workspace lookup/mutation denial not implemented | Open |

---

## Risk Register

| Risk | Severity | Status | Mitigation | Remaining Work |
|---|---|---|---|---|
| Workspace boundary overclaim | P0 | Open | Explicit NO-GO language and tests | Implement and verify workspace model |
| Real-data misuse in preview | P0 | Open | Synthetic/demo-only boundary enforced | Legal/security/data-governance approval |
| Public/export leakage | P1 | Controlled | GL-218 separate gate and scans | Manual export candidate review |
| Static admin token in production context | P1 | Open (Dev Preview OK) | Token is dev-only; never in production | Production IAM implementation |
| Missing database RLS | P1 | Open | Tenant-scoped app controls preserved | Production DB isolation implementation |
| Review boundary drift | P1 | Controlled | GL-222 handoff pack documents boundaries | Periodic boundary review |
| Reviewer receives prohibited materials | P1 | Controlled | GL-222 prohibited materials list | Pre-handoff export scan |
| Security-sensitive finding disclosed publicly | P1 | Controlled | GitHub Security Advisories routing | Reviewer briefing |

---

## Decision

`controlled_external_review_handoff_pack_ready_for_merge`

The handoff pack is complete. Controlled External Technical Review remains
GO with strict boundaries per GL-221 final readiness matrix v6. This pack
may be used to brief a future controlled external technical reviewer. No
public export, publish, or reviewer outreach is initiated by GL-222.

---

## Decision Rationale

GL-222 answers all ten required handoff questions. It documents the current
allowed review posture, eligible and prohibited materials, allowed and prohibited
claims, known limitations, known false-positive classes, reviewer-safe
reproduction commands, security-sensitive report routing, the public/export/
publish approval boundary, and the next roadmap. All NO-GO decisions from
GL-221 remain unchanged. No backend source, migrations, schema, dependencies,
GitHub workflows, snapshot publish scripts, or production deployment config
are modified. No public export is created. No reviewer is contacted.

---

## Safety Confirmations

- GL-222 is an internal controlled-review handoff pack, not reviewer outreach: YES
- GL-222 does not create a public export: YES
- GL-222 does not publish to public GitHub: YES
- GL-222 does not change repository visibility: YES
- GL-222 does not approve public snapshot/export/publish: YES
- Controlled External Technical Review is GO only with strict boundaries: YES
- Review materials remain synthetic/demo only: YES
- Production SaaS remains NO-GO: YES
- Real customer/private grant/institutional data remains NO-GO: YES
- Official SDK/package remains NO-GO: YES
- Compliance certification remains NO-GO: YES
- Live PostgreSQL production readiness remains NO-GO: YES
- Security-sensitive reports route to GitHub Security Advisories: YES
- No exploit details included: YES
- No real secrets included: YES
- No real customer/private data included: YES
- No backend/src changes: YES
- No migrations/DB/schema/dependency changes: YES
- No GitHub workflow changes: YES
- No snapshot publish script changes: YES
- No package publishing metadata: YES
- No deployment/cloud/Kubernetes/Terraform/Helm changes: YES
- No TLS certificate/private key files: YES
- No public snapshot export directory: YES
- No public snapshot worktree: YES
- No force-push: YES
- Unrelated website-design/import files excluded: YES
- GL-214 IAM/operator-control hardening preserved: YES
- GL-215 tenant/workspace guarantees preserved: YES
- GL-216 production operations hardening preserved: YES
- GL-217 Go/No-Go v5 decisions preserved: YES
- GL-218 public/export safety boundaries preserved: YES
- GL-219 identity/access hardening preserved: YES
- GL-220 runtime/infrastructure hardening preserved: YES
- GL-221 final Go/No-Go v6 decisions preserved: YES

---

## Recommended Next Issues

| Issue | Title | Priority |
|---|---|---|
| GL-223 | Workspace Identity / Membership / Ownership Implementation Plan | P1 |
| GL-224 | Workspace-Scoped Lookup and Mutation Enforcement | P1 |
| GL-225 | Workspace Propagation for Evidence / Provenance / Audit / Compliance / Export | P1 |
| GL-226 | Production Identity Provider Readiness Gate (OIDC/SAML/SSO/MFA) | P1 |
| GL-227 | Live PostgreSQL Production Readiness Gate | P1 |
| GL-228 | Production Backup / Restore Automation | P1 |
| GL-229 | Production Observability Stack Baseline | P1 |
| GL-230 | Compliance Certification Readiness Assessment | P0 |
