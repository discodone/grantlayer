# Contributing

## Development Setup

```bash
git clone https://github.com/discodone/grantlayer
cd grantlayer
make install
```

## Running Tests

```bash
# Functional tests (fast, ~3400 tests)
make test

# Full test suite including doc-guard tests
make test-all

# Performance benchmarks
make perf-test

# Lint + type checking
make lint
```

## Code Standards

- **Python**: ruff (linting + formatting), mypy (type checking)
- **TypeScript**: strict mode, no implicit any
- No raw SQL — use SQLAlchemy ORM
- Repository + Service layer pattern
- Test coverage ≥ 95%

## Submitting Changes

1. Create a branch: `git checkout -b gl-NNN-description`
2. Make your changes
3. Run: `make lint && make test`
4. Commit: `git commit -m "feat(GL-NNN): description"`
5. Push and open a PR

## Architecture

- `backend/src/api/` — FastAPI routers and dependencies
- `backend/src/core/` — ORM models, rate limiter, DB
- `backend/src/auth/` — JWT and OIDC authentication
- `backend/src/audit/` — Audit log with hash chain
- `backend/src/policy/` — OPA policy client
- `backend/src/workers/` — ARQ background jobs
- `sdk-js/` — TypeScript SDK
- `deploy/` — Helm chart and K8s manifests
