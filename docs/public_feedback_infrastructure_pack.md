# GL-192 Public Feedback Infrastructure Pack

**Issue ID:** GL-192  
**Date:** 2026-06-03  
**Status:** complete — templates_added  
**Branch:** gl-192-public-feedback-infrastructure-pack  
**Base commit:** d565653

---

## 1. Context

GrantLayer is in public Developer Preview on GitHub at
`https://github.com/Discodone/grantlayer.git`.

GL-187 through GL-191 delivered public docs cleanup, a first-output verify helper,
a grant lifecycle evidence bundle, a demo endpoint safety guard, and a developer
experience polish pack. External developers can now run two no-install examples,
follow a working quickstart, and consult troubleshooting guidance.

GL-192 formalises the public feedback infrastructure: intake categories, severity
model, label taxonomy plan, issue template guidance, security-sensitive routing,
and safe round-2 reviewer guidance.

---

## 2. Scope

**Docs/test/artifact only.** No changes to backend/src, OpenAPI, migrations, DB
schema, dependency manifests, SDK implementation, examples runtime, frontend,
website, design, GitHub Actions/workflows, or snapshot publish scripts.

**Decision: templates_added.** GitHub issue templates were added in a prior
hardening cycle (GL-156) and are confirmed to meet all GL-192 requirements.
No new template files are added by GL-192. The infrastructure is complete and
documented here.

---

## 3. Public Feedback Intake Model

### 3.1 Feedback categories

| Category | Description | Template |
|---|---|---|
| `quickstart-feedback` | Friction, confusion, or errors when following README / agent_quickstart.md | developer_feedback.yml |
| `first-output-feedback` | Issues with scripts/verify-first-output.sh or docs/first_output_verify_helper.md | developer_feedback.yml |
| `grant-lifecycle-example-feedback` | Issues with examples/grant_lifecycle_evidence_bundle.py or docs/grant_lifecycle_evidence_bundle.md | developer_feedback.yml |
| `documentation-feedback` | Unclear, missing, or inconsistent docs | documentation_feedback.yml |
| `developer-experience-feedback` | General DX pain: setup, error messages, tooling, agent workflow | developer_feedback.yml |
| `bug-report` | Reproducible software bug using synthetic/demo data | bug_report.yml |
| `feature-request` | Scoped improvement suggestion for Developer Preview stage | feature_request.yml |
| `product-question` | Questions about roadmap, architecture, tenant model, production posture | Open an issue with label `type:question` |
| `security-sensitive-report` | Vulnerability, auth bypass, secret exposure, audit tampering | **GitHub Security Advisories only — do not file publicly** |
| `non-scope-later` | Production SaaS deployment, real multi-tenant isolation, customer data handling | Deferred — out of Developer Preview scope |

### 3.2 Safe submission rules for all categories

- Use synthetic or demo data only. Do not submit real customer data, real
  institutional data, real grant applications, or real organisational records.
- Do not include secrets, tokens, API keys, passwords, or private keys in any
  public issue body, comment, or attachment.
- Do not include exploit details, payloads, or sensitive reproduction steps
  in public issues. File those privately via GitHub Security Advisories.
- For questions that assume production SaaS or tenant isolation: note the
  current caveat (`not production SaaS`, `tenant isolation not implemented`)
  in your question. The maintainers will answer preserving that caveat.

---

## 4. Severity Model

| Level | Meaning |
|---|---|
| `critical` | Production-blocking security issue (auth bypass, secret leak, data exposure). Route to GitHub Security Advisories immediately. |
| `high` | Significant correctness failure, misleading public safety statement, or security-adjacent concern not yet critical. |
| `medium` | Reproducible bug that degrades a documented workflow; confusing or incorrect documentation that could mislead developers. |
| `low` | Minor friction, cosmetic issues, non-blocking doc gaps. |
| `info` | General feedback, questions, observations with no actionable bug. |

### 4.1 Routing by severity

| Severity | Routing |
|---|---|
| `critical` | GitHub Security Advisories — private coordinated disclosure. Do not file publicly. |
| `high` (security-adjacent) | GitHub Security Advisories. High-level mention in a public issue is acceptable but no exploit details or secrets. |
| `high` (non-security) | Public issue — type:bug or type:docs as appropriate. |
| `medium` | Public issue. |
| `low` | Public issue. |
| `info` | Public issue — product question, DX feedback, or docs feedback as appropriate. |

### 4.2 Special routing rules

- **Security-sensitive reports:** GitHub Security Advisories
  (`https://github.com/Discodone/grantlayer/security/advisories`). Never in a
  public issue body.
- **Suspected secret or private-data leak:** Security advisory. Mark severity
  `critical`. Do not paste the leaked material.
- **Exploit details:** Security advisory only. Never public.
- **Customer or private grant data:** Do not submit at all — not even via
  security advisory. Use synthetic equivalents.
- **Public docs polish (no security angle):** Public issue okay.
  Label `type:docs` + `severity:low` or `severity:medium`.
- **Deterministic output mismatch using synthetic data:** Public issue okay.
  Label `type:bug` + `area:first-output` or `area:grant-lifecycle-example`.
- **Production SaaS questions:** Public product question okay. The answer
  must preserve the caveat: "GrantLayer is not production SaaS. Tenant
  isolation is not implemented."
- **Tenant isolation questions:** Public product question okay. The answer
  must preserve: "Tenant isolation is not implemented at this stage."

---

## 5. Label Taxonomy Plan

Labels are **recommended only**. They should be created manually in the GitHub
repository settings if maintainers choose to adopt them. No labels are created
or modified via the GitHub API by GL-192 or any automated process.

### Type labels

| Label | Purpose |
|---|---|
| `type:bug` | Reproducible software bug |
| `type:docs` | Documentation issue |
| `type:dx` | Developer experience feedback |
| `type:question` | Product question |
| `type:feature` | Feature request or improvement |
| `type:security-sensitive` | Security-sensitive (use GitHub Security Advisories instead of public issues) |

### Area labels

| Label | Purpose |
|---|---|
| `area:quickstart` | Quickstart / README / agent_quickstart.md |
| `area:first-output` | scripts/verify-first-output.sh / docs/first_output_verify_helper.md |
| `area:grant-lifecycle-example` | examples/grant_lifecycle_evidence_bundle.py |
| `area:agent-docs` | AGENTS.md, agent_task_contract.md, agent_integration_manifest.json |
| `area:public-preview` | Developer Preview posture / caveats / public docs in general |

### Severity labels

| Label | Purpose |
|---|---|
| `severity:critical` | Route to security advisory |
| `severity:high` | Significant impact — may need security advisory |
| `severity:medium` | Reproducible, degrades a documented workflow |
| `severity:low` | Minor friction or cosmetic |

### Status labels

| Label | Purpose |
|---|---|
| `status:needs-triage` | Newly opened, not yet reviewed |
| `status:accepted` | Confirmed valid, will be addressed |
| `status:deferred` | Valid but deferred to a later stage |
| `status:not-planned` | Out of scope for current stage |

### Safety labels

| Label | Purpose |
|---|---|
| `safety:no-secrets` | Verified to contain no secrets or sensitive data |
| `safety:needs-advisory` | Should be moved to GitHub Security Advisories |

---

## 6. Issue Template Guidance

The following GitHub issue templates are in place under `.github/ISSUE_TEMPLATE/`:

| File | Category coverage |
|---|---|
| `bug_report.yml` | `bug-report` |
| `developer_feedback.yml` | `quickstart-feedback`, `first-output-feedback`, `grant-lifecycle-example-feedback`, `developer-experience-feedback` |
| `documentation_feedback.yml` | `documentation-feedback` |
| `feature_request.yml` | `feature-request` |
| `security_report.md` | `security-sensitive-report` — routes to GitHub Security Advisories |
| `agent_task_request.yml` | Agent task scoping (not a public feedback category) |
| `config.yml` | Disables blank issues; links to security policy and agent docs |

For `product-question` (`type:question`): no dedicated template. Reporters
should open a plain issue using the label `type:question`. Maintainers will
answer preserving the Developer Preview caveats.

### 6.1 Required safety content in every template

Every public-facing template includes or must include:

- Do not include secrets (API keys, tokens, passwords, private keys).
- Do not include real customer data.
- Do not include private grants or institutional data.
- Do not include exploit details in public issues.
- Use synthetic or demo data only.
- For security-sensitive reports, use GitHub Security Advisories.

These are enforced as required checkboxes in the structured `.yml` templates
and as explicit notices in the markdown templates.

### 6.2 Developer Preview caveat in templates

Every template states:

> Developer Preview — GrantLayer is not production SaaS.
> Tenant isolation is not implemented.

This prevents reviewers from accidentally filing issues that assume production
deployment or multi-tenant isolation.

---

## 7. Security-Sensitive Handling

**Security-sensitive issues must not be filed as public GitHub issues.**

Use GitHub Security Advisories:
`https://github.com/Discodone/grantlayer/security/advisories`

### What belongs in a security advisory (not a public issue)

- Authentication bypass or privilege escalation
- Secret, token, or credential exposure in tracked files or outputs
- Audit log tampering or suppression vectors
- Data leakage across intended boundaries
- Exploit reproduction details, payloads, or proof-of-concept code
- Sensitive system information (internal paths, infrastructure details)

### What a public issue may include

- A high-level description of the type of concern (e.g. "I noticed a potential
  auth issue in the grant approval flow") without exploit details.
- A request for a private reporting path if Security Advisories are unavailable.

### What must never appear in any report (public or private)

- Real secrets, API tokens, or credentials
- Real customer data, real grant applications, institutional records
- Private personal data (names, addresses, identifiers of real individuals)
- Internal infrastructure paths, hostnames, or private remotes

### Reporting process

1. Read [SECURITY.md](../SECURITY.md).
2. Open a GitHub Security Advisory using the private advisory form.
3. Describe the issue, affected component, reproduction steps (redacted as
   needed), and potential impact.
4. Wait for maintainer response before any public disclosure.

---

## 8. Round-2 Reviewer Invite Guidance

This section provides safe guidance for a second wave of developer reviewers.
**No outreach is sent by GL-192.**

### What reviewers can try

1. **First-output verify helper**
   Run `python3 scripts/verify-first-output.sh` (or `bash scripts/verify-first-output.sh`).
   Expected: deterministic JSON output, no backend or secrets required.
   Reference: [docs/first_output_verify_helper.md](first_output_verify_helper.md)

2. **Grant lifecycle evidence bundle**
   Run `python3 examples/grant_lifecycle_evidence_bundle.py`.
   Expected: full grant lifecycle simulation with audit chain, no backend required.
   Reference: [docs/grant_lifecycle_evidence_bundle.md](grant_lifecycle_evidence_bundle.md)

3. **Quickstart**
   Follow README → "What to try first" section.
   Expected: clear entry path to both no-install examples.

4. **Agent task workflow**
   Read [AGENTS.md](../AGENTS.md) and [docs/agent_task_contract.md](agent_task_contract.md).
   Open a scoped agent task request issue using `.github/ISSUE_TEMPLATE/agent_task_request.yml`.

### How to report findings

- Use the appropriate issue template (bug, docs, DX feedback, feature request).
- Use synthetic or demo data only.
- For security-sensitive concerns, use GitHub Security Advisories — not public issues.

### What reviewers should not do

- Do not provide real customer data, real grant applications, or real
  institutional records.
- Do not include real secrets, tokens, API keys, or passwords.
- Do not include exploit details in public issue bodies.
- Do not assume GrantLayer is production SaaS — it is not.
- Do not assume tenant isolation is implemented — it is not.

---

## 9. Non-Goals

- Creating GitHub labels via API — label taxonomy is recommended only.
- Creating GitHub issues or pull requests via API.
- Sending reviewer outreach — no contact is made by this issue.
- Modifying backend/src, OpenAPI, migrations, DB/schema, dependency manifests,
  SDK implementation, examples runtime, frontend, website, design.
- Changing GitHub repository settings or visibility.
- Changing GitHub Actions/workflow files.
- Claiming production SaaS readiness or tenant isolation is implemented.
- Requesting real customer data, private grants, secrets, or exploit details.
- Adding paperclip or external SaaS status updates.

---

## 10. Safety Confirmations

| Confirmation | Status |
|---|---|
| No GitHub push performed | ✓ confirmed |
| No visibility change performed | ✓ confirmed |
| Internal repo not pushed directly to GitHub | ✓ confirmed |
| No GitHub API label changes performed | ✓ confirmed |
| No GitHub issue changes performed | ✓ confirmed |
| No reviewer outreach sent | ✓ confirmed |
| No backend/src changes | ✓ confirmed |
| No OpenAPI changes | ✓ confirmed |
| No migration or DB/dependency changes | ✓ confirmed |
| No frontend/website/design changes | ✓ confirmed |
| No GitHub workflow changes | ✓ confirmed |
| No snapshot publish script behavior changes | ✓ confirmed |
| No production SaaS claim | ✓ confirmed |
| Tenant isolation not claimed | ✓ confirmed |
| No real customer data requested | ✓ confirmed |
| No private grant data requested | ✓ confirmed |
| No secrets requested | ✓ confirmed |
| No exploit details included | ✓ confirmed |
| Security-sensitive reports routed to GitHub Security Advisories | ✓ confirmed |

---

## 11. Next Recommended Issue

GL-192 Combined Merge-and-Publish for Public Feedback Infrastructure Pack

Merge `gl-192-public-feedback-infrastructure-pack` to internal main, then run
the snapshot publish process to push the feedback infrastructure documentation
to the public GitHub repository.

---

## Artifact Reference

JSON artifact: [docs/examples/gl192/public_feedback_infrastructure_pack.json](examples/gl192/public_feedback_infrastructure_pack.json)

Tests: `backend/tests/test_gl192_public_feedback_infrastructure_pack.py`
