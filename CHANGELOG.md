# Changelog

All notable changes to GrantLayer are documented here.

---

## [Unreleased] — v2.0.0 candidate

### GL-302: Test Coverage 95%+ *(in progress)*
- Expanding test coverage across service layer, repository pattern, and edge cases.

### GL-301: Service Layer
- Introduced `GrantService`, `GrantRequestService`, `OperatorService`.
- Business logic fully decoupled from routers.
- 36/36 new tests; ruff/mypy clean.

### GL-300: Repository Pattern
- `Protocol` interfaces + SQLAlchemy implementations in `core/repositories.py` / `core/repositories_sqlalchemy.py`.
- Four repository DI factories; domain model refactored.
- 0 ruff/mypy errors.

### GL-299: Operational Readiness
- Custom SQL parser (`_q_to_named`) removed; SQLAlchemy `text().bindparams()` throughout.
- Startup gate: application refuses to start with missing required config.
- Docker Compose production defaults hardened.
- JWT strict-claims documentation.
- Global 500 handler.

### GL-298: P0 Security Fixes
- Audit chain integrity hardening.
- JWT strict claims enforcement.

### GL-297: PostgreSQL Integration Tests CI
- Dedicated CI job runs the full functional suite against PostgreSQL 16.
- Test isolation: `uuid4()`-generated IDs per test; no hardcoded IDs.

### GL-296: Production Deployment Guide
- `DEPLOYMENT.md` with Docker Compose, nginx TLS, environment variables, and runbook.

### GL-295: JWT iss/aud Claims
- `sign_token` injects `iss`/`aud`; `validate_jwt_header` verifies them.
- Backward-compatible; 19/19 tests.

### GL-294: Complete SQLAlchemy ORM Migration
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
