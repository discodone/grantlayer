# GL-163: Post-Public Agent Intake & First Feedback Triage

## 1. Purpose

This document defines the first post-public intake and triage workflow after the GrantLayer
developer-preview snapshot was published to public GitHub.

**Public GitHub is a clean developer-facing snapshot**, not the internal Forgejo repository.
The public repository contains no backend source code, no `.claude/` directory, no internal
CI configuration, and no full git history.

**Internal Forgejo remains the source of truth.** All changes originate internally, pass
validation and scanning, and are promoted to the public snapshot through a controlled process.
This workflow exists to route public feedback into the internal source of truth without
bypassing that process.

GrantLayer is a Developer Preview — an API-first verification, audit, and compliance layer
for agentic grant workflows. It is not production SaaS. Tenant isolation is not implemented.

---

## 2. Scope

This workflow covers:

- Public GitHub Issues filed by developers or coding agents
- Pull requests, if any appear on the public repository
- Developer feedback received through GitHub Issues or Discussions
- Coding-agent reports (automated or semi-automated findings)
- Security reports filed through SECURITY.md or direct contact
- README and documentation suggestions
- Public snapshot packaging issues (unexpected files, missing files, broken links)
- First post-public snapshot update decisions

---

## 3. Non-Goals

The following are explicitly excluded from this workflow:

- Direct public GitHub hotfixes except in a narrowly defined emergency (see Section 11)
- Live GitHub API automation that creates issues, comments, or labels programmatically
- Production incident response or on-call escalation
- Making or endorsing any claim that GrantLayer is ready for production SaaS deployment (this is a Developer Preview only)
- Making or endorsing any claim that tenant-level workspace isolation is in place (it is not; this remains a known gap)
- Accepting real secrets or real customer data from external reporters
- Merging public GitHub history into internal Forgejo (public history is a snapshot, not a branch)
- Processing out-of-scope feature requests as immediate work items

---

## 4. Intake Channels

### GitHub Issues
Accept: bug reports, documentation questions, SDK/API usage questions, agent integration
questions, compliance language feedback, public snapshot packaging concerns.

Each issue is assigned a triage category (Section 5) and severity (Section 6) before any
internal issue is created.

### GitHub Discussions (if enabled)
Treat the same as GitHub Issues for intake purposes. Discussions are lower-signal until
a concrete reproducible finding or clear question is identified.

### SECURITY.md Reports
Route immediately to security report handling (Section 9). Do not request real secrets
or real customer data from the reporter.

### Direct Developer Feedback
Feedback received through other channels (email, community forums, direct contact) is
treated as equivalent to a GitHub Issue. Create an internal issue with a reference to
the source.

### Coding-Agent Reports
Apply the agent feedback intake policy (Section 8). Require file/line references and
classification before creating an internal issue.

### README / Documentation Suggestions
Accept wording suggestions, clarity improvements, broken link reports, and missing example
reports. Classify under `docs` or `public-snapshot` as appropriate.

---

## 5. Triage Categories

| Category | Description |
|---|---|
| `security` | Potential security vulnerability in public assets or documentation |
| `sensitive-data` | Report of secrets, customer data, or private info in public content |
| `public-snapshot` | Unexpected or missing files, broken packaging, CI issues in public repo |
| `docs` | README, documentation, or example clarity and accuracy |
| `agent-feedback` | Findings from coding agents or automated tools |
| `sdk` | SDK usage questions, bugs, or integration issues |
| `dashboard` | Questions or issues related to the demo dashboard |
| `compliance-language` | Feedback on audit, compliance, or regulatory language in docs |
| `feature-request` | Suggestions for new capabilities or behaviour |
| `bug-report` | Reproducible defect in the developer-preview implementation |
| `question` | Usage or support questions with no reproducible defect |
| `out-of-scope` | Request outside the Developer Preview scope or forbidden scope |

A single item may carry multiple categories. Security and sensitive-data categories take
precedence and must be triaged before all others.

---

## 6. Severity and Priority Model

### P0 — Immediate Action Required
- Active public exposure of a real secret or customer data in any public asset
- Exploitable security vulnerability in public assets (docs, examples, dashboard, SDK)
- Materially misleading production-readiness or compliance claim that could cause harm

P0 items are handled same-day. If the exposure is in a live public file and cannot wait
for the normal snapshot cycle, the emergency exception (Section 11) applies.

### P1 — High Priority
- Public documentation or agent guidance that is materially misleading or broken in a way
  that blocks integrators
- Public snapshot packaging issue (unexpected internal file, missing required file)
- Broken examples or SDK code that prevents the documented quickstart from working
- Confirmed security issue that is not yet publicly exploitable but requires prompt remediation

P1 items are addressed in the next snapshot update cycle.

### P2 — Normal Priority
- Usability improvements to documentation or examples
- Missing examples that would meaningfully help integrators
- Wording clarity improvements that are accurate but not optimal
- Non-blocking SDK improvements
- Agent integration improvements

P2 items are batched into planned snapshot updates.

### P3 — Future / Roadmap
- Feature requests for capabilities beyond the current Developer Preview scope
- Architectural suggestions
- Long-term compliance or certification roadmap ideas

P3 items are noted but do not drive immediate action.

---

## 7. First-Week Monitoring Checklist

Run the following checks daily or near-daily during the first week after public publication:

- [ ] Review new GitHub Issues opened since last check; assign triage category and severity
- [ ] Check for new security reports via SECURITY.md or direct contact
- [ ] Verify no unexpected files have appeared on the public repository (backend/, .claude/, secrets)
- [ ] Confirm README accurately describes the Developer Preview scope (no production-ready claims)
- [ ] Confirm no tenant-isolation-implemented claims have appeared in public content
- [ ] Check for unexpected GitHub Actions or CI activity on the public repository
- [ ] Review GitHub dependency and security alerts if visible on the public repository
- [ ] Check for coding-agent reports mentioning GrantLayer (GitHub Issues or external sources)
- [ ] Note questions about production readiness or tenant isolation and triage appropriately
- [ ] Confirm no private hostnames, internal paths, or internal IP ranges are visible publicly
- [ ] Review any pull requests filed against the public repository (expected: rare to none)
- [ ] Check public scanner status against the current public HEAD

---

## 8. Agent Feedback Intake Policy

Coding-agent findings are accepted subject to the following requirements:

**Required for acceptance:**
- Reproducible file and line reference within the public repository content
- Classification: one of `bug`, `security`, `docs`, or `suggestion`
- Confirmation that no real secret or customer data is included in the report

**Not accepted without the above:**
- Broad automated rewrites with no scoped issue description
- Findings without specific file/line references
- Reports claiming production readiness or completeness failures that are out of scope for
  a Developer Preview

**Processing:**
1. Agent findings that meet the requirements are reviewed by a human.
2. Accepted findings are converted into internal Forgejo issues before any changes are made.
3. Changes are made on an internal branch, validated, and promoted through the clean snapshot
   workflow — not applied directly to the public repository.

Agent-generated pull requests against the public repository are not merged. They are treated
as structured issue reports and converted to internal issues if the finding is valid.

---

## 9. Security Report Handling

1. **Acknowledge** the report promptly (same business day for P0, within two business days otherwise).
2. **Do not request** real secrets, customer credentials, or real personal data from the reporter.
3. **Reproduce internally** using synthetic or test data only.
4. **Classify severity** using the model in Section 6.
5. **Fix internally** on an internal branch following the standard validation process.
6. **Publish through the clean snapshot** — do not push fixes directly to the public repository
   unless the emergency exception (Section 11) applies.
7. **Use a direct public hotfix only** for documented P0 emergencies with active public exposure.
8. **Preserve evidence and audit notes** internally: the report, classification decision,
   remediation steps, and timeline.
9. **Do not disclose** details of an unmitigated security issue publicly before the fix is published.

---

## 10. Public Update Workflow

All changes that result from triage — whether documentation fixes, example corrections,
snapshot packaging fixes, or security remediations — follow this sequence:

1. **Internal issue** — create an internal Forgejo issue referencing the public feedback source
2. **Internal branch** — create a branch from internal main
3. **Implement and validate** — make the change, run tests, run the public scanner gate
4. **Merge to internal main** — complete code review and merge
5. **Build clean public snapshot** — run the clean snapshot build process
6. **Scanner clean** — confirm the scanner passes on the snapshot before pushing
7. **Push public snapshot** — push the clean snapshot to the public GitHub repository
8. **Revoke temporary token** — revoke any short-lived GitHub token used for the push
9. **Post-push verification** — confirm the public repository reflects the intended state;
   confirm no unexpected files are present

No step may be skipped. Scanner must be clean before the public push.

---

## 11. Emergency Exception

A direct public hotfix is allowed only when all of the following are true:

- There is an active public exposure of a real secret, customer data, or materially harmful
  content that cannot wait for a full internal cycle
- The change is the minimum necessary to remove the harmful content
- No broad refactors, rewrites, or unrelated changes are included

If a direct public hotfix is applied:

1. Document the decision, rationale, and change immediately in an internal note
2. Backport the change to the internal Forgejo source of truth within the same working day
3. Run the full validation and scanner cycle on the backport before the next snapshot push
4. Record the emergency exception in the internal audit log

The emergency exception does not authorize live GitHub API automation, broad rewrites, or
changes that bypass internal validation.

---

## 12. Go / No-Go Criteria for First Post-Public Changes

### Go
- Scanner clean on the internal snapshot
- No `backend/` or internal source files exposed in the public snapshot
- No `.claude/` directory or files in the public snapshot
- No private hostnames or internal IP ranges in any public content
- No real secrets or customer data in any public content
- No production-ready or tenant-isolation-implemented claims in any public content
- Internal main is clean and tests pass (or the change is docs-only with justified validation)

### No-Go
- Scanner reports any blocker on the snapshot
- Source-of-truth state is unclear (internal main not clean, or snapshot build process incomplete)
- Unreviewed secret or security issue that has not been classified and mitigated
- Public git history rewrite required without explicit documented approval
- Live direct GitHub edits have been made and not yet backported to internal source of truth

---

## 13. Recommended Labels / Categories

Apply these labels to GitHub Issues for triage (text only — do not call the GitHub API
programmatically to create or assign labels):

- `security` — security vulnerability or concern
- `sensitive-data` — real secrets, customer data, or PII in public content
- `docs` — documentation clarity, accuracy, or completeness
- `public-snapshot` — snapshot packaging, unexpected files, missing files
- `agent-feedback` — finding from a coding agent or automated tool
- `sdk` — SDK usage, bug, or integration
- `dashboard` — demo dashboard question or issue
- `compliance-language` — audit, compliance, or regulatory wording
- `question` — usage or support question
- `out-of-scope` — outside Developer Preview scope
- `good-first-review` — clearly scoped, low-risk, good candidate for fast internal triage

---

## 14. Handoff and Next Actions

1. **Monitor first public feedback** — apply the first-week monitoring checklist (Section 7)
   daily for the first seven days after public publication
2. **Create internal issues** for any accepted feedback — do not make changes in response to
   public feedback without a corresponding internal Forgejo issue
3. **Avoid direct public edits** — except for documented emergencies, all changes flow through
   the internal source of truth and clean snapshot process
4. **Review after first 5–10 public interactions** or after any P0 or P1 finding — reassess
   triage categories, severity model, and monitoring checklist coverage
5. **Next planned review** — after the first complete snapshot update cycle triggered by
   public feedback

---

*GrantLayer Developer Preview — GL-163 Post-Public Agent Intake & First Feedback Triage.*
*This document covers the developer-preview phase only. It is not production SaaS documentation.*
*Tenant isolation is not implemented. No real secrets. No real customer data.*
*Internal Forgejo remains the source of truth. Public GitHub is a clean snapshot.*
