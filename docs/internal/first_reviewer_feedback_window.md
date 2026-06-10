# GL-185 First Reviewer Feedback Window / Feedback Capture

**Issue ID:** GL-185
**Title:** First Reviewer Feedback Window / Feedback Capture

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
| GL-184 | First External Reviewer Invite Pack | Done — merged_done |

GL-184 produced:
- 4 reviewer profiles
- A complete invite message draft
- 9 reviewer tasks including the first verifiable output
- 13 feedback questions across comprehension, trust, clarity, caveats, and next steps
- 6 reviewer safety instructions
- A 17-field feedback recording model
- Triage alignment with GL-183 categories and severity levels

This issue opens the first external reviewer feedback window in a controlled, safe way.
It does not send invites. It does not contact reviewers. It only defines the window,
the invitation procedure, the capture structure, and the safety checklist so the user
can invite reviewers manually and record responses internally.

This issue is documentation, test, and artifact only.

**No outreach was sent by this issue.**
**No GitHub push was performed by this issue.**
**No visibility change was performed by this issue.**
**The internal repo was not pushed directly to GitHub by this issue.**
**No GitHub API label or issue changes were performed by this issue.**

---

## Scope

This issue defines the first reviewer feedback window plan. It does not:

- Send emails or messages to reviewers
- Contact reviewers in any channel
- Push to GitHub
- Change GitHub repository visibility
- Modify backend source code (`backend/src/*`)
- Modify API/OpenAPI, migrations, DB schema, or dependencies
- Modify SDK implementation, frontend, website, or design assets
- Change GitHub workflows or snapshot publish script behavior
- Create GitHub labels via API
- Create or modify GitHub issues via API
- Collect real customer data
- Claim production SaaS readiness
- Claim tenant/workspace isolation is implemented
- Reference Paperclip

Allowed files in this issue:

- `docs/first_reviewer_feedback_window.md` (this document)
- `docs/examples/gl185/first_reviewer_feedback_window.json`
- `backend/tests/test_gl185_first_reviewer_feedback_window.py`

---

## 1. Feedback Window Definition

**Purpose:**
Collect controlled, qualitative feedback from 2–5 carefully selected external reviewers on
GrantLayer's developer preview. The goal is to identify blockers, confusing documentation,
broken quickstart paths, or missing examples before widening the reviewer pool or adding
public issue templates.

**Suggested length:** 5–10 business days from the date the first invite is sent.

**Target reviewer count:** 2–5 reviewers from GL-184 archetypes.

**Review source:** Public GitHub repository at
`https://github.com/Discodone/grantlayer.git`

**Feedback capture:** Manual/internal recording only. No automated collection. No public
form or survey. No webhook or API collection.

**Automated outreach:** None performed in this issue. All invites are sent manually by the
user.

**Window open signal:** When the user sends the first invite manually.

**Window close signal:** When either the window length expires or 2–5 responses have been
captured — whichever comes first.

---

## 2. Reviewer Invitation Procedure

The user should follow these steps manually. This issue does not perform any of them.

### Step 1: Select reviewers

Select 2–5 individuals matching one or more GL-184 reviewer profiles:
- External Backend Developer
- AI-Agent Workflow Developer
- Grant / Compliance or Audit-Minded Reviewer
- Security-Minded Technical Reviewer

Do not include real names or private contact details in this document.

### Step 2: Prepare the invite

Use the invite message draft from GL-184
(`docs/first_external_reviewer_invite_pack.md`, section 2).

Verify before sending:
- The public GitHub URL is correct:
  `https://github.com/Discodone/grantlayer.git`
- The technical preview / developer preview caveat is present.
- The "not production SaaS" disclaimer is present.
- The "tenant isolation not yet implemented" disclaimer is present.
- The safety rules (no secrets, no customer data, no exploit details) are present.
- The GitHub Security Advisories path is mentioned.
- No support SLA is implied.
- No customer onboarding is offered.
- No commercial commitment is implied.

### Step 3: Send manually

Send the invite message manually via a trusted private channel. Do not send via bulk email
or automated tooling. Do not include this in a public GitHub issue or discussion.

### Step 4: Record the invite

After each invite is sent, record internally:
- reviewer profile (archetype, not real name)
- date invite was sent
- public commit hash at time of invite

### Step 5: Await response

Reviewers may submit feedback via:
- A public GitHub issue on the repository
- A direct message through the private channel used to invite them

For security-sensitive feedback, direct reviewers to GitHub Security Advisories.

### Step 6: Capture each response

Use the feedback capture record model (section 3) to record each response internally
within 48 hours of receipt.

### Step 7: Triage

Use the GL-183 category and severity model (section 4) to triage each captured response.

---

## 3. Feedback Capture Record Model

Record the following fields for each reviewer response. Do not record private reviewer
identity beyond the archetype unless the reviewer voluntarily provided contact details
outside this task.

| Field | Type | Description |
|-------|------|-------------|
| `feedback_id` | string | Unique ID for this feedback record (e.g. `GL185-F001`) |
| `reviewer_profile` | string | Archetype matched (e.g. `external-backend-developer`) |
| `invite_sent_date` | date | ISO 8601 date the invite was sent (e.g. `2026-06-10`) |
| `response_received_date` | date | ISO 8601 date the response was received |
| `public_commit_reviewed` | string | Git commit hash at time of reviewer's review |
| `tasks_attempted` | array | Tasks the reviewer attempted from the GL-185 task list |
| `first_verifiable_output_attempted` | boolean | Whether the reviewer attempted the first verifiable output |
| `first_verifiable_output_result` | string | `match` / `mismatch` / `not-run` / `error` |
| `docs_clarity_score` | integer 1–5 | Self-reported clarity score (5 = very clear) |
| `trust_score` | integer 1–5 | Self-reported trust score (5 = high trust) |
| `caveat_visibility` | string | `visible` / `hard-to-find` / `missing` |
| `quickstart_result` | string | `success` / `partial` / `failed` / `skipped` |
| `security_reporting_clarity` | string | `clear` / `unclear` / `not-checked` |
| `broken_links_reported` | array | Links that returned 404 or were stale |
| `confusing_claims` | array | Claims that felt misleading or overclaiming |
| `requested_examples` | array | Examples the reviewer wanted |
| `category` | string | GL-183 triage category |
| `severity` | string | `critical` / `high` / `medium` / `low` / `info` |
| `blocking` | boolean | Whether this item blocks future reviewer invites |
| `security_sensitive` | boolean | Whether the feedback contains security-sensitive content |
| `private_follow_up_required` | boolean | Whether a private follow-up channel is needed |
| `next_action` | string | `fix-now` / `clarify-docs` / `add-to-backlog` / `defer` / `close-as-non-scope` / `escalate-security` |
| `notes` | string | Any additional context not captured in other fields |

---

## 4. Feedback Triage Flow

All feedback must be triaged using the GL-183 category and severity model.

**Reference:** GL-183 External Feedback Triage / Public Issue Hygiene.

### Categories (assign exactly one per feedback item)

| Category | Use When | Default Next Action |
|----------|----------|---------------------|
| `blocker` | Something prevents the reviewer from completing any task | fix-now |
| `confusing-docs` | Documentation is unclear, contradictory, or hard to follow | clarify-docs |
| `broken-quickstart` | Clone/run path or first verifiable output does not work | fix-now |
| `missing-example` | A useful example is absent | add-to-backlog or fix-now if it blocks comprehension |
| `product-question` | The reviewer is asking what GrantLayer does or how it works | answer publicly if safe and concise |
| `security-concern` | Potential security issue or sensitive reporting concern | escalate-security |
| `production-readiness-concern` | Concern about production suitability, support, or operational maturity | clarify docs — do not overpromise |
| `feature-request` | Suggestion for new functionality | add-to-backlog |
| `non-scope-later` | Valid feedback out of scope for the current developer-preview posture | defer and label clearly |

### Severity Levels

| Severity | Criteria | Typical Response Time |
|----------|----------|-----------------------|
| `critical` | Immediate safety or trust failure | Immediate — before next invite |
| `high` | Serious issue affecting safety or first-use trust | Same day |
| `medium` | Important but not immediately blocking | Within the window |
| `low` | Small correctness or clarity issue | Next doc polish issue |
| `info` | Suggestion or non-blocking observation | Backlog |

### Routing

- **Critical/High + security-sensitive:** Route immediately to GitHub Security Advisories.
  Do not discuss in public. Halt public engagement if a real secret or exploit detail was shared.
- **Broken quickstart (`broken-quickstart`, `blocker`):** Treat as an immediate fix candidate.
  Do not invite additional reviewers until the quickstart path is restored.
- **Confusing documentation (`confusing-docs`):** Schedule a docs polish issue (e.g. GL-186
  README/Docs Polish).
- **Feature request (`feature-request`):** Backlog without commitment. Do not imply the
  feature will be built for the developer-preview posture.
- **Production-readiness concern (`production-readiness-concern`):** Clarify the developer-preview
  posture in documentation. Do not promise production readiness, SLA, or onboarding.
- **Out of scope (`non-scope-later`):** Close or defer politely. Explain the current posture.
- **Security advisory unavailable:** If a reviewer cannot access GitHub Security Advisories,
  acknowledge the report publicly with a minimal, non-revealing comment and open a private
  follow-up channel.

---

## 5. Safety Checklist

The following safety rules must be observed before inviting any reviewer and during the
entire feedback window.

### Before sending any invite

- [ ] No secrets are requested from reviewers in the invite message.
- [ ] No customer data is requested from reviewers.
- [ ] No private grant or institutional data is requested.
- [ ] The invite message does not claim production SaaS readiness.
- [ ] The invite message does not claim tenant/workspace isolation is implemented.
- [ ] The invite message does not offer a support SLA.
- [ ] The invite message does not offer customer onboarding.
- [ ] No commercial commitment is implied.
- [ ] The GitHub Security Advisories path is clearly stated in the invite message.
- [ ] Reviewers are told to use synthetic/demo data only.

### During the feedback window

- [ ] Do not ask reviewers to share real customer data in public issues.
- [ ] Do not ask reviewers to share private grants or institutional records.
- [ ] Do not post exploit details in public GitHub issues.
- [ ] If a public issue contains secrets or exploit details, acknowledge and redirect
  immediately to GitHub Security Advisories. Do not quote or expand the sensitive content.
- [ ] If a report includes a real secret, treat it as an incident or rotation concern before
  responding publicly.
- [ ] Do not make production SaaS promises in public responses to feedback.
- [ ] Do not make tenant isolation claims in public responses.
- [ ] Do not make SLA or support commitments in public responses.
- [ ] Record all feedback internally within 48 hours of receipt.
- [ ] Triage all feedback using GL-183 category and severity model.
- [ ] Stop the feedback window immediately if a critical-severity safety issue is found.

---

## 6. Initial Reviewer Packet

This is a summary of what the user should send manually to each reviewer.
This issue does not send it.

**Public repository URL:**
`https://github.com/Discodone/grantlayer.git`

**Short project description:**
GrantLayer is a Python backend with a REST API and SDK for creating structured, verifiable
evidence bundles used in grant management and agentic compliance workflows.

**Technical preview caveat:**
This is a technical preview / developer preview only. It is not a production SaaS platform.
Tenant/workspace isolation is not yet implemented. No support SLA is offered.

**First verifiable output task:**
```
git clone https://github.com/Discodone/grantlayer.git
cd grantlayer
python3 examples/first_verifiable_output.py --output /tmp/gl_first_output.json
```
Compare `/tmp/gl_first_output.json` with `examples/first_verifiable_output.json`.

**Feedback questions (summary):**
1. What did you think GrantLayer does after reading the README?
2. Could you find the first verifiable output quickly?
3. Could you run it, or understand what it proves?
4. What felt confusing?
5. What felt trustworthy?
6. What felt missing?
7. Are the non-production caveats clear?
8. Are the security reporting instructions clear?
9. What would make you try the SDK or API next?
10. What would make you trust this project more?
11. What is the smallest next example you would want?

**Safety instructions summary:**
- Use synthetic/demo data only.
- Do not share secrets, credentials, or private keys in public issues.
- Do not share customer data or institutional records.
- Do not post exploit details publicly.
- Report security-sensitive issues via GitHub Security Advisories (see SECURITY.md).

**Security advisory reporting path:**
See SECURITY.md in the repository for the GitHub Security Advisories reporting path.

---

## 7. Success Criteria

GL-185 is considered successful when:

1. **2–5 reviewers invited manually** using the GL-184 invite message draft.
2. **At least 1–3 reviewer responses captured** in the feedback recording model within
   the feedback window.
3. **No secrets or customer data collected.** All feedback uses synthetic/demo data only.
4. **No security-sensitive details posted publicly.** Any security concern is routed to
   GitHub Security Advisories.
5. **Feedback categorized and severity-ranked** using the GL-183 triage model for each
   captured response.
6. **Next issues proposed** from the feedback — at minimum one follow-up issue identified
   from the triage results.

Partial success: If fewer than 2 responses are received within the window, the window can
be extended or additional reviewers added from the GL-184 profiles. A zero-response window
is not a failure if no blocking issues are found in the attempt.

---

## 8. Non-Goals

The following are explicitly out of scope for this issue:

- **No outreach sent by this issue.** The invite message is defined in GL-184. This issue
  prepares the operational plan only.
- **No production SaaS promise.** GrantLayer is in developer-preview / controlled-pilot
  posture only.
- **No tenant/workspace isolation claim.** Tenant isolation is not implemented.
- **No real customer data collection.** All feedback must use synthetic/demo data only.
- **No real grant/institutional data review.** Reviewers must use synthetic identifiers.
- **No payment or treasury flow.** Not in current MVP scope.
- **No blockchain requirement in current MVP.** Planned as optional Phase 3 layer.
- **No SLA or support promise.** No SLA is offered for developer preview.
- **No public issue template creation in this issue.** Templates remain deferred (GL-183
  decision: `templates_deferred`).
- **No GitHub label creation in this issue.** Labels are documented in GL-183; no API
  changes are made.
- **No GitHub issue creation in this issue.** Issues are created by reviewers, not by this
  issue.
- **No automated collection of personal reviewer data.** Do not collect names, email
  addresses, or contact details via any form, webhook, or API.

---

## 9. Next Recommended Issue

**GL-186: First Reviewer Feedback Triage**

After the feedback window closes (or when 2–5 responses are captured), the next step is to
triage all collected responses:
- Assign each response a GL-183 category and severity.
- Identify any critical or high-severity items requiring immediate action.
- Propose follow-up issues for each actionable triage outcome (docs polish, quickstart fix,
  missing example, etc.).
- Decide whether to widen the reviewer pool or add public issue templates before the next
  feedback round.

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
- Automated reviewer contact was not performed.

---

## Explicit Operational Statements

- **No outreach was sent.** This issue produces the feedback-window operational plan only.
  No invites were sent.
- **No GitHub push was performed.** This branch exists in the internal repository only.
- **No visibility change was performed.** The public repository visibility was not changed.
- **The internal repo was not pushed directly to GitHub.** Changes remain on the internal
  branch.
- **No GitHub API label or issue changes were performed.** All label and issue content is
  in docs/artifacts only.
