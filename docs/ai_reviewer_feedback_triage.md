# GL-186: AI Reviewer Feedback Triage

**Issue ID:** GL-186  
**Title:** AI Reviewer Feedback Triage  
**Branch:** gl-186-ai-reviewer-feedback-triage  
**Base commit:** f5a7fd8e47fbb80dfb1dc6a47da148a59665a7f3 (Merge GL-185)  
**Date:** 2026-06-02  
**Scope:** docs/test/artifact only — no backend, no API, no DB, no runtime changes

---

## Context

GrantLayer is public on GitHub at https://github.com/Discodone/grantlayer.git in a
Developer Preview / Controlled Pilot posture following GL-176 through GL-185. GL-185
opened the first reviewer feedback window and defined the feedback capture model. No
real human reviewer outreach has been sent yet.

Instead, the user gathered three AI-simulated external reviewer reports:
1. Codex Backend/DX Review
2. Kimi K2.6 Agent/OSS Review
3. Security/Product-Readiness Review (uploaded external review PDF)

GL-186 triages these three reports, normalizes findings into the GL-183 category/severity
model, identifies repeated themes across reviewers, separates blockers from non-blocking
polish, and recommends the next concrete GL issues.

---

## Scope

**Allowed files in this issue:**
- `docs/ai_reviewer_feedback_triage.md` (this document)
- `docs/examples/gl186/ai_reviewer_feedback_triage.json`
- `backend/tests/test_gl186_ai_reviewer_feedback_triage.py`

**Explicitly out of scope:** backend/src/\*, OpenAPI, migrations, DB/schema, dependencies,
SDK implementation, frontend/website/design, GitHub workflow changes, snapshot publish
script, git remotes, public GitHub push, visibility changes, automated GitHub API
calls, reviewer outreach.

---

## Input Reviews Summary

### Reviewer 1 — Codex Backend/DX Review

| Field | Value |
|---|---|
| reviewer_id | codex-backend-dx |
| persona | External backend developer |
| review_type | Backend developer experience / documentation |
| base_commit_reviewed | f5a7fd8e (public mirror) |

**Positive signals:**
- GrantLayer is understandable as a local-first verification/audit/compliance layer for
  agentic grant workflows.
- First verifiable output is discoverable, reproducible, and ran successfully, matching
  the committed reference JSON.
- Safety caveats are explicit and appropriately bounded.

**Major concerns:**
- README "no installation required" language conflicts with backend quickstart venv/requirements
  setup (GL-REV-01, medium).
- Port inconsistency between backend quickstart (8765) and integration example (8000)
  (GL-REV-02, low).
- "Source of truth | Internal Forgejo" wording is confusing in a public repo (GL-REV-03, low).

**Recommended next improvements:**
- Split README into explicit paths: "First verifiable output" vs "Backend quickstart".
- Standardize port references or add an explanatory note.
- Replace Forgejo wording with public-oriented language.

---

### Reviewer 2 — Kimi K2.6 Agent/OSS Review

| Field | Value |
|---|---|
| reviewer_id | kimi-k2-agent-oss |
| persona | AI-agent workflow developer and first-time open-source reviewer |
| review_type | Agent/OSS developer experience |
| base_commit_reviewed | f5a7fd8e (public mirror) |

**Positive signals:**
- README is clear enough to understand GrantLayer quickly.
- AGENTS.md, llms.txt, and llms-full.txt are unusually strong and useful for agent onboarding.
- First verifiable output is easy to locate and runs deterministically.
- Safety/caveats are clear.

**Major concerns:**
- ten_minute_quickstart.md still uses placeholder/future public GitHub clone language
  (GL-REV-KIMI-01, medium).
- agent_quickstart.md says "approved internal source" for cloning, misleading in a
  public repo (GL-REV-KIMI-02, medium).
- AGENTS.md and llms-full.txt contain stale "Public GitHub release not performed" /
  "formal visibility decision pending" language (GL-REV-KIMI-03, low).
- llms-full.txt "Next Planned Issues" table is stale (GL-REV-KIMI-04, low).
- README clone command and cd path are slightly inconsistent (GL-REV-KIMI-05, low).

**Recommended next improvements:**
- Update clone commands in quickstart docs to actual public URL.
- Update agent-facing state in AGENTS.md and llms-full.txt.
- Add a verify-first-output helper script.
- Clarify SDK/API status: local import only vs published package.

---

### Reviewer 3 — Security/Product-Readiness Review

| Field | Value |
|---|---|
| reviewer_id | security-product-readiness |
| persona | Security-oriented senior technical reviewer with product-readiness awareness |
| review_type | Security and product readiness |
| source | Uploaded external review PDF: grantlayer_external_review_2026-06-02.md |

**Positive signals:**
- GrantLayer is a clearly bounded Developer Preview / Controlled Pilot.
- First verifiable output is cryptographically reproducible and matches committed
  reference output exactly.
- Safety caveats are honest and repeated throughout.
- No broken links among checked files.
- docs/security_boundaries.md praised explicitly.
- No real secrets or customer data found in the review.

**Major concerns:**
- README test count claim ("1130 tests, 3 skipped, 0 failures") is immediately
  falsifiable — actual runs show thousands of tests and some known failures (F-001, high).
- CONTRIBUTING.md says public GitHub release not performed / requires approval, but
  the repository is already public (F-002, high).
- README "Suggested repository metadata" speaks hypothetically about public publication
  approval (F-003, medium).
- GL-155 described as both planned and completed/added in different places (F-004, medium).
- ENABLE_DEMO_ENDPOINTS=true combined with non-localhost host may expose unauthenticated
  tamper endpoint — kept high-level only (F-005, medium, security-concern).
- sourceOfTruth: internal-forgejo in public JSON files confuses external reviewers
  (F-006, low).

**Recommended next improvements:**
- Update or remove stale test count claim in README.
- Update CONTRIBUTING.md to reflect actual public state.
- Remove hypothetical framing from README metadata section.
- Resolve GL-155 contradiction.
- Add startup warning / guard for demo endpoint — route to later hardening issue.
- Exclude or explain internal-forgejo wording in public files.

---

## Normalized Findings

| ID | Source Reviews | Severity | Category | Summary | Blocking | Proposed Follow-Up |
|---|---|---|---|---|---|---|
| NF-001 | F-001 (sec) | high | stale-claim / broken-quickstart | README test count is stale and immediately falsifiable. Claimed "1130 tests, 3 skipped, 0 failures"; actual suites show thousands of tests and known failures. Harms trust at first impression. | yes | GL-187 |
| NF-002 | F-002 (sec) | high | stale-claim / confusing-docs | CONTRIBUTING.md still states public GitHub release not performed / requires approval. Repository is already public. | yes | GL-187 |
| NF-003 | GL-REV-KIMI-01 (kimi), GL-REV-01 (codex) | medium | confusing-docs / broken-quickstart | Clone instructions in ten_minute_quickstart.md and README use inconsistent or hypothetical public GitHub language instead of actual public URL. | yes | GL-187 |
| NF-004 | GL-REV-KIMI-02 (kimi) | medium | confusing-docs | agent_quickstart.md refers to "approved internal source" for cloning, misleading in a public repository context. | yes | GL-187 |
| NF-005 | GL-REV-KIMI-03 (kimi), GL-REV-KIMI-04 (kimi) | low | confusing-docs | AGENTS.md and llms-full.txt contain stale "Public GitHub release not performed" / "formal visibility decision pending" language and a stale Next Planned Issues table. | no | GL-187 |
| NF-006 | F-003 (sec) | medium | confusing-docs | README "Suggested repository metadata" section still speaks hypothetically about public publication approval. | no | GL-187 |
| NF-007 | F-004 (sec) | medium | confusing-docs | GL-155 is described as planned in one place and completed/added elsewhere. Contradiction in docs. | no | GL-187 |
| NF-008 | GL-REV-03 (codex), F-006 (sec) | low | confusing-docs | "Source of truth: internal-forgejo" / sourceOfTruth: internal-forgejo appears in public-facing docs and JSON files, confusing external reviewers unfamiliar with the internal mirror setup. | no | GL-187 |
| NF-009 | GL-REV-02 (codex) | low | confusing-docs | Port inconsistency: backend quickstart references 8765, integration example uses 8000. | no | GL-187 |
| NF-010 | GL-REV-KIMI-05 (kimi) | low | confusing-docs | README clone command and resulting cd directory path are slightly inconsistent. | no | GL-187 |
| NF-011 | GL-REV-KIMI-06 (kimi) | info | feature-request | Add a small verify-first-output helper script so developers can run and compare output in one step. | no | GL-188 |
| NF-012 | GL-REV-04 (codex) | info | missing-example | Add a second runnable example: create a grant, query audit trail, export verifiable evidence bundle. | no | GL-189 |
| NF-013 | F-005 (sec) | medium | security-concern | ENABLE_DEMO_ENDPOINTS=true combined with a non-localhost host binding may expose unauthenticated tamper endpoint. Kept high-level. Details routed to GitHub Security Advisories / separate hardening issue. | no | GL-190 |
| NF-014 | GL-REV-05 (codex) | info | confusing-docs | README lacks a clear "choose your path" section to guide developers to the right starting point. | no | GL-187 |
| NF-015 | GL-REV-KIMI-07 (kimi) | info | product-question | SDK/API status is not explicit: local import only vs future published package. Clarification needed. | no | GL-187 |

---

## Repeated Themes

### Theme 1 — Stale public-state docs (3/3 reviewers flagged)
All three reviewers independently identified that various docs still reflect a
pre-publication internal state. Affected files include README.md, CONTRIBUTING.md,
AGENTS.md, llms-full.txt, ten_minute_quickstart.md, and agent_quickstart.md.
This is the highest-priority theme because it damages trust at first impression.

### Theme 2 — First verifiable output works well (3/3 reviewers confirmed)
All three reviewers confirmed the first verifiable output ran successfully,
deterministically, and matched the committed reference JSON. This is a strong
positive signal and a meaningful trust anchor for the developer preview.

### Theme 3 — Quickstart / clone-path inconsistency (2/3 reviewers flagged)
Both Codex and Kimi flagged inconsistent or hypothetical clone commands and
directory names in quickstart docs. Minor but immediately visible on first use.

### Theme 4 — Agent docs strong but stale in places (1/3 reviewers flagged explicitly)
Kimi flagged that AGENTS.md, llms.txt, and llms-full.txt are unusually strong for
agent onboarding, but contain stale public-state language. The security reviewer
implicitly confirmed by noting no broken links — the structure is sound, the
content just needs public-state updates.

### Theme 5 — Test count / status claims need cleanup (1/3 reviewers flagged)
The security reviewer flagged the stale test count in README as immediately
falsifiable and trust-damaging. This is distinct from the general stale-docs
theme because it is a specific verifiable claim.

### Theme 6 — Verify-first-output helper script requested (1/3 reviewers)
Kimi requested a small helper script or test to verify the first output in one
step. Lower priority but a meaningful DX improvement.

### Theme 7 — Second runnable example needed (1/3 reviewers)
Codex requested a second example covering grant creation, audit trail query, and
verifiable evidence export. This is a feature-level addition for a future issue.

### Theme 8 — Demo endpoint safety hardening warrants separate issue (1/3 reviewers)
The security reviewer flagged a configuration-level risk around the demo tamper
endpoint. This should be a separate higher-care issue (GL-190), not bundled with
docs cleanup.

---

## Security-Sensitive Handling Note (NF-013 / F-005)

Finding NF-013 relates to a configuration-level risk: ENABLE_DEMO_ENDPOINTS=true
combined with a non-localhost host binding may expose an unauthenticated endpoint.

This document keeps the concern at the description level only. No exploit details,
no proof-of-concept, no specific attack paths are included.

The recommended action is to create GL-190 as a separate, higher-care backend
hardening issue. Security-sensitive details should be submitted via GitHub Security
Advisories (see SECURITY.md) rather than in public issues.

This triage document does not implement any security changes. GL-190 is a planning
artifact only.

---

## Priority Follow-Up Plan

### GL-187 — Public Docs Post-Public Stale Claim Cleanup (immediate next)
- **Priority:** 1 — Blocker for trust
- **Severity trigger:** NF-001 (high), NF-002 (high), NF-003 (medium), NF-004 (medium)
- **Recommended model:** Claude Code (Sonnet)
- **Scope:** README.md, CONTRIBUTING.md, AGENTS.md, llms-full.txt,
  ten_minute_quickstart.md, agent_quickstart.md, possibly public metadata JSON files.
- **Expected outcomes:**
  - Remove or update stale test count claim.
  - Update CONTRIBUTING.md to reflect actual public state.
  - Update clone commands to real public URL.
  - Update agent-facing state in AGENTS.md and llms-full.txt.
  - Remove hypothetical framing from README metadata section.
  - Resolve GL-155 contradiction.
  - Align README clone command with cd directory name.
  - Optionally address port inconsistency and Forgejo wording.
- **Non-goals:** No backend changes. No new features. No OpenAPI. No migrations.

### GL-188 — First Output Verify Helper Script
- **Priority:** 2 — DX improvement
- **Severity trigger:** NF-011 (info, feature-request)
- **Recommended model:** Claude Code (Sonnet)
- **Scope:** Small script or test helper in scripts/ or examples/ that runs the
  first verifiable output example and compares against committed reference JSON.
- **Non-goals:** No backend changes. No new API surface.

### GL-189 — Second Runnable Example / Grant Lifecycle Evidence Bundle
- **Priority:** 3 — New example
- **Severity trigger:** NF-012 (info, missing-example)
- **Recommended model:** Claude Code (Sonnet)
- **Scope:** New public example showing grant creation, audit trail query, and
  verifiable evidence export. Docs/examples only, no backend/src changes.
- **Non-goals:** No backend implementation changes. No new API routes.

### GL-190 — Demo Endpoint Safety Guard / Startup Warning
- **Priority:** 4 — Security hardening, separate higher-care issue
- **Severity trigger:** NF-013 (medium, security-concern)
- **Recommended model:** Claude Code (Sonnet or Opus for security judgment)
- **Scope:** Backend startup validation or warning when ENABLE_DEMO_ENDPOINTS=true
  and host is not localhost. Docs update to SECURITY.md or security_boundaries.md.
- **Important:** This involves backend/src changes and requires higher review care.
  Do not bundle with GL-187 docs cleanup.
- **Non-goals:** No exploit details in public artifacts. Security-sensitive details
  via GitHub Security Advisories.

---

## Immediate Next Issue Recommendation

**GL-187 — Public Docs Post-Public Stale Claim Cleanup**

**Rationale:** Three independent reviewers flagged stale public-state docs, broken
clone instructions, and trust-damaging test-count claims. NF-001 and NF-002 are
both high-severity and are immediately falsifiable by any external developer who
runs the test suite or reads CONTRIBUTING.md. These are more urgent than adding new
features or helper scripts because they undermine the basic trust signal that the
developer preview is meant to build.

**Recommended model:** Claude Code (Sonnet)

**Expected scope:** README.md, CONTRIBUTING.md, AGENTS.md, llms-full.txt,
ten_minute_quickstart.md, agent_quickstart.md. Possibly public metadata JSON files
containing sourceOfTruth: internal-forgejo. No backend/src changes. No API changes.

**Explicit non-goals for GL-187:**
- No backend/src changes
- No OpenAPI changes
- No migration or DB/schema changes
- No dependency changes
- No new examples (that is GL-188 and GL-189)
- No security hardening (that is GL-190)
- No GitHub push during this issue
- No visibility changes

---

## Non-Goals

This issue (GL-186) does not:
- Implement any of the recommended fixes
- Push to GitHub
- Change GitHub visibility
- Create GitHub issues or labels via API
- Send reviewer outreach
- Include any reviewer private data
- Include any secrets or tokens
- Include any exploit details
- Claim production SaaS readiness
- Assert multi-tenant or workspace isolation as a completed feature
- Change backend behavior
- Change API contracts
- Modify migrations or DB schema
- Modify dependencies
- Modify SDK implementation
- Modify frontend or website

---

## Safety Confirmations

| Confirmation | Status |
|---|---|
| No GitHub push performed | confirmed |
| No visibility change performed | confirmed |
| Internal repo was not pushed directly to GitHub | confirmed |
| No outreach sent | confirmed |
| No reviewer private data included | confirmed |
| No secrets or tokens included | confirmed |
| No exploit details included | confirmed |
| Security-sensitive concern (NF-013/F-005) kept high-level | confirmed |
| Security-sensitive details directed to GitHub Security Advisories or later hardening issue | confirmed |
| Production SaaS readiness not claimed | confirmed |
| Multi-tenant or workspace isolation not asserted as complete | confirmed |
| No GitHub API label changes performed | confirmed |
| No GitHub issue changes performed | confirmed |
| No backend/src changes | confirmed |
| No OpenAPI changes | confirmed |
| No migration or DB/schema changes | confirmed |
| No dependency manifest changes | confirmed |
| No SDK implementation changes | confirmed |
| No frontend/website/design changes | confirmed |
| No GitHub workflow changes | confirmed |
| No snapshot publish script behavior changes | confirmed |
| No git remote changes | confirmed |

**Explicit statements:**
- No GitHub push was performed in this issue.
- No GitHub visibility change was performed in this issue.
- The internal repository was not pushed directly to GitHub in this issue.
- No reviewer outreach was sent in this issue.
- No reviewer private data (email, phone, internal hostname) is included in this issue.
- No GitHub API label or issue changes were performed in this issue.

---

## Changed Files

- `docs/ai_reviewer_feedback_triage.md` (this document)
- `docs/examples/gl186/ai_reviewer_feedback_triage.json`
- `backend/tests/test_gl186_ai_reviewer_feedback_triage.py`
