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
| Public GitHub release | **Not performed** — requires explicit later approval |

There is **no production SaaS support guarantee yet**. Do not deploy to shared multi-tenant infrastructure without completing the remaining hardening gates.

---

## 2. Reporting Guidance

### Before public release

If you discover a security issue before the repository is publicly available on GitHub:

- **Avoid public disclosure** before maintainers can respond.
- Contact the maintainers through the existing private channel.
- Provide a clear description, reproduction steps, and impact assessment.

### After public release

Once the repository is publicly available on GitHub, security issues should be reported through **GitHub Security Advisories** when that feature is enabled.

Until then, the reporting channel is **pending** and will be documented here after public release is approved.

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

- **Public release not approved by GL-153** — this security policy is part of the pre-publication governance baseline. Public GitHub publication has not happened and requires explicit later approval.
- **Production SaaS readiness not claimed** — the backend has not completed all production-hardening gates required for a shared multi-tenant SaaS.
- **Tenant isolation not implemented** — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers.

---

## 7. Next Steps

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-154 | AGENTS.md + llms.txt + Agent Integration Manifest | Add agent entry points, task contracts, and integration manifest. |

> This SECURITY.md was created in **GL-153 LICENSE / CONTRIBUTING / SECURITY Decision Pack**. It does **not** publish to GitHub, change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation.
