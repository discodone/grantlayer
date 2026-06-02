# GL-184 First External Reviewer Invite Pack

**Issue ID:** GL-184
**Title:** First External Reviewer Invite Pack

## Context

GrantLayer is publicly readable on GitHub in a developer-preview / controlled-pilot posture
following the readiness sequence below:

| Issue | Work | Result |
|-------|------|--------|
| GL-176 | Public snapshot published to GitHub | Done |
| GL-177 | Public repo smoke verification (fresh clone) | Passed with cautions |
| GL-178 | README.md and SECURITY.md post-public state correction | Done |
| GL-179 | GL-178 fixes pushed to public GitHub | Done |
| GL-180 | Public docs smoke verification (fresh clone) | Passed — no blockers |
| GL-181 | Public snapshot exclusion cleanup | Done |
| GL-182 | External Developer Feedback Intake plan | Done |
| GL-183 | External Feedback Triage / Public Issue Hygiene | Done |

The repository is publicly readable at:
`https://github.com/Discodone/grantlayer.git`

GL-183 decided `templates_deferred` — public issue templates were deferred until the first
reviewer window confirms the category and label set. The triage and severity model is ready.
This issue prepares the controlled invite package for 2–5 external reviewers.

This issue is documentation, test, and artifact only.

**No outreach was sent by this issue.**
**No GitHub push was performed by this issue.**
**No visibility change was performed by this issue.**
**The internal repo was not pushed directly to GitHub by this issue.**
**No GitHub API label or issue changes were performed by this issue.**

---

## Scope

This issue defines the first external reviewer invite pack. It does not:

- Send emails or messages to reviewers
- Contact reviewers in any channel
- Push to GitHub
- Change GitHub repository visibility
- Modify backend source code (`backend/src/*`)
- Modify API/OpenAPI, migrations, DB schema, or dependencies
- Modify SDK implementation, frontend, website, or design assets
- Change GitHub workflows or snapshot publish script behavior
- Create GitHub labels via API
- Create GitHub issues via API
- Collect real customer data
- Claim production SaaS readiness
- Claim tenant/workspace isolation is implemented
- Reference Paperclip

Allowed files in this issue:

- `docs/first_external_reviewer_invite_pack.md` (this document)
- `docs/examples/gl184/first_external_reviewer_invite_pack.json`
- `backend/tests/test_gl184_first_external_reviewer_invite_pack.py`

---

## 1. Reviewer Profiles

The first review window targets 2–5 reviewers matching one or more of the following archetypes.
Do not include real names or private contact details in this document.

### Profile 1: External Backend Developer

- Familiar with Python, REST APIs, and SQLite or PostgreSQL
- Can clone a repo, install dependencies, and run tests in approximately 10 minutes
- May or may not have a grant-domain background
- **Key questions:** Is the quickstart clear and complete? Does the API surface make sense?
  Is the first verifiable output reproducible?

### Profile 2: AI-Agent Workflow Developer

- Builds or evaluates AI-agent pipelines (LangGraph, LangChain, AutoGen, or similar)
- Interested in audit trails, verification layers, and agentic compliance patterns
- Evaluates whether an SDK like GrantLayer fits into an agentic workflow
- **Key questions:** Does the GrantLayer integration story make sense for an AI-agent pipeline?
  Is the LangGraph example legible and realistic? Is the audit structure comprehensible?

### Profile 3: Grant / Compliance or Audit-Minded Reviewer

- Works with grant management, institutional compliance, or audit processes
- Does not need to be a developer — can assess concepts rather than code
- Evaluates whether the evidence bundle and audit trail concepts map to real institutional needs
- **Key questions:** Do the concepts (evidence bundles, audit trails, policy evaluation) reflect
  real institutional workflows? Are the safety caveats about current limitations visible and
  appropriately cautious?

### Profile 4: Security-Minded Technical Reviewer

- Reviews security posture of developer-preview software
- Familiar with OWASP, API security basics, and responsible disclosure practices
- Evaluates whether the repository is clean of secrets, sensitive paths, and overclaims
- **Key questions:** Are the security caveats visible? Is the reporting channel obvious?
  Does the repository appear free of real secrets or sensitive infrastructure paths?

---

## 2. Invite Message Draft

The following message may be sent manually to individual reviewers. It must not be sent
programmatically or in bulk. No outreach is performed by this issue — this is a draft only.

---

**Subject:** GrantLayer Developer Preview — Invitation to Review

Hello,

We are inviting a small, selected group of developers and reviewers to take an early look at
GrantLayer, a technical preview project for structured grant-application verification and
AI-agent audit workflows.

**Repository:** https://github.com/Discodone/grantlayer.git

**What GrantLayer is:**
GrantLayer is a Python backend with a REST API and SDK for creating structured, verifiable
evidence bundles used in grant management and agentic compliance workflows. This is a developer
preview only.

**What GrantLayer is not (please read before starting):**
- This is **not a production SaaS** platform. Do not treat it as a production service.
- **Tenant/workspace isolation is not yet implemented.** Do not use shared or real institutional
  data.
- No customer onboarding process is available.
- No support SLA is offered for this developer preview. We cannot guarantee response times.
- This is not an invitation to a paid or commercial commitment of any kind.

**What we are asking of you:**
1. Read README.md — can you understand what GrantLayer is in 2 minutes?
2. Read SECURITY.md — can you find the security reporting channel and current-limitations
   caveats?
3. Run or inspect the first verifiable output:
   ```
   git clone https://github.com/Discodone/grantlayer.git
   cd grantlayer
   python3 examples/first_verifiable_output.py --output /tmp/gl_first_output.json
   ```
4. Compare `/tmp/gl_first_output.json` with `examples/first_verifiable_output.json`.
5. Note what is confusing, missing, or unclear.
6. Tell us whether the purpose of the project is clear in 2 minutes of reading.

**Safety rules — please read before posting any feedback:**
- Use **synthetic/demo data only**. Do not share real customer data, private grants, or
  institutional records in any public issue or discussion.
- **Do not share secrets**, credentials, API tokens, or private keys in public issues.
- **Do not post exploit details publicly.** If you find a potential security vulnerability,
  report it through **GitHub Security Advisories** (see SECURITY.md for instructions) — not
  in a public issue.
- **Do not share real customer data** or personally identifiable information in any public
  channel.

**How to share feedback:**
Open a public GitHub issue on the repository with your observations. For security-sensitive
reports, use GitHub Security Advisories instead of public issues.

We appreciate your time. This is a controlled review window. No commercial commitment, customer
onboarding, or support guarantee is implied or offered.

---

## 3. Reviewer Task List

Ask each reviewer to attempt the following tasks, recording what succeeds, fails, or causes
confusion.

1. **Read README.md** — Assess whether the project purpose is understandable within 2 minutes.
2. **Read SECURITY.md** — Confirm the security reporting channel and current-limitations caveats
   are visible and clear.
3. **Find the quickstart / first verifiable output** — Locate `examples/first_verifiable_output.py`
   and the quickstart instructions without guidance.
4. **Run or inspect `examples/first_verifiable_output.py`** — Attempt to run the first verifiable
   output example and observe whether it succeeds or fails.
5. **Compare generated output with `examples/first_verifiable_output.json`** — Determine whether
   the generated output matches the expected reference output.
6. **Note confusing setup steps** — Record any step that required guessing, searching elsewhere,
   or extra time to complete.
7. **Identify broken links or stale wording** — Flag any hyperlink that returns 404 or any
   documentation text that appears outdated or contradictory.
8. **Assess whether caveats are visible** — Evaluate whether "not production SaaS" and "tenant
   isolation not implemented" are easy to find and clearly worded.
9. **Assess whether the project purpose is understandable in 2 minutes** — Give a one-sentence
   summary of what GrantLayer does after reading only the README.

---

## 4. Feedback Questions

The following questions should guide early reviewer feedback. They may be shared with reviewers
alongside the invite message or as a lightweight survey.

### Understanding

1. What did you think GrantLayer does after reading the README?
2. Could you find the first verifiable output quickly?
3. Could you run it, or at least understand what it proves without running it?

### Clarity and Confusion

4. What felt confusing?
5. Which part of the README or documentation was hardest to follow?
6. Were any setup steps missing, unclear, or broken?

### Trust and Credibility

7. What felt trustworthy?
8. Are the non-production caveats clear? Were you able to find them without searching?
9. Are the security reporting instructions clear and easy to follow?

### Usefulness and Next Steps

10. What felt missing?
11. What would make you try the SDK or API next?
12. What would make you trust this project more?
13. What is the smallest next example you would want to see added?

---

## 5. Reviewer Safety Instructions

The following safety rules apply to all reviewers submitting feedback in public GitHub issues,
discussions, or pull requests.

1. **Use synthetic/demo data only.** The repository uses synthetic demo data throughout.
   All examples and reproduction steps should use synthetic identifiers (e.g. `demo-subject-001`,
   `test-grant-abc`). Do not use real grant application data.

2. **Do not share secrets.** Do not include API tokens, private keys, passwords, session tokens,
   or any value that could grant system access in public issues. Use placeholder values only.

3. **Do not share customer data.** Do not paste real grant applications, institutional records,
   personally identifiable information, or beneficiary data into any public channel.

4. **Do not share private grants or institutional data.** Do not include real institutional
   funding records, award identifiers linked to real organizations, or any non-public grant
   data in public issues or pull requests.

5. **Do not post exploit details publicly.** If you discover a potential security vulnerability,
   report it through GitHub Security Advisories as described in SECURITY.md. Do not post exploit
   steps, proof-of-concept payloads, or sensitive system details in public issues.

6. **Direct security-sensitive reports to GitHub Security Advisories.** If GitHub Security
   Advisories are unavailable for any reason, open a minimal public issue without exploit
   details or secrets and explicitly request a private reporting path.

---

## 6. Feedback Recording Model

Feedback received from external reviewers should be recorded internally using the following
fields. Do not record private reviewer identity unless it was voluntarily provided outside
this task.

| Field | Type | Description |
|-------|------|-------------|
| `reviewer_profile` | string | Archetype matched — e.g. `external-backend-developer` |
| `review_date` | date | ISO 8601 date — e.g. `2026-06-15` |
| `public_commit_reviewed` | string | Git commit hash at time of review |
| `reviewer_tasks_attempted` | array | Tasks the reviewer attempted from the task list |
| `quickstart_result` | string | `success` / `partial` / `failed` / `skipped` |
| `first_verifiable_output_result` | string | `match` / `mismatch` / `not-run` / `error` |
| `docs_clarity_score` | integer 1–5 | Self-reported clarity score (5 = very clear) |
| `trust_score` | integer 1–5 | Self-reported trust score (5 = high trust) |
| `caveat_visibility` | string | `visible` / `hard-to-find` / `missing` |
| `security_feedback` | string | Any security-relevant observation (paraphrased, no exploit details) |
| `broken_links` | array | Links that returned 404 or were stale |
| `confusing_claims` | array | Claims that felt misleading or overclaiming |
| `requested_examples` | array | Examples the reviewer wanted |
| `severity` | string | `critical` / `high` / `medium` / `low` / `info` |
| `category` | string | GL-183 triage category |
| `next_action` | string | `fix-now` / `clarify-docs` / `add-to-backlog` / `defer` / `close-as-non-scope` / `escalate-security` |
| `follow_up_needed` | boolean | `true` if follow-up action is required |

---

## 7. Triage Alignment with GL-183

All incoming reviewer feedback must be triaged using the GL-183 category and severity model.

**Reference:** GL-183 External Feedback Triage / Public Issue Hygiene

### Categories (assign exactly one per feedback item)

| Category | Use When |
|----------|----------|
| `blocker` | Something prevents the reviewer from completing any task |
| `confusing-docs` | Documentation is unclear, contradictory, or hard to follow |
| `broken-quickstart` | Clone/run path or first verifiable output does not work |
| `missing-example` | A useful example is absent |
| `product-question` | The reviewer is asking what GrantLayer does or how it works |
| `security-concern` | Potential security issue or sensitive reporting concern |
| `production-readiness-concern` | Concern about production suitability, support, or operational maturity |
| `feature-request` | Suggestion for new functionality |
| `non-scope-later` | Valid feedback out of scope for the current developer-preview posture |

### Severity Levels

| Severity | Criteria |
|----------|----------|
| `critical` | Immediate safety or trust failure |
| `high` | Serious issue affecting safety or first-use trust |
| `medium` | Important but not immediately blocking |
| `low` | Small correctness or clarity issue |
| `info` | Suggestion or non-blocking observation |

---

## 8. Non-Goals

The following are explicitly out of scope for this issue and for the first reviewer window:

- **No production SaaS promise.** GrantLayer is in developer-preview / controlled-pilot posture
  only. Do not promise production readiness.
- **No tenant/workspace isolation claim.** Tenant isolation is not implemented. Do not imply
  it is.
- **No real customer data collection.** Do not collect, store, or request real grant or customer
  data from reviewers.
- **No real grant/institutional data review.** Reviewers must use synthetic data only.
- **No payment or treasury flow.** Payment, wallet, and treasury features are not in current
  MVP scope.
- **No blockchain requirement in current MVP.** Blockchain is planned as an optional Phase 3
  layer.
- **No SLA or support promise.** No SLA is offered for developer preview.
- **No public issue template creation in this issue.** Templates were deferred by GL-183.
- **No GitHub label creation in this issue.** Labels are documented only in GL-183; no API
  changes are made.
- **No reviewer outreach sent in this issue.** The invite message above is a draft only.

---

## 9. Next Recommended Issue

**GL-185: First Reviewer Feedback Window / Feedback Capture**

The invite pack is ready. The next step is to open the first reviewer feedback window:
invite 2–5 reviewers manually using the invite message draft from this issue, record their
feedback using the feedback recording model, and triage each item using the GL-183 category
and severity model.

Public issue templates (GL-183 decision: `templates_deferred`) should remain deferred until
the first reviewer window confirms the category and label taxonomy is correct.

---

## Safety Confirmations

- No outreach was sent by this issue.
- No GitHub push was performed by this issue.
- No visibility change was performed by this issue.
- The internal repo was not pushed directly to GitHub by this issue.
- No GitHub API label changes were performed by this issue.
- No GitHub API issue changes were performed by this issue.
- Production SaaS readiness is not claimed.
- Tenant/workspace isolation is not claimed.
- Real customer data was not requested.
- Private grant data was not requested.
- Secrets were not requested.
- Exploit details were not requested publicly.
- Security-sensitive reports are directed to GitHub Security Advisories.

---

## Explicit Operational Statements

- **No outreach was sent.** This issue produces a draft invite pack only. No emails, messages,
  or invites were sent.
- **No GitHub push was performed.** This branch exists in the internal repository only.
- **No visibility change was performed.** The public repository visibility was not changed.
- **The internal repo was not pushed directly to GitHub.** Changes remain on the internal
  branch.
- **No GitHub API label or issue changes were performed.** All label and issue documentation
  is in docs/artifacts only.
