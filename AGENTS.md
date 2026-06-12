# Contributing to GrantLayer

GrantLayer is a grant lifecycle management API — issue, verify, audit, and revoke
scoped access grants. This file is a quick orientation for new contributors.

---

## Getting Started

1. **[README.md](README.md)** — project overview and API reference
2. **[QUICKSTART.md](QUICKSTART.md)** — run the stack in 5 minutes
3. **[docs/architecture.md](docs/architecture.md)** — system design and data model
4. **[docs/openapi.yaml](docs/openapi.yaml)** — full OpenAPI spec (also at `/api/docs` when running)

---

## Local Setup

```bash
git clone https://github.com/discodone/grantlayer.git
cd grantlayer
cp .env.example .env          # edit .env: set GRANTLAYER_JWT_SECRET
./nginx/generate-certs.sh
docker compose up -d
curl http://localhost:8765/health
```

For running tests (from the repo root):

```bash
pip install -r requirements-dev.txt
scripts/run-functional-tests.sh   # fast, no network
scripts/run-full-backend-suite.sh # full suite
```

---

## How to Contribute

1. Fork the repository and create a feature branch.
2. Make your change with tests. The test suite must pass before opening a PR.
3. Open a pull request against `main`. Describe what changed and why.
4. Keep PRs focused — one logical change per PR.

Good starting points:

- Documentation improvements or typo fixes
- New test cases for edge conditions
- Example updates or clarifications

---

## Architecture Overview

| Layer | Location | Purpose |
|-------|----------|---------|
| HTTP API | `backend/src/api/routers/` | FastAPI route handlers |
| Business logic | `backend/src/` | Grant lifecycle, audit, auth |
| Database | SQLite (default) / PostgreSQL | Persistent storage |
| Auth | JWT (HS256) via `/v1/auth/token` | Stateless token auth |

Key concepts:

- **Grant** — a scoped, time-bounded access record for a subject
- **Grant Request** — a request/approval workflow that produces a Grant on approval
- **Audit Event** — an immutable log entry for every state change
- **Workspace** — a namespace for tenant isolation (developer preview)

---

## Reporting Bugs

1. Check [existing issues](https://github.com/discodone/grantlayer/issues) first.
2. Open a [new issue](https://github.com/discodone/grantlayer/issues/new) with:
   - Exact command you ran
   - Expected outcome
   - Actual outcome (error message, status code)
   - OS, Docker version, Python version

---

## Reporting Security Issues

Use [GitHub Security Advisories](https://github.com/discodone/grantlayer/security/advisories/new).
Do **not** open a public issue for vulnerabilities.

See [SECURITY.md](SECURITY.md) for the full security policy.

---

## Code Rules

- **No real secrets** — never commit API keys, tokens, or passwords. All examples use placeholder values.
- **No real customer data** — never commit real names, addresses, or identifiers. Use synthetic data in tests and examples.
- **No production overclaims** — tenant/workspace isolation is not production-complete. Do not represent this as production SaaS.
