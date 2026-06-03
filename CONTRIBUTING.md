# Contributing to GrantLayer

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

Thank you for your interest in contributing to GrantLayer. This document describes the contribution rules, expectations, and safety boundaries for the developer-preview phase.

---

## 1. Project Status

GrantLayer is in **Developer Preview**.

| Posture | Value |
|---------|-------|
| Maturity | Developer Preview — local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub release | **Available** — repository publicly accessible at `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

This is **not a production SaaS**. Do not deploy to shared multi-tenant infrastructure without completing the remaining hardening gates.

---

## 2. Contribution Model

We welcome small, scoped contributions. The safest default contribution types are:

- Documentation improvements
- Test additions or fixes
- Example updates
- Developer-experience tooling

Production code changes require an explicit issue scope and maintainer agreement before work begins.

### Issue-first preferred

- Open or reference an issue before starting significant work.
- Describe the scope, motivation, and expected files changed.
- Wait for maintainer acknowledgment before investing large effort.

### Safest default

If you are unsure what to contribute, start with:

- Fixing typos or outdated links in docs
- Adding missing test coverage
- Improving error messages or docstrings
- Updating examples to be clearer or safer

---

## 3. Local Setup

See the following documents for setup instructions:

- [README.md](README.md) — repository overview and quick start
- [docs/ten_minute_quickstart.md](docs/ten_minute_quickstart.md) — clone, install, start backend, run smoke path
- [sdk/python/README.md](sdk/python/README.md) — import the SDK and make typed calls

No cloud service, database subscription, or third-party API is required for the baseline path.

---

## 4. Testing Expectations

All contributions should include targeted tests that cover the changed behavior.

- Run targeted tests for the area you changed.
- Run the security boundary regression test:
  ```bash
  python3 -m unittest backend.tests.test_security_boundary_regression -v
  ```
- Run the full backend suite before merge when possible:
  ```bash
  scripts/run-full-backend-suite.sh
  ```
- If the full suite cannot be run locally, state this clearly in the pull request.

---

## 5. Coding-Agent Contribution Rules

GrantLayer is designed to be especially attractive for AI/coding agents. If you are an agent or assisting an agent, follow these rules:

1. **Follow issue-specific allowed/forbidden files** — each issue defines what may and may not be changed. Do not exceed the scope.
2. **Do not change production code unless the issue explicitly allows it** — `backend/src/*` is off-limits unless the issue says otherwise.
3. **Do not stage `.claude/`** — the `.claude/` directory is ignored and must not be committed.
4. **Do not add internal URLs or paths** — use relative paths and public-safe placeholders only.
5. **Do not add real secrets or customer data** — all examples must use synthetic identifiers and placeholder tokens.
6. **Agent entry points are available** — `AGENTS.md`, `llms.txt`, and the agent integration manifest are the primary agent-facing files (added in GL-154). Read them before starting work.

---

## 6. Security and Data Rules

- **No real secrets** — never commit API keys, Bearer tokens, JWTs, encryption keys, or passwords.
- **No real customer data** — never commit names, addresses, identifiers, or other personal/organizational data from real customers.
- **No private personal data** — do not include any personally identifiable information about real individuals.
- All documentation and examples must use obviously fake placeholders (e.g. `demo-admin-token-gl146`, `gl146-demo-subject-001`).

---

## 7. DCO and CLA

### DCO (Developer Certificate of Origin)

DCO-style sign-off is **recommended** for future public contributions. When committing, include a sign-off line:

```
Signed-off-by: Your Name <your.email@example.com>
```

This certifies that you have the right to submit the contribution under the Apache License 2.0.

### CLA (Contributor License Agreement)

A CLA is **not required now**. The project may revisit this decision later if the contribution volume or legal requirements change.

---

## 8. Pull Request Expectations

A good pull request includes:

1. **Summary** — what changed and why.
2. **Scope** — which files were changed and which were intentionally left untouched.
3. **Tests run** — which test commands were executed and their results.
4. **Caveats** — any known limitations, follow-up work, or items that could not be tested.

Please keep pull requests small and focused. Large refactorings should be split into multiple issues and pull requests.

---

## 9. No Overclaims

All contributions must preserve the following messaging:

- Do **not** claim production SaaS readiness.
- Do **not** claim tenant isolation is implemented.
- Do **not** claim production readiness beyond the current developer-preview / controlled-pilot posture.
- Do **not** claim external adoption or real customer usage.

If you update public-facing documentation, ensure the caveats in Section 1 remain prominent.

---

## 10. Next Steps

The repository is publicly available on GitHub. Contributions follow the issue-first workflow described above.

For security-sensitive reports, use [GitHub Security Advisories](https://github.com/Discodone/grantlayer/security/advisories/new) — do not open public issues for vulnerabilities.

> This CONTRIBUTING.md was created in **GL-153 LICENSE / CONTRIBUTING / SECURITY Decision Pack** and updated in **GL-187 Public Docs Stale Claim Cleanup**. It does **not** change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation.
