# GL-195 Public Safety / Scanner / Claim Consistency Gate

## Issue ID

GL-195

## Title

Public Safety / Scanner / Claim Consistency Gate

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture (GL-176).

The sequence GL-187 through GL-194 delivered: stale public docs cleanup,
a first-output verify helper, a grant lifecycle evidence bundle, a demo
endpoint safety guard, a developer experience polish pack, a public feedback
infrastructure, a public agent/API walkthrough refresh, and a public preview
review & feedback triage pack (GL-194).

GL-194 identified the need for a consolidated public safety, scanner, and claim
consistency gate (GL-195). This issue creates that gate as a review/docs/test
artifact only. It does not implement backend features, change GitHub settings,
or send outreach.

---

## Current Public Preview State

| Posture | Value |
|---------|-------|
| Release label | **GL-0.1 / Developer Preview** |
| Maturity | Local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub repository | **Available** — `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Public snapshot | Clean developer-facing snapshot — no internal paths, no real secrets |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

---

## Scope

This issue is **review / docs / test / artifact only.**

Allowed files created:
- `docs/public_safety_scanner_claim_consistency_gate.md` (this file)
- `docs/examples/gl195/public_safety_scanner_claim_consistency_gate.json`
- `backend/tests/test_gl195_public_safety_scanner_claim_consistency_gate.py`

This issue does **not**:
- implement backend features
- change GitHub settings, labels, or issues via API
- send reviewer outreach
- push to GitHub
- change database schema, migrations, or OpenAPI
- change dependency manifests
- change SDK or examples runtime
- change frontend, website, or design
- claim production SaaS readiness
- claim tenant isolation is implemented

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| README.md | yes |
| SECURITY.md | yes |
| CONTRIBUTING.md | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes (header and map) |
| docs/first_output_verify_helper.md | yes |
| docs/grant_lifecycle_evidence_bundle.md | yes |
| docs/public_developer_experience_polish_pack.md | yes |
| docs/public_feedback_infrastructure_pack.md | yes |
| docs/public_agent_api_walkthrough_refresh.md | yes |
| docs/public_preview_review_feedback_triage_pack.md | yes |
| docs/examples/gl191/public_developer_experience_polish_pack.json | referenced |
| docs/examples/gl192/public_feedback_infrastructure_pack.json | referenced |
| docs/examples/gl193/public_agent_api_walkthrough_refresh.json | referenced |
| docs/examples/gl194/public_preview_review_feedback_triage_pack.json | yes |
| examples/first_verifiable_output.py | smoke-tested |
| examples/first_verifiable_output.json | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.py | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.json | smoke-tested |
| scripts/verify-first-output.sh | smoke-tested |

---

## Current Public Safety Posture

The public snapshot was established via a clean explicit workflow (GL-176,
GL-179, GL-181) and has been reviewed after each subsequent public publish.
The most recent published commit is `48caad1b2db638d733b528a12bb9e269e9a6d4fe`
(GL-194 public publish).

Key confirmed posture points:
- No private data, private keys, real secrets, or internal infrastructure found.
- All examples use synthetic identifiers and placeholder tokens.
- Production SaaS readiness is explicitly not claimed in all entry points.
- Tenant/workspace isolation is explicitly documented as not implemented.
- Security-sensitive reports are routed to GitHub Security Advisories.
- Public snapshot was not produced by a direct internal repo push to GitHub.
- No force push has been used to produce the current public snapshot.

---

## Scanner Rule Review

### Scanner Blocker Categories

The following categories, if found in the public snapshot, are **blockers**
that must be resolved before any subsequent public publish:

| Category | Example Indicators |
|----------|--------------------|
| Raw secret material | Actual API keys, Bearer tokens, passwords, private keys (PEM blocks) |
| Real API keys / tokens / passwords | Strings matching `sk-`, `ghp_`, `eyJ` JWT patterns with real payloads |
| Private customer data | Real customer names, addresses, identifiers, emails, phone numbers |
| Private grant or institutional data | Real grant IDs, institution names, PII from real grant workflows |
| Private internal hostnames or remotes | Forgejo host, internal VM IPs, internal git remote URLs |
| Private absolute paths in public-facing docs | `/home/adminuser/`, `/home/adminuser/projects/`, internal Forgejo paths |
| Exploit details in public docs/issues | Reproduction steps for unpatched vulnerabilities |
| Instruction to push internal repo directly to GitHub | Any script or doc that calls `git push github` on internal remote |
| Force-push requirement for public snapshot | Any publish step that requires `git push --force` |
| Public claim that production SaaS is ready | Any uncaveated statement that the service is ready for production tenants |
| Public claim that tenant isolation is implemented | Any statement that tenant/workspace boundaries are enforced |

### Scanner Non-Blocking False-Positive Categories

The following categories trigger scanner pattern matches but are **expected
non-blocking false positives** when correctly documented:

| FP Class | Why Non-Blocking | Record As | Becomes Blocking If |
|----------|-----------------|-----------|---------------------|
| `prohibition-text` | Safety rules like "do not include secrets" contain the keywords but are not secrets. | FP, document in scanner log. | The surrounding context changes to include actual secret material. |
| `safety-faq-answered-no` | FAQ questions like "Is tenant isolation implemented?" followed by "No" / "Not implemented" are correctly stating the caveat. | FP, document in scanner log. | The answer changes to "Yes" or the caveat is removed. |
| `scanner-pattern-definitions` | This gate document and the JSON artifact contain the prohibited-phrase patterns as documentation. Scanners will match their own definitions. | FP, document in scanner log. | The pattern definitions are moved into executable code or deployment config. |
| `meta-excluded-governance-docs` | GL-177/178/179/180 governance docs (visibility decision, dry-run, correction-push, exclusion-cleanup) contain historical pre-public phrases and are explicitly excluded from the public snapshot. | FP, document in scanner log. | Those docs are un-excluded from the public snapshot and published. |
| `historical-scope-guard-tests` | Old scope-guard tests that fail because newer GL issue files exist (e.g. GL-186 scope-guard tests that did not anticipate GL-195 files) are pre-existing known FPs. | FP, pre-existing known issue. | A scope-guard test fails for a file in an actively prohibited scope. |

---

## Stale Public-State Phrase Rules

The following phrases are stale indicators from pre-public cycles and **must
not appear** in public-facing entry docs (README.md, AGENTS.md, llms.txt,
SECURITY.md, CONTRIBUTING.md, docs/ten_minute_quickstart.md,
docs/agent_quickstart.md):

| Phrase | Reason Stale |
|--------|--------------|
| `publication pending` | Repository is already public (GL-176). |
| `public GitHub release has not happened` | Repository is already public (GL-176). |
| `visibility decision pending` | Visibility decision completed (GL-175). |
| `formal visibility decision pending` | Visibility decision completed (GL-175). |
| `approved internal source` | Repository is public; no approval required to access. |
| `if and when public publication is approved` | Publication has occurred; this condition is already satisfied. |

Historical governance docs that contain these phrases for archival purposes
are excluded from the public snapshot (GL-181) and are not subject to this
stale-phrase rule.

Old stale test-count claims such as literal strings "1130 tests / 3 skipped /
0 failures" from pre-public baseline counts should not appear in public entry
docs. Current suite counts change with each GL issue and should be described
as "thousands of tests" or linked to the full suite runner rather than stated
as fixed numbers.

---

## Claim Consistency Rules

### Required Public Caveats

All public entry-point docs (README.md, AGENTS.md, llms.txt, SECURITY.md) and
all public feedback/issue templates must include or clearly reference:

| Required Caveat | Enforcement |
|----------------|-------------|
| Developer Preview / technical preview posture | Present in all four entry-point docs |
| Not production SaaS | Present in all four entry-point docs |
| Tenant/workspace isolation not implemented | Present in all four entry-point docs |
| Synthetic/demo data only — no real customer data | Present in all examples and quickstarts |
| No real secrets — all tokens are placeholders | Present in all examples and quickstarts |
| No real private grants or institutional data | Present in examples and key hygiene doc |
| Security-sensitive reports route to GitHub Security Advisories | Present in SECURITY.md and all feedback templates |

### Prohibited Public Claims

The following claims are prohibited in any public file unless actually true
and explicitly approved:

| Prohibited Claim | Rationale |
|-----------------|-----------|
| Production-ready SaaS | Not true; hardening gates incomplete |
| Tenant isolation implemented | Not true; explicitly documented as not implemented |
| Safe for real customer data | Not true; data layer is local/demo only |
| Safe for real grant or institutional data | Not true; no data handling guarantees |
| Full security or compliance guarantee | Not true; security model is developer-preview only |
| Production deployment complete | Not true; no production deployment exists |
| Official SDK or package published (if not actually published) | SDK is minimal; no PyPI release |
| Hidden or stale "publication pending" claims after repo is public | Misleading; public since GL-176 |

---

## Public Caveat Rules

The following caveat rules apply to every issue, pull request, and doc:

1. Always include "Developer Preview" or "technical preview" when describing
   the maturity of the project to an external audience.
2. Never state the backend is "production-ready" or suitable for "production
   tenants" without completing the hardening gate sequence.
3. Always state "tenant isolation is not implemented" whenever describing
   multi-user or multi-organization scenarios.
4. Always state "synthetic/demo data only" when describing example data.
5. Route all security-sensitive reports to GitHub Security Advisories — never
   encourage plain public issues for vulnerability reports.

---

## GitHub Publish Safety Rules

The following rules govern how the public snapshot is published and maintained:

| Rule | Requirement |
|------|-------------|
| Clean snapshot workflow | Use the explicit exclusion-list workflow (GL-181), never a raw push of internal remote |
| No force push | Public snapshot must be produced via non-destructive push only |
| No visibility change without explicit approval | Visibility changes require a dedicated go/no-go gate (GL-175) |
| No direct internal repo push to GitHub | Internal Forgejo remote must never be pushed directly to the GitHub remote |
| Excluded governance docs remain excluded | GL-177/178/179/180 governance docs remain excluded from every publish |
| No automated GitHub API changes without explicit approval | Labels, issues, and repository settings must not be modified by automated scripts |
| No reviewer outreach without explicit approval | Direct email/message to reviewers requires explicit session approval |

---

## Security-Sensitive Reporting Routing Rules

Security-sensitive reports must be routed as follows:

1. **Primary channel:** GitHub Security Advisories at
   `https://github.com/Discodone/grantlayer/security/advisories`.
2. **Fallback:** Open a minimal public issue requesting a private reporting
   path — do not include exploit details, secrets, or sensitive reproduction
   steps in the public issue.
3. **Never:** Post exploit details, credentials, or sensitive reproduction
   steps in public issues, comments, or pull requests.
4. **Agent behavior:** AI coding agents must not include exploit details in
   final reports or documentation, even for demonstration purposes.

---

## Public Snapshot Safety Assessment

### Dimension Assessment Table

| Dimension | Status | Severity | Rationale | Recommended Follow-up |
|-----------|--------|----------|-----------|----------------------|
| Private-data safety | pass | — | No real customer names, addresses, identifiers, or PII found in reviewed files. All examples use synthetic identifiers. | — |
| Secret safety | pass | — | No real API keys, tokens, passwords, or private keys found. All tokens are placeholders (e.g. `demo-admin-token-gl146`). | — |
| Internal infrastructure leakage | pass | — | No internal hostnames, Forgejo URLs, internal VM IPs, or internal absolute paths found in public-facing entry docs. | — |
| Claim consistency | pass | — | All four entry-point docs (README.md, AGENTS.md, llms.txt, SECURITY.md) contain all required caveats. No prohibited claims found. | — |
| Stale phrase absence | pass | — | No stale public-state phrases found in public entry docs. Historical governance docs containing stale phrases are excluded from the public snapshot (GL-181). | — |
| Scanner false-positive handling | pass_with_cautions | low | Pre-existing scope-guard FPs in the full test suite are documented. This gate doc itself contains scanner-pattern-definitions FPs. Both are expected and non-blocking. | Document per-FP class; monitor for new FP classes. |
| Security-advisory routing | pass | — | SECURITY.md section 2 routes security-sensitive reports to GitHub Security Advisories. GL-192 templates include explicit advisory routing. | — |
| Public push safety | pass | — | GL-194 public publish used the clean snapshot workflow (no force push, no direct internal push to GitHub, no visibility change). | — |
| Public example determinism | pass | — | `scripts/verify-first-output.sh` → MATCH. `diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl195_grant_lifecycle_check.json` → empty diff. | — |
| Developer preview caveats | pass | — | "Developer Preview", "not production SaaS", "tenant isolation not implemented" appear in README.md, AGENTS.md, llms.txt, SECURITY.md, all issue templates. | — |
| Production readiness caveats | pass | — | "Not claimed" / "not provided" for production SaaS in all entry docs. No production-ready claim present. | GL-199 will consolidate the gap report. |
| Tenant isolation caveats | pass | — | "Not implemented" for tenant isolation in all entry docs. | GL-199 will consolidate the isolation gap analysis. |

---

## Findings

### GL-195-F001

| Field | Value |
|-------|-------|
| id | GL-195-F001 |
| severity | low |
| category | scanner-false-positive |
| summary | This gate document itself contains scanner-pattern-definition text (prohibited phrase lists) that will trigger keyword scanner heuristics. |
| evidence | This document's "Scanner Blocker Categories" and "Stale Public-State Phrase Rules" sections contain the exact phrases that scanner heuristics search for (e.g., "raw secret material", "publication pending"). |
| blocking | no |
| false_positive_class | scanner-pattern-definitions |
| recommended_action | Mark as expected FP. Any scanner tool that processes this file should treat it as a meta-document and exclude it from blocker evaluation. |
| recommended_issue | No new issue required — document in scanner log and test suite. |

### GL-195-F002

| Field | Value |
|-------|-------|
| id | GL-195-F002 |
| severity | low |
| category | scanner-false-positive |
| summary | Pre-existing scope-guard test failures in the full test suite occur because older GL scope-guard tests did not anticipate newer GL issue files (GL-186 scope-guard tests failing when GL-195 files appear). |
| evidence | Full suite historically shows 9–21 pre-existing scope-guard false-positive failures. These are documented in GL-162D, GL-181, GL-186, GL-191, GL-192, GL-193, GL-194 histories. |
| blocking | no |
| false_positive_class | historical-scope-guard-tests |
| recommended_action | Accept as pre-existing known FPs. Record in final report. Do not attempt to fix by modifying historic test files. |
| recommended_issue | GL-199 or a dedicated housekeeping issue can revisit if FP count grows significantly. |

### GL-195-F003

| Field | Value |
|-------|-------|
| id | GL-195-F003 |
| severity | low |
| category | documentation-feedback |
| summary | llms.txt "Next Steps" still references "GL-193 (public agent/API walkthrough refresh)" as an upcoming issue, but GL-193 is complete (GL-194-F001). |
| evidence | `llms.txt` line 79: "Upcoming issues: GL-193 (public agent/API walkthrough refresh)." GL-193 was merged and published. |
| blocking | no |
| false_positive_class | — |
| recommended_action | Update llms.txt "Next Steps" to reference GL-195–GL-199 roadmap items in a subsequent issue. |
| recommended_issue | GL-196 or GL-197 can include this one-line cross-link update. |

### GL-195-F004

| Field | Value |
|-------|-------|
| id | GL-195-F004 |
| severity | info |
| category | product-question |
| summary | No formal production readiness gap report v2 exists (identified in GL-194-F002). This is non-blocking for developer preview. |
| evidence | README and SECURITY.md list individual caveats; no single consolidated production gap report v2 exists. GL-194 confirmed this is a known gap. |
| blocking | no |
| false_positive_class | — |
| recommended_action | GL-199 Production Readiness Gap Report v2 should document all remaining hardening gates. |
| recommended_issue | GL-199 |

### GL-195-F005

| Field | Value |
|-------|-------|
| id | GL-195-F005 |
| severity | info |
| category | product-question |
| summary | No formal tenant isolation gap analysis exists documenting what isolation work remains and in what order (identified in GL-194-F003). Non-blocking. |
| evidence | All four entry-point docs state "tenant isolation is not implemented." No doc maps the isolation implementation path. |
| blocking | no |
| false_positive_class | — |
| recommended_action | Include tenant isolation gap analysis in GL-199 Production Readiness Gap Report v2. |
| recommended_issue | GL-199 |

---

## Decision

**public_safety_gate_passed_with_cautions**

---

## Decision Rationale

No blocker findings were identified:
- No private data, secrets, or internal infrastructure found in the public snapshot.
- No prohibited public claims found in any entry-point doc.
- No stale public-state phrases found in public entry docs.
- No force-push requirement or direct internal push to GitHub.
- Security-sensitive reporting routed correctly to GitHub Security Advisories.
- Both public examples produce exact matches with committed reference artifacts.

Cautions:
- Pre-existing scope-guard FP count is known and documented (GL-195-F002).
- This gate document itself triggers scanner-pattern-definition FPs (GL-195-F001).
- llms.txt "Next Steps" references a completed issue (GL-195-F003, low severity).
- Production readiness gap report v2 and tenant isolation gap analysis remain as
  planned follow-up items (GL-199).

The public developer preview may continue without blocking changes.

---

## Recommended Next Issues

| Issue | Title | Priority | Rationale |
|-------|-------|----------|-----------|
| GL-195P | GL-195 Combined Merge-and-Publish | high | Merge GL-195 to main and publish public snapshot update. |
| GL-196 | Public Safety Gate Activation | medium | Operationalise this gate as a repeatable checkpoint in the publish workflow. |
| GL-197 | API/SDK/Agent Value Decision Pack | medium | Document SDK maturity, packaging decision, and agent integration value proposition. |
| GL-198 | Controlled Preview Boundary Pack | medium | Draft reviewer invite criteria, data policy summary, and onboarding/offboarding. |
| GL-199 | Production Readiness Gap Report v2 | medium | Consolidated production-vs-preview gap analysis, tenant isolation path, and remaining hardening gates. |

---

## Non-Goals

This issue does **not**:
- implement backend features or change production runtime behavior
- change the database schema, migrations, or OpenAPI contract
- change dependency manifests (requirements.txt, requirements-dev.txt)
- change SDK implementation or examples runtime behavior
- change frontend, website, or design files
- change GitHub workflow files or the snapshot publish script
- change git remotes
- push to GitHub or change GitHub visibility
- use force push
- create or modify GitHub labels via API
- create or modify GitHub issues via API
- send reviewer outreach
- claim production SaaS readiness
- claim tenant isolation is implemented
- request real customer data, private grants, or secrets
- include exploit details

---

## Safety Confirmations

| Confirmation | Status |
|-------------|--------|
| no_github_push_performed | confirmed |
| no_visibility_change_performed | confirmed |
| internal_repo_not_pushed_directly_to_github | confirmed |
| no_github_api_label_changes_performed | confirmed |
| no_github_issue_changes_performed | confirmed |
| no_reviewer_outreach_sent | confirmed |
| no_backend_src_changes | confirmed |
| no_openapi_changes | confirmed |
| no_migration_db_dependency_changes | confirmed |
| no_dependency_manifest_changes | confirmed |
| no_sdk_implementation_changes | confirmed |
| no_examples_runtime_changes | confirmed |
| no_frontend_website_design_changes | confirmed |
| no_github_workflow_changes | confirmed |
| no_snapshot_publish_script_behavior_changes | confirmed |
| no_production_saas_claim | confirmed |
| tenant_isolation_not_claimed | confirmed |
| no_real_customer_data_requested | confirmed |
| no_private_grant_data_requested | confirmed |
| no_secrets_requested | confirmed |
| no_exploit_details_included | confirmed |
| security_sensitive_reports_routed_to_github_security_advisories | confirmed |

---

> This document was created in **GL-195 Public Safety / Scanner / Claim Consistency Gate**. It is a review/docs/test artifact only. It does not change git remotes, rewrite history, modify production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, launch a website or frontend, claim production SaaS readiness, or claim tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
