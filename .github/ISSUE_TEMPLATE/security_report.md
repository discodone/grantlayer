---
name: Security reports
about: Guidance for reporting security issues in GrantLayer
title: "[Security]: "
labels: security
---

## ⚠️ Do not open a public issue for sensitive security findings

If you have found a potential security vulnerability, authentication bypass, secret exposure, audit tampering risk, or data leakage issue:

**Do not open a public GitHub issue.**

Public issues are visible to everyone. Disclosing sensitive security findings publicly before they are fixed can put other users at risk.

---

## How to report a security issue

Please read the full [SECURITY.md](../../SECURITY.md) policy before reporting.

Once this repository is public, sensitive findings should be submitted via **[GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)** (private, coordinated disclosure). This feature will be enabled when the repository is published.

Until the repository is public, contact the maintainers directly as described in [SECURITY.md](../../SECURITY.md).

---

## Developer Preview caveats

- GrantLayer is a **developer preview**. It is not production SaaS.
- **Tenant isolation is not implemented.** Do not use with real customer data.
- Do not report issues that assume multi-tenant production deployment — they are already known out-of-scope for this stage.

---

## What to include in a security report

- A clear description of the vulnerability (without sensitive payloads in a public issue)
- The affected component (auth, audit log, grant lifecycle, SDK, examples)
- Reproduction steps (redacted as needed)
- Potential impact

---

## What NOT to include in any report (public or private)

- Real secrets, API tokens, or credentials
- Real customer data
- Private personal data
- Internal infrastructure paths

---

## Non-sensitive documentation or security feedback

If your feedback is **not** a vulnerability (e.g. a doc improvement about security best practices, a question about the threat model, or feedback on the agent safety examples), you may open a regular [Documentation feedback](documentation_feedback.yml) issue instead.
