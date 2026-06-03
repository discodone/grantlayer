# GL-194 Public Preview Review & Feedback Triage Pack

## Issue ID

GL-194

## Title

Public Preview Review & Feedback Triage Pack

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture (GL-176).

The sequence GL-187 through GL-193 delivered: stale public docs cleanup, a
first-output verify helper, a grant lifecycle evidence bundle, a demo endpoint
safety guard, a developer experience polish pack, a public feedback
infrastructure, and a public agent/API walkthrough refresh.

GL-194 synthesises the current public preview state, triages accumulated
feedback themes from AI reviewers and prior review cycles, assesses public
preview readiness across sixteen dimensions, and converts that analysis into a
prioritised roadmap for issues GL-195 through GL-199.

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

## Completed Public Preview Improvements Summary

| Issue | Title | Status |
|-------|-------|--------|
| GL-187 | Public Docs Stale Claim Cleanup | merged_done |
| GL-187P | Public Snapshot Correction Push | merged_done |
| GL-188 | First Output Verify Helper | merged_done |
| GL-188P | Public Snapshot Correction Push | merged_done |
| GL-189 | Second Runnable Evidence Bundle | merged_done |
| GL-189P | Public Snapshot Push | merged_done |
| GL-190 | Demo Endpoint Safety Guard | merged_done |
| GL-191 | Public Developer Experience Polish Pack | merged_and_published |
| GL-192 | Public Feedback Infrastructure Pack | merged_and_published |
| GL-193 | Public Agent/API Walkthrough Refresh | merged_and_published |

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| README.md | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes (partial — header and map) |
| docs/first_output_verify_helper.md | yes |
| docs/grant_lifecycle_evidence_bundle.md | yes |
| docs/public_developer_experience_polish_pack.md | yes |
| docs/public_feedback_infrastructure_pack.md | yes |
| docs/public_agent_api_walkthrough_refresh.md | yes |
| docs/examples/gl191/public_developer_experience_polish_pack.json | referenced |
| docs/examples/gl192/public_feedback_infrastructure_pack.json | referenced |
| docs/examples/gl193/public_agent_api_walkthrough_refresh.json | yes |
| examples/first_verifiable_output.py | smoke-tested |
| examples/first_verifiable_output.json | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.py | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.json | smoke-tested |
| scripts/verify-first-output.sh | smoke-tested |
| SECURITY.md | yes |

---

## AI/Reviewer Feedback Themes

The following themes emerged from prior AI reviewer inputs (GL-186 triage) and
observation of the public preview state after GL-187–GL-193:

1. **Entry-point clarity** — Earlier reviewers noted that the README did not
   clearly sequence "what to run first" vs "what to run next." GL-191 resolved
   this with explicit "What to try first / next" sections.

2. **Stale public-state claims** — GL-187 cleaned phrases such as "coming
   soon" or "will be published" that had persisted from pre-public cycles.

3. **First deterministic output trust** — Reviewers found value in a runnable
   example that produces verifiable output with no install. GL-188 added the
   verify helper script.

4. **Second example gap** — Reviewers requested a second runnable example to
   show more product concepts beyond the initial record shape. GL-189 delivered
   the grant lifecycle evidence bundle.

5. **Agent/coding-agent path** — AI coding agents needed one clear sequence
   (README → AGENTS.md → llms.txt → walkthrough). GL-193 refreshed this path.

6. **Feedback routing and security advisory path** — Earlier docs did not
   explicitly route security-sensitive findings away from public issues.
   GL-192 formalised this with category templates and advisory routing.

7. **Caveat consistency** — Multiple reviewers noted that "Developer Preview",
   "not production SaaS", and "tenant isolation not implemented" needed to be
   explicit everywhere a developer might enter. These phrases now appear in
   README, AGENTS.md, llms.txt, SECURITY.md, and every public template.

8. **Backend/no-install separation** — The quickstart previously blended the
   no-install examples with the backend setup steps. GL-191 separated these
   into Path A / Path A2 / Path B with explicit notes.

9. **Production readiness gap report** — No formal production-vs-preview gap
   report exists yet. This is non-blocking for developer preview but should be
   documented in GL-199.

10. **API/SDK packaging decision** — The minimal Python SDK exists but no
    formal packaging or maturity decision has been documented. GL-197 tracks this.

---

## Feedback Triage Categories

| Category | Description |
|----------|-------------|
| `quickstart-feedback` | Friction, confusion, or errors when following README / agent_quickstart.md |
| `first-output-feedback` | Issues with scripts/verify-first-output.sh or docs/first_output_verify_helper.md |
| `grant-lifecycle-example-feedback` | Issues with examples/grant_lifecycle_evidence_bundle.py or docs/grant_lifecycle_evidence_bundle.md |
| `documentation-feedback` | Unclear, missing, or inconsistent docs |
| `developer-experience-feedback` | General DX pain: setup, error messages, tooling, agent workflow |
| `bug-report` | Reproducible software bug using synthetic/demo data |
| `feature-request` | Scoped improvement suggestion for Developer Preview stage |
| `product-question` | Questions about roadmap, architecture, tenant model, production posture |
| `security-sensitive-report` | Vulnerability, auth bypass, secret exposure — GitHub Security Advisories only |
| `non-scope-later` | Production SaaS deployment, real multi-tenant isolation, customer data handling |

---

## Severity Model

| Level | Meaning |
|-------|---------|
| `critical` | Production-blocking security issue (auth bypass, secret leak, data exposure). Route to GitHub Security Advisories immediately. |
| `high` | Significant correctness failure, misleading public safety statement, or security-adjacent concern not yet critical. |
| `medium` | Reproducible bug that degrades a documented workflow; confusing or incorrect documentation that could mislead developers. |
| `low` | Minor friction, cosmetic issues, non-blocking doc gaps. |
| `info` | General feedback, questions, observations with no actionable bug. |

---

## Public Preview Readiness Assessment

### Dimension Table

| Dimension | Status | Severity | Rationale | Follow-up |
|-----------|--------|----------|-----------|-----------|
| README clarity | ready | — | "What to try first / next", developer entry path, and path table all present (GL-191). Caveats explicit. | — |
| First output helper | ready | — | `scripts/verify-first-output.sh` verified: MATCH (GL-194 smoke check). | — |
| Second runnable example | ready | — | `grant_lifecycle_evidence_bundle.py` verified: empty diff (GL-194 smoke check). | — |
| Public feedback infrastructure | ready | — | Templates, severity model, security advisory routing, label taxonomy plan all in place (GL-192). | — |
| Agent/API walkthrough | ready | — | `docs/public_agent_api_walkthrough_refresh.md` covers all entry points, paths, and caveats (GL-193). | — |
| Security-sensitive routing | ready | — | SECURITY.md and GL-192 both route security-sensitive reports to GitHub Security Advisories. Explicit in every template. | — |
| Caveat clarity | ready | — | "Developer Preview", "not production SaaS", "tenant isolation not implemented" appear in README, AGENTS.md, llms.txt, SECURITY.md, all issue templates. | — |
| Public claim safety | ready_with_cautions | low | All active public claims appear accurate. A scanner/claim consistency gate (GL-195) would add confidence. | GL-195 |
| Example determinism | ready | — | Both examples produce exact match with committed reference artifacts (GL-194 smoke check). | — |
| Backend quickstart separation | ready | — | Path A (no-install), Path A2 (no-install), Path B (requires pip install) clearly separated (GL-191). | — |
| Coding agent readiness | ready | — | AGENTS.md, llms.txt, llms-full.txt, agent_quickstart.md, agent_task_contract.md all present and current (GL-193). | — |
| Public snapshot safety | ready | — | No private paths, secrets, internal hostnames, or private remotes found during review. | — |
| Production readiness | needs_followup | medium | Production readiness is explicitly not claimed. No formal production-vs-preview gap report v2 yet written. | GL-199 |
| Tenant isolation | needs_followup | medium | Tenant isolation is explicitly not implemented and prominently documented. No formal isolation gap report yet written. | GL-199 |
| API/SDK maturity | needs_followup | low | Minimal Python SDK exists; no formal packaging maturity decision or public release process documented. | GL-197 |
| Controlled preview readiness | needs_followup | low | No formal controlled-preview boundary document (invite criteria, onboarding, offboarding, data policy). | GL-198 |

---

## Findings

### GL-194-F001

| Field | Value |
|-------|-------|
| id | GL-194-F001 |
| severity | low |
| category | documentation-feedback |
| summary | llms.txt mentions "Upcoming issues: GL-193" as a future step, but GL-193 is now complete. |
| evidence | llms.txt line 79: "Upcoming issues: GL-193 (public agent/API walkthrough refresh)." GL-193 merged and published (GL-193 memory). |
| blocking | no |
| recommended_action | Update llms.txt "Next Steps" to reference GL-194 and the compact roadmap (GL-195–GL-199) instead of GL-193. |
| recommended_issue | GL-195 or GL-197 can include this as a one-line cross-link update. |

### GL-194-F002

| Field | Value |
|-------|-------|
| id | GL-194-F002 |
| severity | medium |
| category | product-question |
| summary | No formal production readiness gap report v2 exists documenting exactly what must be completed before production deployment. |
| evidence | README "Current status" table and SECURITY.md "Current Caveats" list individual caveats but no single consolidated gap report v2. |
| blocking | no — developer preview is explicitly not production; the caveat is documented |
| recommended_action | Create GL-199 Production Readiness Gap Report v2 as a standalone doc listing all remaining hardening gates with severity and owner. |
| recommended_issue | GL-199 |

### GL-194-F003

| Field | Value |
|-------|-------|
| id | GL-194-F003 |
| severity | medium |
| category | product-question |
| summary | Tenant isolation is prominently caveated but no formal isolation gap report exists describing what isolation work remains and in what order. |
| evidence | README, AGENTS.md, llms.txt, SECURITY.md all state "tenant isolation is not implemented." No doc maps the isolation implementation path. |
| blocking | no — the caveat is explicit and consistent |
| recommended_action | Include tenant isolation gap analysis in GL-199 Production Readiness Gap Report v2. |
| recommended_issue | GL-199 |

### GL-194-F004

| Field | Value |
|-------|-------|
| id | GL-194-F004 |
| severity | low |
| category | developer-experience-feedback |
| summary | The minimal Python SDK exists but no formal API/SDK packaging maturity decision or public release process is documented. |
| evidence | `sdk/python/README.md` and `sdk/python/grantlayer_client.py` exist. No version, no release tag, no packaging manifest. |
| blocking | no |
| recommended_action | GL-197 API/SDK/Agent Value Decision Pack should document the SDK maturity state and whether a PyPI or packaged release is planned for the preview stage. |
| recommended_issue | GL-197 |

### GL-194-F005

| Field | Value |
|-------|-------|
| id | GL-194-F005 |
| severity | low |
| category | product-question |
| summary | No formal controlled-preview boundary document defines reviewer invite criteria, onboarding steps, data policy, or offboarding. |
| evidence | GL-192 round-2 reviewer guidance covers what reviewers can try and what to report. No invite policy document exists. |
| blocking | no |
| recommended_action | GL-198 Controlled Preview Boundary Pack should draft invite criteria, data policy summary, and onboarding/offboarding guidance. |
| recommended_issue | GL-198 |

### GL-194-F006

| Field | Value |
|-------|-------|
| id | GL-194-F006 |
| severity | info |
| category | first-output-feedback |
| summary | Both public runnable examples confirmed deterministic and matching committed reference artifacts as of GL-194 smoke check (2026-06-03). |
| evidence | `scripts/verify-first-output.sh` → MATCH. `diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl194_grant_lifecycle_check.json` → empty diff. |
| blocking | no |
| recommended_action | No action needed. Record as positive health indicator. Include in GL-196 Public Smoke Matrix Pack. |
| recommended_issue | GL-196 |

### GL-194-F007

| Field | Value |
|-------|-------|
| id | GL-194-F007 |
| severity | info |
| category | developer-experience-feedback |
| summary | Public scanner / claim consistency has not been formally gated. All reviewed claims appear accurate, but a formal scan for stale or unsafe claims would add confidence. |
| evidence | GL-187 cleaned a prior round of stale claims. No formal claim-scan gate has been run since GL-193. |
| blocking | no |
| recommended_action | GL-195 Public Safety / Scanner / Claim Consistency Gate should formalise and document the claim scan. |
| recommended_issue | GL-195 |

---

## Finding Counts by Severity

| Severity | Count |
|----------|-------|
| critical | 0 |
| high | 0 |
| medium | 2 |
| low | 3 |
| info | 2 |
| **Total** | **7** |

No critical or high findings. No blocker for continuing developer preview.

---

## What Is Ready

- README: clear "What to try first / next" guidance, developer entry path, and path table.
- First output verify helper: working, deterministic, smoke-tested.
- Second runnable example: working, deterministic, smoke-tested.
- Public feedback infrastructure: templates, severity model, advisory routing.
- Agent/API walkthrough: entry points, paths, caveats, backend handoff.
- Security-sensitive routing: GitHub Security Advisories documented everywhere.
- Caveat clarity: "Developer Preview", "not production SaaS", "tenant isolation not implemented" explicit across all key docs.
- Example determinism: both examples match committed reference artifacts.
- Backend quickstart separation: no-install and backend paths clearly separated.
- Coding agent readiness: AGENTS.md, llms.txt, llms-full.txt, quickstart, contract all current.
- Public snapshot safety: no private paths, secrets, or internal data found.

---

## What Remains Caveated

- Production SaaS readiness is **not claimed**. The backend has not completed all production-hardening gates.
- Tenant/workspace isolation is **not implemented**. A single namespace is used for all data.
- API/SDK packaging maturity is **undecided** — no versioned public release process exists.
- Controlled-preview boundary is **not formalised** — no invite policy, data policy, or onboarding doc.

---

## What Is Blocking Production (but NOT Blocking Developer Preview)

- No production SaaS hardening gates completed.
- No TLS, HSM/KMS, real IAM, or multi-tenant data isolation.
- No production authentication (no OAuth, JWT).
- No formal production readiness gap report v2.
- No formal tenant isolation implementation plan.

None of these block the current developer-preview / controlled-pilot posture.

---

## What Is Not Blocking Developer Preview

- llms.txt stale "Upcoming issues: GL-193" reference (GL-194-F001, low).
- Missing production readiness gap report v2 (GL-194-F002, medium, non-blocking).
- Missing tenant isolation gap report (GL-194-F003, medium, non-blocking).
- API/SDK maturity undecided (GL-194-F004, low).
- Controlled preview boundary not formalised (GL-194-F005, low).
- Claim consistency gate not yet formalised (GL-194-F007, info).

---

## Feedback-to-Roadmap Conversion

| Theme | Finding(s) | Follow-up Issue | Priority |
|-------|-----------|-----------------|----------|
| Stale claim cleanup and scanner gate | GL-194-F007 | GL-195 Public Safety / Scanner / Claim Consistency Gate | high |
| Smoke matrix and determinism coverage | GL-194-F006 | GL-196 Public Smoke Matrix Pack | high |
| API/SDK maturity decision | GL-194-F004 | GL-197 API/SDK/Agent Value Decision Pack | medium |
| Controlled preview boundary | GL-194-F005 | GL-198 Controlled Preview Boundary Pack | medium |
| Production readiness gap report v2 | GL-194-F002, GL-194-F003 | GL-199 Production Readiness Gap Report v2 | medium |

---

## Recommended Next Compact Roadmap

| Issue | Title | Blocks |
|-------|-------|--------|
| GL-195 | Public Safety / Scanner / Claim Consistency Gate | wider reviewer widening |
| GL-196 | Public Smoke Matrix Pack | wider reviewer widening |
| GL-197 | API/SDK/Agent Value Decision Pack | SDK release decision |
| GL-198 | Controlled Preview Boundary Pack | formal invite expansion |
| GL-199 | Production Readiness Gap Report v2 | production deployment |

Suggested sequencing:
1. GL-195 and GL-196 (safety and smoke coverage) first — needed before any
   further review widening.
2. GL-197 in parallel with GL-196 if capacity allows.
3. GL-198 after GL-195 confirms claim safety.
4. GL-199 as the final pre-production gate review.

---

## Decision / Disposition

**Decision:** `public_preview_continue_with_cautions`

**Rationale:**

All developer-facing entry points are working and verified. Both runnable
examples pass smoke checks. Public caveats are consistent and explicit across
README, AGENTS.md, llms.txt, SECURITY.md, and all issue templates.
Security-sensitive routing is in place. No private data, no secrets, and no
unsafe public claims were found during this review.

The remaining findings (GL-194-F001 through GL-194-F007) are all low or
info severity, non-blocking for developer preview, and are already tracked in
the GL-195 through GL-199 roadmap.

Widening the reviewer pool beyond the current controlled-pilot posture is not
yet recommended. GL-195 (claim consistency gate) and GL-196 (smoke matrix)
should complete first.

**Blocking threshold was not met.** No critical or high findings. No private
data or secret exposure. No unsafe production or tenant-isolation claim.
No broken core public examples. No misleading SaaS or isolation claim found.

---

## Safety Confirmations

| Confirmation | Status |
|---|---|
| No GitHub push performed | confirmed |
| No visibility change performed | confirmed |
| Internal repo not pushed directly to GitHub | confirmed |
| No GitHub API label changes performed | confirmed |
| No GitHub issue changes performed | confirmed |
| No reviewer outreach sent | confirmed |
| No backend/src changes | confirmed |
| No OpenAPI changes | confirmed |
| No migration or DB/dependency changes | confirmed |
| No dependency manifest changes | confirmed |
| No SDK implementation changes | confirmed |
| No examples runtime changes | confirmed |
| No frontend/website/design changes | confirmed |
| No GitHub workflow changes | confirmed |
| No snapshot publish script behavior changes | confirmed |
| No production SaaS claim | confirmed |
| Tenant isolation not claimed | confirmed |
| No real customer data requested | confirmed |
| No private grant data requested | confirmed |
| No secrets requested | confirmed |
| No exploit details included | confirmed |
| Security-sensitive reports routed to GitHub Security Advisories | confirmed |

---

## Non-Goals

- No GitHub push.
- No visibility change.
- No GitHub API label changes.
- No GitHub issue creation or modification.
- No reviewer outreach.
- No backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency manifest changes.
- No SDK implementation changes.
- No examples runtime changes.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No snapshot publish script behavior changes.
- No production SaaS claim.
- No tenant isolation claim.
- No real customer data, private grants, secrets, or exploit details.

---

## Artifact Reference

JSON artifact: [docs/examples/gl194/public_preview_review_feedback_triage_pack.json](examples/gl194/public_preview_review_feedback_triage_pack.json)

Tests: `backend/tests/test_gl194_public_preview_review_feedback_triage_pack.py`

---

## Next Recommended Issue

GL-194 Combined Merge-and-Publish for Public Preview Review & Feedback Triage Pack

Merge `gl-194-public-preview-review-feedback-triage-pack` to internal main,
then run the snapshot publish process to push this review and feedback triage
pack to the public GitHub repository.
