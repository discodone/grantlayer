# Security Policy

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

This document describes the security posture, reporting guidance, and data-handling rules for GrantLayer.

---

## 1. Supported Status

GrantLayer is in **Developer Preview** with a controlled pilot posture.

| Posture | Value |
|---------|-------|
| Maturity | Developer Preview — local evaluation and controlled pilot only |
| Production SaaS support guarantee | **Not provided** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub repository | **Available** — publicly accessible at `https://github.com/Discodone/grantlayer.git` (GL-176) |

There is **no production SaaS support guarantee yet**. Do not deploy to shared multi-tenant infrastructure without completing the remaining hardening gates.

---

## 2. Reporting Guidance

The GrantLayer repository is publicly available on GitHub at `https://github.com/Discodone/grantlayer.git`.

**Active security reporting channel:** Please report security issues via **GitHub Security Advisories** for this repository (`https://github.com/Discodone/grantlayer/security/advisories`). If advisories are unavailable, open a minimal public issue that does not include exploit details or secrets and request a private reporting path.

**Important:** Do not disclose exploit details, secrets, or sensitive reproduction steps publicly (e.g. in public issues, comments, or pull requests). Always use a private reporting path for vulnerability details.

General guidance:
- Provide a clear description, reproduction steps, and impact assessment.
- Follow the data-handling rules in Section 5 of this document.

---

## 3. What to Report

We appreciate reports on the following categories:

- **Secrets exposure** — any real secret, key, token, or password found in tracked files.
- **Auth bypass** — any mechanism that allows unauthorized access to protected endpoints or data.
- **Audit tampering** — any way to modify, delete, or suppress audit records without detection.
- **Data leakage** — any way to access data across intended boundaries.
- **Dependency vulnerabilities** — known vulnerabilities in runtime or development dependencies.
- **Unsafe examples or documentation** — examples that encourage unsafe practices or contain real secrets.

---

## 4. Out of Scope

The following are considered out of scope for this security policy:

- **Social engineering** — attacks targeting individuals rather than the software.
- **Attacks against third-party services** — vulnerabilities in services GrantLayer depends on but does not control.
- **Spam or DoS against public infrastructure** — denial-of-service or spam attacks against publicly hosted instances.

---

## 5. Data Handling

When reporting security issues, please follow these data-handling rules:

- **No real secrets** — do not include real API keys, tokens, or passwords in your report.
- **No real customer data** — do not include real customer names, addresses, identifiers, or other data.
- **No private personal data** — do not include personally identifiable information about real individuals.
- **Minimal reproduction only** — provide the smallest possible example that demonstrates the issue.

---

## 6. Current Caveats

- **Public GitHub repository is available** — the repository is publicly accessible at `https://github.com/Discodone/grantlayer.git` (GL-176). Public smoke verification completed (GL-177).
- **Production SaaS readiness not claimed** — the backend has not completed all production-hardening gates required for a shared multi-tenant SaaS.
- **Tenant isolation not implemented** — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers.
- **Developer Preview posture** — intended for local evaluation and controlled pilot only. Do not deploy to shared multi-tenant infrastructure.
- **No real secrets or customer data** — all examples and documentation use synthetic identifiers and placeholder tokens.

---

## 7. Current status

The repository is publicly available on GitHub (GL-176). Agent entry points and governance files
(GL-153–GL-155) are complete. Public smoke verification passed with cautions (GL-177).
README and SECURITY post-public state correction complete (GL-178).
