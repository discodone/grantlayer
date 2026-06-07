# GL-218 — Public / External Review Export Safety Pack

**Issue ID:** GL-218
**Title:** Public / External Review Export Safety Pack
**Branch:** `gl-218-public-external-review-export-safety-pack`
**Status:** Internal / Developer Preview

GL-218 is a safety pack, not a public export or publish. No public
snapshot or export directory is created by GL-218.
No public GitHub push is performed by GL-218.
No repository visibility change is performed by GL-218.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Controlled external technical review remains allowed only with
strict boundaries. Controlled preview and external review remain
synthetic/demo-data only. Production SaaS remains NO-GO. Real
customer/private grant/institutional data remains NO-GO. Official SDK/package
remains NO-GO. Compliance certification remains NO-GO. Live PostgreSQL
production readiness remains NO-GO. Public snapshot preparation is conditional
and requires a later explicit gate and separate approval. Public website publish
remains deferred/no-go unless a later explicit publish gate approves it.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is included.

Unrelated website-design/import files (`website-design/`,
`docs/website_design_workspace_import_report.md`,
`docs/website_design_workspace_import_report_dirty_stop.md`,
and similarly named files) are excluded from GL-218.

---

## Context

GL-214 (Production IAM & Operator Control Completion), GL-215 (Tenant /
Workspace Production Guarantee), GL-216 (Production Operations Hardening
Pack), and GL-217 (Production Go/No-Go v5) are merged internally. GL-217
produced the following final decisions:

| Tier | Decision |
|---|---|
| Developer Preview | GO / CONTINUE |
| Controlled External Technical Review | GO with strict boundaries |
| Synthetic/Demo Controlled Pilot | CONDITIONAL |
| Public Snapshot Preparation | CONDITIONAL — separate gate required |
| Public Website Publish | DEFER / NO-GO |
| Official SDK / Package | NO-GO |
| Real Customer Data | NO-GO |
| Private Grant / Institutional Data | NO-GO |
| Production SaaS | NO-GO |
| Compliance Certification | NO-GO |
| Live PostgreSQL Production Readiness | NO-GO |

GL-217 post-merge full suite baseline: 8847 tests / 43 failures / 3 errors /
253 skipped / 0 real regressions.

GL-218 prepares a safety gate for a possible future public/external review
export. It documents what is and is not eligible for such an export, what
claims are permitted, and what checks must pass before any export may proceed.
It does not create the export.

---

## Scope

GL-218 covers:
- Assessment of which files and content are eligible for a future external
  review export candidate
- Explicit documentation of excluded internal/private materials
- Allowed and prohibited public-facing claim boundaries
- No-real-data, no-secret, and no-internal-infrastructure safety checks
- No-package/publish/deployment/cloud safety checks
- No-production-claim, no-official-SDK/package, no-compliance-certification,
  and no-live-PostgreSQL-production safety checks
- Public website publish boundary
- Controlled external review boundary and synthetic/demo-data-only boundary
- Prerequisites and explicit approval requirements before any public push/export/publish
- Risk register for external review export
- Remaining blockers before any public export or public publish
- Optional local-only dry-run safety scan helper

## Non-Goals

GL-218 does not:
- Create a public export, public snapshot, public export directory, or public
  snapshot worktree
- Push to public GitHub or change repository visibility
- Create a public release branch, public release tag, or release metadata
- Perform reviewer outreach or public announcement
- Create GitHub issues or labels through API
- Run public snapshot publish scripts or change snapshot publish scripts
- Change GitHub workflows
- Add package publishing metadata, SDK pyproject.toml, setup.py, package.json,
  or package-lock.json
- Turn the internal SDK prototype into an official SDK/package
- Add production credentials, external hostnames, analytics, tracking, or forms
- Add deployment, cloud, Kubernetes, Terraform, or Helm files
- Change backend/src, add migrations, or change DB/schema/dependency files
- Claim Production SaaS readiness
- Claim real customer/private grant/institutional data readiness
- Claim official SDK/package availability
- Claim live PostgreSQL production readiness
- Claim compliance certification, GDPR, SOC2, ISO, or enterprise readiness
- Include exploit details, real secrets, real customer data, or private grant data
- Include internal Forgejo URLs, private hostnames, private IPs, internal
  filesystem paths, or private operator details in public/exportable content

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/production_operations_hardening_pack.md | Yes |
| docs/examples/gl216/production_operations_hardening_pack.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/production_readiness_gap_report_v4.md | Yes |
| docs/examples/gl213/production_readiness_gap_report_v4.json | Yes |
| docs/public_external_review_readiness_gate_pack.md | Yes |
| docs/examples/gl212/public_external_review_readiness_gate_pack.json | Yes |
| docs/public_snapshot_external_review_checklist.md | Yes |
| docs/sdk_pilot_production_gate.md | Yes |
| docs/examples/gl211/sdk_pilot_production_gate.json | Yes |
| docs/website_track.md | Yes |
| docs/examples/gl210/website_track.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/claim_safety_controlled_preview_boundary.md | Yes |
| docs/examples/gl207/claim_safety_controlled_preview_boundary.json | Yes |
| docs/live_postgres_validation_execution_gl206b.md | Yes |
| docs/examples/gl206b/live_postgres_validation_execution_gl206b.json | Yes |
| docs/live_postgres_backup_observability_baseline.md | Yes |
| docs/examples/gl205/live_postgres_backup_observability_baseline.json | Yes |
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| website/index.html | Yes |
| examples/first_verifiable_output.json | Yes |
| examples/grant_lifecycle_evidence_bundle.json | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |
| scripts/verify-first-output.sh | Yes |
| scripts/ops/gl216_production_operations_gate.py | Yes |
| scripts/ops/gl205_live_postgres_validation.py | Yes |
| scripts/ops/gl205_backup_restore_drill.py | Yes |
| scripts/ops/gl209_audit_export_check.py | Yes |

---

## Current Public / External Review Posture

GrantLayer is Developer Preview / Controlled Preview with strict boundaries
after GL-214, GL-215, GL-216, and GL-217.

**Baseline controls in place:**
- Fail-closed production-like config checks (GL-201)
- Operator token hashing PBKDF2-HMAC-SHA256 and tenant binding (GL-206)
- Admin token constant-time comparison and fail-closed route guards (GL-201, GL-206)
- Operator role vocabulary constrained to owner/grant_admin/auditor (GL-214)
- Durable audit-chain events for operator create/revoke (GL-214)
- Tenant-filtered primary and secondary execution-derived routes (GL-215)
- Cross-tenant direct-ID mutation denied on demo path (GL-215)
- Append-only hash-chained audit events (GL-209)
- Safe synthetic backup/restore and audit export check scripts (GL-205, GL-209)
- Ephemeral live PostgreSQL validation passed with synthetic/demo data (GL-206B)
- Structured logging, correlation IDs, redaction helpers (GL-208)
- Runtime abuse and rate-limit baseline (GL-208)
- Production operations posture documentation and local-only dry-run gate script (GL-216)
- Claim-safety corrections across README, SECURITY, AGENTS, llms.txt, llms-full.txt (GL-207)

**Not production-complete:**
- No OIDC/SAML/SSO/MFA or enterprise IAM
- Static admin token not resolved
- No workspace-level enforcement or database RLS
- No tenant provisioning API
- No production runbook, SLO, or DR playbook
- No independent security audit or compliance review

---

## Export Candidate Safety Assessment

A future export candidate is only permitted under the following conditions:

1. A dedicated later issue (not GL-218) explicitly authorises the export.
2. An explicit approval by the repository owner is obtained before any push or publish.
3. The candidate passes all forbidden-file, secret, real-data, overclaim, package-metadata,
   workflow, and deployment-config scans documented below.
4. The candidate is reviewed for internal-infrastructure leakage (Forgejo URLs, private
   IPs, private hostnames, internal filesystem paths, private operator details).
5. The candidate uses only synthetic/demo data — no real customer data, no private grant
   data, no institutional data.
6. The candidate makes no overclaimed production, compliance, or SDK/package claims.

**GL-218 does not create, prepare, or validate any export candidate.**

---

## Eligible Public / External Review Materials

The following categories are eligible for inclusion in a future controlled external
review export candidate (subject to per-file claim review and secret scan):

- `README.md` — reviewed, claim-safe after GL-207 corrections
- `SECURITY.md` — reviewed, routes security reports to GitHub Security Advisories
- `AGENTS.md` — reviewed, claim-safe
- `llms.txt` — reviewed, claim-safe
- `llms-full.txt` — reviewed, claim-safe
- `docs/openapi.yaml` — reviewed, API contract only, no real credentials
- `website/index.html` — reviewed static website baseline, no production hosting implied
- `examples/first_verifiable_output.py` — local-only, no real secrets, no customer data
- `examples/first_verifiable_output.json` — synthetic reference artifact
- `examples/grant_lifecycle_evidence_bundle.py` — local-only, synthetic/demo data only
- `examples/grant_lifecycle_evidence_bundle.json` — synthetic evidence bundle
- `scripts/verify-first-output.sh` — local-only verification helper
- `scripts/ops/gl205_live_postgres_validation.py` — dry-run/plan mode only, no real credentials
- `scripts/ops/gl205_backup_restore_drill.py` — dry-run/plan mode only, no real credentials
- `scripts/ops/gl209_audit_export_check.py` — dry-run/plan mode only, no real credentials
- `scripts/ops/gl216_production_operations_gate.py` — dry-run/plan mode only, local-only
- `scripts/ops/gl218_public_export_safety_scan.py` — dry-run/scan mode only, local-only
- Reviewed backend source files (no real secrets, no private credentials, no private
  infrastructure references) — subject to per-file review before export
- Reviewed test files that use only synthetic/demo data
- Reviewed docs/ artifacts for resolved issues (not internal-infrastructure references)

All eligibility is conditional. Each file must pass the secret scan,
real-data scan, overclaim scan, internal-path scan, and package-metadata scan
before inclusion in any export candidate.

---

## Excluded Materials

The following must never appear in a public export or external review package:

**Secrets and credentials:**
- `.env*` files, `*.env`, environment files with real credentials
- Raw PostgreSQL DSNs (`postgresql://...`) with real hostnames or passwords
- Raw tokens, token hashes, auth headers, Bearer tokens, API keys
- Private keys (RSA, OPENSSH, EC, DSA or similar PEM blocks)
- Real admin tokens or operator tokens
- Real SMTP, S3, or cloud credentials

**Real data:**
- Real customer data, real grant applications, real funding records
- Real institutional data, real personal data (PII/GDPR-scope)
- Real private grant data or private attachments
- Database dumps, backup files, or logs containing real data

**Internal infrastructure:**
- Internal Forgejo URLs (e.g. `forgejo.internal`, `git.internal`, private Forgejo host)
- Private IP addresses, private hostnames, private network identifiers
- Internal filesystem paths (e.g. `/home/adminuser/...`, `/srv/internal/...`)
- Private operator usernames, private operator workspace IDs
- Internal CI/CD configuration referencing private services

**Forbidden files and paths:**
- `website-design/` directory and all contents
- `docs/website_design_workspace_import_report.md`
- `docs/website_design_workspace_import_report_dirty_stop.md`
- Any `docs/website_design_*` or `docs/website-design-*` import/report files
- `setup.py`, SDK `pyproject.toml`, `package.json`, `package-lock.json`
- Package publishing config, package registry metadata
- Analytics/tracking integrations, data collection forms
- GitHub Actions workflow files (`.github/workflows/`) without separate review
- Snapshot publish scripts unless separately reviewed
- Production deployment config (Kubernetes, Terraform, Helm, cloud provider)
- Release metadata, release tags, public release branches
- `data/` directory contents with real operational data
- `.git/` directory, local caches, virtual environments, `__pycache__/`
- Any file matching `.gitignore` patterns

---

## Allowed Public Claims

The following claims are permitted in public/external review materials:

- GrantLayer is in **Developer Preview** and **Controlled Preview with strict boundaries**
- Local evaluation and controlled pilot only
- Tenant/workspace isolation: baseline implemented, not production-complete
- Ephemeral live PostgreSQL validation passed with synthetic/demo data (GL-206B)
- Fail-closed auth baseline implemented (not production-grade IAM)
- Append-only hash-chained audit baseline implemented
- Operator token hashing and tenant binding implemented
- Structured logging and rate-limit baseline implemented
- Controlled external technical review is allowed **only with strict boundaries and synthetic/demo data**
- All examples use synthetic identifiers only — no real customer data
- All tokens and keys in examples are placeholders
- Security-sensitive reports route to GitHub Security Advisories
- Production SaaS is not claimed and not supported
- Real customer/private grant/institutional data is not ready
- Official SDK/package is not published

---

## Prohibited Public Claims

The following claims must never appear in public/external review materials:

- Production SaaS ready / production-grade / enterprise ready
- Ready for real customer data / private grant data / institutional data
- Claimed compliance certification, GDPR certification, SOC2 certification, ISO certification, or enterprise-grade compliance
- Official SDK available / official package published / SDK production-ready
- Live PostgreSQL production ready / production PostgreSQL deployment supported
- Independent security audit completed / penetration test passed
- Multi-tenant production isolation guaranteed / database RLS enforced
- OIDC / SAML / SSO / MFA implemented
- Public website is a production marketing launch
- Any claim implying a support SLA or uptime guarantee
- Any claim that implies real customer deployments are running

---

## No-Real-Data Safety Assessment

| Check | Status |
|---|---|
| All examples use synthetic identifiers | Confirmed |
| No real customer data in tracked files | Confirmed |
| No real private grant or institutional data in tracked files | Confirmed |
| No real personal data (PII) in tracked files | Confirmed |
| Database dump or backup with real data not in tracked files | Confirmed |
| `data/` directory contents not included in export candidate | Required before export |
| Any new file added before export must pass real-data scan | Required before export |

**Assessment:** No real data is present in currently tracked candidate files.
A per-file real-data scan is required before any export candidate is created.

---

## No-Secret Safety Assessment

| Check | Status |
|---|---|
| No raw DSNs with real credentials in tracked files | Confirmed |
| No raw tokens, auth headers, or Bearer tokens in tracked files | Confirmed |
| No PEM private key blocks in tracked files | Confirmed |
| No real admin tokens or operator tokens in tracked files | Confirmed |
| No `.env*` files with real credentials tracked | Confirmed |
| No SMTP/S3/cloud credentials in tracked files | Confirmed |
| Secret-pattern scan required before any export | Required before export |

**Assessment:** No obvious secret patterns detected in currently reviewed
candidate files. A dedicated secret-pattern scan (see gl218_public_export_safety_scan.py)
must pass before any export candidate is created or pushed.

---

## Internal Infrastructure Leakage Assessment

| Check | Status |
|---|---|
| No internal Forgejo URLs in intended export files | Confirmed for reviewed files |
| No private IP addresses or hostnames in export files | Confirmed for reviewed files |
| No internal filesystem paths in export files | Confirmed for reviewed files |
| No private operator usernames/workspace IDs in export files | Confirmed for reviewed files |
| SECURITY.md references public GitHub URL only | Confirmed |
| README.md references public GitHub URL only in public-facing sections | Confirmed |
| Internal-path scan required before any export | Required before export |

**Assessment:** Reviewed candidate files do not contain detected internal
infrastructure references. An internal-path scan must be run before any export.

---

## Package / Publish Metadata Assessment

| Check | Status |
|---|---|
| No `setup.py` in tracked files | Confirmed |
| No SDK `pyproject.toml` in tracked files | Confirmed |
| No `package.json` or `package-lock.json` in tracked files | Confirmed |
| No package registry metadata in tracked files | Confirmed |
| No `publish` or `release` script in tracked files | Confirmed for reviewed files |
| No `.github/workflows/` changes in GL-218 | Confirmed |
| No snapshot publish script changes in GL-218 | Confirmed |

**Assessment:** No package/publish/deployment/cloud metadata is present in
tracked candidate files or added by GL-218.

---

## Public Snapshot / Export Boundary

A public snapshot or export may only proceed when:

1. A dedicated later issue (not GL-218) creates and scans the export candidate.
2. Explicit approval from the repository owner is obtained.
3. All forbidden-file, secret, real-data, overclaim, internal-path, and
   package-metadata scans pass with zero findings.
4. The candidate preserves all Developer Preview / Controlled Preview claim boundaries.
5. No production SaaS, real-data, compliance, official-SDK/package, or
   live-PostgreSQL-production claims appear.
6. The export does not include internal Forgejo URLs, private IPs, private hostnames,
   internal paths, or private operator details.

**GL-218 does not create, validate, or approve any public snapshot or export.**
The public snapshot preparation decision from GL-217 remains:
**CONDITIONAL — separate explicit gate and approval required.**

---

## Public Website Publish Boundary

- Public website publish remains **DEFERRED / NO-GO** as of GL-217.
- `website/index.html` exists as a static baseline only — it is not a production
  marketing site and must not be deployed as one.
- No production hosting, CDN, analytics, or tracking may be added without a
  separate explicit publish gate.
- GL-218 does not change the website publish boundary.

---

## Controlled External Review Boundary

Controlled external technical review is permitted under the following strict boundaries:

- Synthetic/demo data only — no real customer data, no private grant data, no
  institutional data under any circumstances
- Reviewer must be informed that GrantLayer is Developer Preview with strict
  boundaries and is not production-grade
- No production SaaS implication — reviewer must not deploy to shared multi-tenant
  infrastructure or use with real users
- Security-sensitive findings must be reported via GitHub Security Advisories, not
  public issues or comments
- No compliance implication — reviewer must not interpret review as compliance
  certification or security audit
- No official SDK/package implication — the internal SDK prototype is not a published
  package
- No live PostgreSQL production implication — production PostgreSQL readiness is NO-GO
- Review materials must pass the export safety scan before being shared

---

## Synthetic / Demo Data Only Boundary

All controlled preview, controlled external review, and any future export candidate must:
- Use only synthetic identifiers (e.g. `grant-synth-001`, `tenant-demo-01`)
- Use only placeholder tokens and keys (e.g. `changeme`, `placeholder-token`)
- Not include any real grant application, funding record, institutional record, or personal data
- Not connect to any real PostgreSQL instance with production data
- Not transmit any real data to external services

This boundary applies to:
- All examples (`examples/`)
- All test fixtures and test data
- All scripts run in dry-run or plan mode
- Any export candidate prepared for external review

---

## Official SDK / Package Boundary

- The internal SDK prototype exists in `sdk/` as a local development aid.
- It is not an official SDK, not a published package, and not a supported library.
- No `setup.py`, SDK `pyproject.toml`, `package.json`, or package registry metadata
  exists or may be added without a separate SDK release gate.
- GL-218 does not change the official SDK/package boundary.
- This boundary remains: **NO-GO**.

---

## Production SaaS Boundary

- GrantLayer is not production SaaS ready.
- Multiple P0 blockers remain: static admin token, no workspace enforcement, no
  database RLS, no OIDC/SAML/SSO/MFA, no production runbook, no independent security audit.
- No shared multi-tenant deployment is permitted.
- No real user data may be processed.
- This boundary remains: **NO-GO**.

---

## Compliance Certification Boundary

- No compliance certification is claimed or in progress.
- GDPR, SOC2, ISO, and enterprise-grade compliance assessments have not been performed.
- No independent security audit or penetration test has been completed.
- This boundary remains: **NO-GO**.

---

## Live PostgreSQL Production Readiness Boundary

- Ephemeral live PostgreSQL validation passed in GL-206B with synthetic/demo data only.
- That result closed the specific ephemeral validation execution gap only.
- Production PostgreSQL deployment (persistent, multi-tenant, with production data)
  is not supported and not claimed.
- This boundary remains: **NO-GO**.

---

## Optional Scan Helper Summary

A local-only dry-run safety scan helper has been added:

**`scripts/ops/gl218_public_export_safety_scan.py`**

The script:
- Is local-only and scan-only by default
- Does not create a public export directory or copy files to a public snapshot
- Does not push anywhere or contact external services
- Does not require credentials
- Does not run destructive commands
- Does not modify repository files
- Scans the current worktree for obvious forbidden public/export indicators
- Checks for package/publish/deployment/public-snapshot forbidden paths
- Checks for obvious secret-like patterns in intended exportable files
- Checks that production/real-data/compliance/official-SDK/live-Postgres claims
  are not overclaimed in public-facing files
- Checks that public snapshot/export remains conditional and separate-gate only
- Redacts matched secret-like values in output
- Explicitly states it is not a complete security audit and not approval to publish
- Supports `--dry-run` and `--plan` modes

The script is not a substitute for a dedicated security audit and does not
constitute approval to publish.

---

## Production Readiness Impact

GL-218 has no production readiness impact. It is a safety pack only.

- No backend/src changes are made.
- No migration, schema, or dependency changes are made.
- No new production controls are added.
- No production blockers are resolved.
- P0/P1/P2 blocker status is unchanged from GL-217.

---

## Controlled Preview Impact

GL-218 has no controlled preview impact beyond documentation.

- Controlled external technical review remains: **GO with strict boundaries**
- Synthetic/demo controlled pilot remains: **CONDITIONAL**
- Developer Preview remains: **GO / CONTINUE**
- Public snapshot preparation remains: **CONDITIONAL — separate gate required**

---

## Remaining Blockers

All P0 blockers from GL-217 remain open:

| ID | Category | Blocker |
|---|---|---|
| PB-001 | IAM | Static admin token in auth baseline; no OIDC/SAML/SSO/MFA |
| PB-002 | Tenant/Workspace | No workspace-level enforcement; no database RLS |
| PB-003 | Tenant Lifecycle | No tenant provisioning API; no deprovision/offboarding flow |
| PB-004 | Data Governance | No production data retention/deletion pipeline; no DSAR |
| PB-005 | Operations | No production runbook; no SLO definition; no DR playbook |
| PB-006 | Observability | No production alerting, on-call rotation, or SLO dashboards |
| PB-007 | Security Audit | No independent security audit or penetration test |
| PB-008 | Compliance | No GDPR, SOC2, ISO, or enterprise compliance assessment |
| PB-009 | PostgreSQL | No persistent multi-tenant PostgreSQL deployment |
| PB-010 | Export Safety | No vetted export candidate; public snapshot requires separate gate |

---

## Risk Register

| Risk ID | Category | Description | Severity | Mitigation |
|---|---|---|---|---|
| RR-001 | Secret Leakage | Future export candidate may inadvertently include real secrets | Critical | Run gl218_public_export_safety_scan.py before any export; require explicit approval |
| RR-002 | Real Data Exposure | Future export may include real customer/grant/institutional data | Critical | Enforce synthetic/demo data only boundary; scan before export |
| RR-003 | Overclaim Drift | Future materials may drift to overclaim production/compliance readiness | High | Prohibited-claim list; automated scan; claim review gate required |
| RR-004 | Infrastructure Leakage | Export may include internal Forgejo URLs, private IPs, or internal paths | High | Internal-path scan required; review all new docs before export |
| RR-005 | Package Metadata | A contributor may add setup.py, pyproject.toml, or package.json | High | Scope guard tests block forbidden package files in GL-218 branch |
| RR-006 | Workflow Change | A contributor may change GitHub workflows or snapshot publish scripts | High | Scope guard tests block workflow changes in GL-218 branch |
| RR-007 | Premature Export | An export is created before a separate gate approves it | High | GL-218 explicitly does not create an export; requires a later issue |
| RR-008 | Controlled Review Misuse | An external reviewer uses real data or deploys to shared infrastructure | Medium | Reviewer briefing required; strict boundary documented |
| RR-009 | SDK/Package Claim | SDK prototype is presented as an official published package | Medium | Prohibited-claim list; scope guards block SDK package metadata |
| RR-010 | Compliance Claim | Developer Preview materials are interpreted as compliance certification | Medium | Prohibited-claim list; SECURITY.md explicit non-claim language |

---

## Decision

**GL-218 is a safety pack / scan / checklist only.**

- This issue is: **ready_for_merge**
- No public export is created.
- No public GitHub push is performed.
- No repository visibility change is performed.
- All prior safety boundaries from GL-207 through GL-217 are preserved.

---

## Decision Rationale

GL-218 documents the safety boundaries for a possible future public/external
review export. It answers the six required questions (eligible files, excluded
files, allowed/prohibited claims, required checks, required approvals, and
remaining blockers) without creating the export itself. A local-only dry-run
safety scan helper is added. No production, real-data, compliance, official-SDK,
or live-PostgreSQL-production claims are made. All hard rules are observed.

---

## Safety Confirmations

| Confirmation | Status |
|---|---|
| GL-218 does not create a public export or public snapshot | Confirmed |
| GL-218 does not push to public GitHub | Confirmed |
| GL-218 does not change repository visibility | Confirmed |
| GL-218 does not merge to main | Confirmed |
| Production SaaS is NO-GO | Confirmed |
| Real customer/private grant/institutional data is NO-GO | Confirmed |
| Official SDK/package is NO-GO | Confirmed |
| Compliance certification is NO-GO | Confirmed |
| Live PostgreSQL production readiness is NO-GO | Confirmed |
| Controlled external review requires strict boundaries and synthetic/demo data | Confirmed |
| Public snapshot/export requires later explicit gate and approval | Confirmed |
| Public website publish is deferred/no-go | Confirmed |
| No exploit details included | Confirmed |
| No real secrets included | Confirmed |
| No real customer/private data included | Confirmed |
| No backend/src changes | Confirmed |
| No migrations/DB/schema/dependency changes | Confirmed |
| No GitHub workflow changes | Confirmed |
| No snapshot publish script changes | Confirmed |
| No package publishing metadata added | Confirmed |
| No production deployment/cloud/Kubernetes/Terraform/Helm files added | Confirmed |
| Unrelated website-design/import files excluded | Confirmed |
| Security-sensitive reports route to GitHub Security Advisories | Confirmed |

---

## Recommended Next Issues

| Issue | Title | Priority |
|---|---|---|
| GL-218 Merge | Merge GL-218 to internal main | Immediate |
| GL-219 | Production Identity & Access Hardening Pack | High — resolves PB-001 |
| GL-220 | Production Runtime & Infrastructure Hardening Pack | High — resolves PB-005, PB-006 |
| GL-221 | Workspace Enforcement & Final Go/No-Go v6 | High — resolves PB-002, PB-003 |
