# Changelog

All notable changes to GrantLayer are documented here.

---

## [Unreleased] — v2.0.0 candidate

### Redis Hard Requirement + API Rate Limiting
- Redis URL (`GRANTLAYER_REDIS_URL`) is now a hard requirement in staging/production modes.
- Rate limiting middleware applied to all `/v1/` endpoints (120 req/min per IP default).
- 429 responses include `errorCode: rate_limit_exceeded` and `Retry-After` header.
- CORS preflight (`OPTIONS`) requests bypass rate limiting.
- 20/20 new tests.

### Test Coverage 95%+
- Expanded test coverage across service layer, repository pattern, and edge cases.

### Service Layer
- Introduced `GrantService`, `GrantRequestService`, `OperatorService`.
- Business logic fully decoupled from routers.
- 36/36 new tests; ruff/mypy clean.

### Repository Pattern
- `Protocol` interfaces + SQLAlchemy implementations in `core/repositories.py` / `core/repositories_sqlalchemy.py`.
- Four repository DI factories; domain model refactored.
- 0 ruff/mypy errors.

### Operational Readiness
- Custom SQL parser (`_q_to_named`) removed; SQLAlchemy `text().bindparams()` throughout.
- Startup gate: application refuses to start with missing required config.
- Docker Compose production defaults hardened.
- JWT strict-claims documentation.
- Global 500 handler.

### P0 Security Fixes
- Audit chain integrity hardening.
- JWT strict claims enforcement.

### PostgreSQL Integration Tests CI
- Dedicated CI job runs the full functional suite against PostgreSQL 16.
- Test isolation: `uuid4()`-generated IDs per test; no hardcoded IDs.

### Production Deployment Guide
- `DEPLOYMENT.md` with Docker Compose, nginx TLS, environment variables, and runbook.

### JWT iss/aud Claims
- `sign_token` injects `iss`/`aud`; `validate_jwt_header` verifies them.
- Backward-compatible; 19/19 tests.

### Complete SQLAlchemy ORM Migration
- All remaining raw SQL removed.
- Full ORM coverage: Grant, GrantRequest, GrantExecution, Operator.

---

## [1.2.0] — CI Stability + Prometheus Metrics

- CI stability improvements across parallel test runs.
- Prometheus metrics endpoint added.
- ruff/mypy baseline established (0 errors).

---

## [1.1.0] — SQLAlchemy ORM + Redis Rate Limiter + Coverage 91%

- SQLAlchemy ORM session (`get_db()` dependency) replacing raw DB calls.
- Redis sliding-window rate limiter (`RedisRateLimiter`) with in-process fallback.
- `GRANTLAYER_REDIS_URL` environment variable.
- `/health` Redis field.
- Test coverage raised to 91%.

---

## [1.0.0] — PyJWT + Workspace Isolation + Pagination

- PyJWT `>=2.8.0` replaces custom HMAC/RSA implementation.
- RS256 default authentication; HS256 legacy path.
- Workspace isolation enforced at API level: every request resolves a workspace from operator identity.
- Cursor-based pagination foundation.
- Public GitHub repository published.
