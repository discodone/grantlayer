# GL-182: External Developer Feedback Intake

## Issue ID

GL-182

## Title

External Developer Feedback Intake — Developer Preview

## Context

GrantLayer is now publicly available on GitHub in a developer-preview / controlled-pilot posture.

The following readiness sequence is complete:

| Issue | Work | Result |
|-------|------|--------|
| GL-176 | Public snapshot published to GitHub | Done |
| GL-177 | Public repo smoke verification (fresh clone) | Passed with cautions |
| GL-178 | README.md and SECURITY.md post-public state correction | Done |
| GL-179 | GL-178 fixes pushed to public GitHub | Done |
| GL-180 | Public docs smoke verification (fresh clone) | Passed — no blockers |
| GL-181 | Public snapshot exclusion cleanup (governance docs excluded) | Done |

The repository is publicly readable at:
`https://github.com/Discodone/grantlayer.git`

This issue defines the lightweight plan for collecting early external developer feedback.

**No GitHub push was performed by this issue.**
**No visibility change was performed by this issue.**
**The internal repo was not pushed directly to GitHub.**

---

## Scope

This issue is planning and documentation only. It does not:

- Push to GitHub
- Change GitHub repository visibility
- Modify backend source code
- Modify API/OpenAPI, migrations, DB schema, or dependencies
- Collect real customer data
- Claim production SaaS readiness
- Claim tenant/workspace isolation is implemented

---

## Target Reviewer Profiles

Early feedback is most valuable from reviewers who match one or more of the following profiles:

### 1. External Backend Developer

- Familiar with Python, REST APIs, SQLite or PostgreSQL
- Can clone a repo, start a backend, and run tests in ~10 minutes
- Key questions: Is the quickstart clear? Does the API make sense?

### 2. AI-Agent Workflow Developer

- Builds or evaluates AI-agent pipelines (LangGraph, LangChain, or similar)
- Interested in audit trails, verification layers, and agentic compliance
- Key questions: Does the GrantLayer integration story make sense? Is the LangGraph example legible?

### 3. Grant / Compliance or Audit-Minded Reviewer

- Works with grant management, institutional compliance, or audit processes
- Does not need to be a developer
- Key questions: Do the concepts (evidence bundles, audit trails, policy evaluation) map to real institutional needs? Are the caveats about current limitations visible?

### 4. Security-Minded Technical Reviewer

- Reviews security posture of developer-preview software
- Familiar with OWASP, API security basics, responsible disclosure
- Key questions: Are the security caveats clear? Is the reporting channel obvious? Does the repository look clean of secrets or sensitive paths?

---

## Reviewer Tasks

Ask each reviewer to attempt the following, recording what succeeds, fails, or confuses them:

1. **Read README.md** — Determine if they can understand what GrantLayer is and does within 2 minutes.
2. **Read SECURITY.md** — Confirm the security reporting channel and current-limitations caveats are visible.
3. **Run the first verifiable output example:**
   ```bash
   git clone https://github.com/Discodone/grantlayer.git
   cd grantlayer
   python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
   ```
4. **Inspect the expected output:** Compare `/tmp/grantlayer_first_output.json` with `examples/first_verifiable_output.json`.
5. **Assess caveat clarity:** Are the "not production SaaS" and "tenant isolation not implemented" caveats visible and understandable?
6. **Report broken links or confusing docs** — Note any link that returns 404 or documentation that is unclear or contradictory.
7. **Report unclear claims or overclaims** — Flag any claim in the docs that seems to promise production readiness, tenant isolation, or customer onboarding.

---

## Feedback Questions

The following questions should guide early reviewer feedback:

### Comprehension

1. Can you understand what GrantLayer does in 2 minutes of reading the README?
2. What is your one-sentence summary of what GrantLayer is?
3. Which part of the README felt most confusing?

### Quickstart Experience

4. Can you run the first verifiable output in under 10 minutes?
5. Were any setup steps missing, unclear, or broken?
6. Is the expected output understandable? Does the record structure make sense?

### Caveat Visibility

7. Are the safety caveats ("not production SaaS", "tenant isolation not implemented") easy to find?
8. Is it clear that this is a developer preview and not a production service?

### Blocking Issues

9. What would block you from trying the SDK or API next?
10. Was anything missing that you expected to find?

### Credibility and Improvement

11. What would make the repository more credible or trustworthy?
12. Which next example would you most want to see?
13. Would you recommend this to a colleague? Why or why not?

---

## Feedback Triage Categories

All incoming feedback should be assigned exactly one primary category:

| Category | Description |
|----------|-------------|
| `blocker` | Something that prevents the reviewer from completing any task |
| `confusing-docs` | Documentation that is unclear, contradictory, or hard to follow |
| `broken-quickstart` | The first verifiable output or clone/run path does not work |
| `missing-example` | A useful example is absent that would aid understanding |
| `product-question` | A question about what GrantLayer does or how it works |
| `security-concern` | A report of a potential security issue (should also be filed via SECURITY.md channel) |
| `production-readiness-concern` | A question or concern about production suitability |
| `feature-request` | A suggestion for new product functionality |
| `non-scope-later` | Valid feedback that is out of scope for the current developer-preview posture |

---

## Severity Model

When triaging feedback, assign a severity level:

| Severity | Criteria |
|----------|----------|
| `critical` | Public credential leak, secret material in repository, broken public clone URL, harmful overclaim of production readiness, SECURITY.md reporting channel broken |
| `high` | Quickstart completely broken, security reporting channel unclear, misleading production SaaS claim, important safety caveat missing |
| `medium` | Confusing setup instructions, unclear caveat placement, important broken link, misleading but not harmful claim |
| `low` | Minor wording issue, formatting inconsistency, non-critical broken link, cosmetic confusion |
| `info` | Suggestion, future idea, or neutral observation with no urgency |

---

## Safety Instructions for Reviewers

The following rules apply to all feedback submitted in public GitHub issues, discussions, or pull requests:

1. **Do not include secrets or credentials in public issues.** This includes API tokens, private keys, passwords, or any value that could grant system access. Use synthetic placeholder values only.
2. **Do not include exploit details publicly.** If you discover a potential security vulnerability, use the GitHub Security Advisory channel described in SECURITY.md — do not post exploit steps in public issues.
3. **Do not include customer data.** Do not paste real grant applications, institutional records, or personally identifiable information into public issues.
4. **Do not include private grants or real institutional funding data.** All feedback examples should use synthetic identifiers (e.g. `demo-subject-001`, `test-grant-abc`).
5. **Use synthetic data only.** The repository uses synthetic demo data throughout; reviewers should do the same.
6. **Security-sensitive reports should be filed via GitHub Security Advisories.** See SECURITY.md for the reporting process.

---

## Non-Goals for Early Feedback

The following are explicitly out of scope and should not be reported as gaps for this developer-preview phase:

| Non-Goal | Reason |
|----------|--------|
| Production SaaS readiness | GrantLayer is in developer-preview / controlled-pilot posture only |
| Tenant/workspace isolation | Not implemented — stated caveat in README.md and SECURITY.md |
| Customer onboarding | No production onboarding process exists yet |
| Payment, treasury, or wallet flows | Not in current MVP scope |
| Blockchain integration | Planned as optional Phase 3 layer — not in MVP |
| Support SLA or uptime guarantee | No SLA is offered for developer preview |
| OAuth, JWT, or production authentication | Not implemented — developer preview uses static admin token |
| Collection or storage of real grants / customer data | Explicitly not claimed or supported in this posture |
| External CI/CD pipeline readiness | No production deployment pipeline |

Reviewers are encouraged to note these gaps as `non-scope-later` rather than blockers.

---

## How to Record Feedback Internally

Feedback received from external reviewers should be recorded as follows:

1. **Triage within 48 hours** of receipt.
2. **Assign category and severity** from the models above.
3. **Log in internal backlog** (GL-30 or equivalent) with:
   - reviewer profile type
   - category and severity
   - exact question/concern quoted
   - whether it affects README, SECURITY, examples, API, or other scope
   - proposed resolution or deferral reason
4. **Critical or high severity** items should be addressed before inviting the next batch of reviewers.
5. **Security concerns** filed publicly must be acknowledged and redirected to SECURITY.md channel immediately.

---

## Next Recommended Issue

After GL-182 feedback is collected, the next recommended step is:

**GL-183: External Feedback Triage / Public Issue Hygiene**

This issue should:
- Review all feedback received during the GL-182 intake window
- Triage each item by category and severity
- Identify any critical or high-severity items requiring immediate action
- Establish public GitHub issue labels for ongoing feedback hygiene
- Decide whether to add issue templates before widening the reviewer invite list

Alternatively, if public issue hygiene infrastructure is needed first:

**GL-183: Public Issue Template / Feedback Labels Readiness**

This issue should:
- Create `.github/ISSUE_TEMPLATE/` entries for bug reports, feedback, and security concerns
- Add GitHub issue labels matching the triage categories above
- Link issue templates from CONTRIBUTING.md

---

## Safety Confirmations

- No GitHub push was performed by this issue.
- No GitHub visibility change was performed by this issue.
- The internal Forgejo repository was not pushed directly to GitHub.
- Production SaaS readiness is not claimed anywhere in this document.
- Tenant/workspace isolation is not claimed anywhere in this document.
- No real customer data is collected or requested.
- No secrets or credentials are requested from reviewers.
- Security-sensitive reports are directed to GitHub Security Advisories (per SECURITY.md).
