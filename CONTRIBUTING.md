# Contributing to GrantLayer

> GrantLayer turns agentic grant workflows into verifiable institutional records.

Thank you for your interest in contributing. This document covers everything you need to get started, report bugs, and submit pull requests.

---

## Quick start for first-time contributors

```bash
git clone https://github.com/discodone/grantlayer.git
cd grantlayer
cp .env.example .env
# Set GRANTLAYER_JWT_SECRET in .env — see QUICKSTART.md step 1
./nginx/generate-certs.sh
docker compose up -d
curl -k https://localhost/health   # → {"status": "ok", ...}
```

Full walkthrough: **[QUICKSTART.md](QUICKSTART.md)** (5–10 minutes, Docker required).

---

## 1. Project Status

GrantLayer is in **Developer Preview**.

| Posture | Value |
|---------|-------|
| Maturity | Developer Preview — local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub | `https://github.com/discodone/grantlayer` |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

This is **not a production SaaS**. Do not deploy to shared multi-tenant infrastructure.

---

## 2. Bug Reports and Feedback

We need external testers. The most valuable thing you can do right now is run the quickstart and tell us what breaks.

### Reporting a bug

1. Check [existing issues](https://github.com/discodone/grantlayer/issues) first.
2. Open a [new issue](https://github.com/discodone/grantlayer/issues/new) with:
   - What you ran (exact command)
   - What you expected
   - What happened instead (error message, unexpected output)
   - OS, Docker version, Python version

### Reporting a security issue

Use [GitHub Security Advisories](https://github.com/discodone/grantlayer/security/advisories/new) — do **not** open a public issue for vulnerabilities.

### General feedback

Comment on the [Call for early testers issue](https://github.com/discodone/grantlayer/issues) or open a new issue tagged `feedback`.

---

## 3. Local Setup

See [QUICKSTART.md](QUICKSTART.md) for the full step-by-step flow including:

- Docker Compose stack startup
- TLS cert generation (self-signed, local dev)
- JWT token generation
- Grant creation, listing, and audit log export

For SDK usage: [sdk/python/README.md](sdk/python/README.md)

No cloud service, database subscription, or third-party API is required.

---

## 4. Contribution Model

We welcome small, scoped contributions. The safest default types are:

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

If unsure what to contribute:

- Fix typos or outdated links in docs
- Add missing test coverage
- Improve error messages or docstrings
- Update examples to be clearer or safer

---

## 5. Testing Expectations

All contributions should include targeted tests that cover the changed behavior.

```bash
# Run targeted tests for the area you changed
python3 -m unittest backend.tests.<test_module> -v

# Security boundary regression test (required)
python3 -m unittest backend.tests.test_security_boundary_regression -v

# Full functional suite
make test

# Full suite including doc-guard tests
make test-all
```

If the full suite cannot run locally, state this clearly in the pull request.

---

## 6. Coding-Agent Contribution Rules

GrantLayer is designed to be especially attractive for AI/coding agents. If you are an agent or assisting an agent:

1. **Follow issue-specific allowed/forbidden files** — each issue defines what may and may not be changed. Do not exceed the scope.
2. **Do not change production code unless the issue explicitly allows it** — `backend/src/*` is off-limits unless the issue says otherwise.
3. **Do not stage `.claude/`** — the `.claude/` directory is ignored and must not be committed.
4. **Do not add internal URLs or paths** — use relative paths and public-safe placeholders only.
5. **Do not add real secrets or customer data** — all examples must use synthetic identifiers and placeholder tokens.
6. **Agent entry points:** `AGENTS.md`, `llms.txt`, and the agent integration manifest are the primary agent-facing files. Read them before starting work.

---

## 7. Security and Data Rules

- **No real secrets** — never commit API keys, Bearer tokens, JWTs, encryption keys, or passwords.
- **No real customer data** — never commit names, addresses, identifiers, or other personal/organizational data from real customers.
- All documentation and examples must use obviously fake placeholders (e.g. `demo-admin-token-gl146`, `gl146-demo-subject-001`).

---

## 8. DCO

DCO-style sign-off is **recommended** for public contributions:

```
Signed-off-by: Your Name <your.email@example.com>
```

This certifies that you have the right to submit the contribution under the Apache License 2.0. A CLA is **not required** at this time.

---

## 9. Pull Request Expectations

A good pull request includes:

1. **Summary** — what changed and why.
2. **Scope** — which files were changed and which were intentionally left untouched.
3. **Tests run** — which test commands were executed and their results.
4. **Caveats** — any known limitations, follow-up work, or items that could not be tested.

Keep pull requests small and focused. Large refactorings should be split into multiple issues and pull requests.

---

## 10. No Overclaims

All contributions must preserve the following messaging:

- Do **not** claim production SaaS readiness.
- Do **not** claim tenant isolation is implemented.
- Do **not** claim production readiness beyond the current developer-preview / controlled-pilot posture.
- Do **not** claim external adoption or real customer usage.

---

## 11. Next Steps

- [QUICKSTART.md](QUICKSTART.md) — get running in 5 minutes
- [Issues](https://github.com/discodone/grantlayer/issues) — browse open work or report bugs
- [SECURITY.md](SECURITY.md) — security policy and responsible disclosure
