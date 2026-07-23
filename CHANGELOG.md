# Changelog

All notable changes to GrantLayer are documented here.

**Versioning note:** The 0.x line is the authoritative version scheme for
GrantLayer, matching the Helm chart and the TypeScript SDK at 0.19.0. The
v1.x/v2.x git tags and the v1.1.0 GitHub release are historical artifacts
retained for provenance; they are not current versions.

---

## [Unreleased]

### Site hosting moved to GitHub Pages
- The static marketing/verify site under `site/` now publishes to GitHub Pages
  via the `pages.yml` Actions workflow (`upload-pages-artifact` + `deploy-pages`),
  custom domain `grantlayer.de`. There is no build step; `site/` is served as-is.
- The earlier MkDocs "Developer Portal" Pages deploy and its `gh-pages` branch
  were removed; the `gh-pages` branch has been deleted and nothing is served
  from it.

---

## [0.19.0] — 2026-06-18

### Developer Portal + API Documentation Site
- MkDocs Material site with dark theme (slate palette).
- Docs: index, getting-started, authentication, webhooks, sdk-python, sdk-js, self-hosting, contributing.
- `make docs` (build) and `make docs-serve` (local preview) targets.
- At the time, a GitHub Actions workflow deployed the MkDocs docs to a
  `gh-pages` branch on push to main. *(Superseded — see [Unreleased]: the
  MkDocs Pages deploy was removed and the `gh-pages` branch deleted; the static
  `site/` now publishes to GitHub Pages via `pages.yml`.)*

### Multi-Workspace Grant Templates
- `GrantTemplate` model: id, workspace_id, name, description, schema_json, default_values, version, parent_id, is_active, locked.
- CRUD: `/v1/grant-templates/` (list, create, get, deactivate, new-version).
- Templates immutable after first use; new-version creates incremented record with parent_id.
- `GET /v1/grant-templates/public` returns system-wide templates.
- Migration 0018; tests for CRUD, versioning, deactivation.

### OPA Policy Engine Integration
- OPA sidecar in docker-compose (openpolicyagent/opa:latest).
- `opa/policies/main.rego`: role-based grant approval, workspace_id match, API key scope enforcement.
- `policy/opa_client.py`: async `evaluate_policy()` + sync fallback; graceful degradation if OPA unreachable.
- `require_policy()` FastAPI dependency — raises 403 on deny.

### TypeScript/JavaScript SDK
- `sdk-js/` — TypeScript strict mode, ESM + CJS dual output.
- `GrantLayerClient` covering all endpoints: auth, grants, grant requests, audit, webhooks, API keys, workspaces, GDPR.
- Fetch-based (no axios), Node.js 18+ + browser compatible.
- Retry: 3 attempts, exponential backoff, 429 Retry-After awareness.
- Jest tests: mock fetch, assert correct endpoints called.

### Audit Log Compliance Export + Immutability Proof
- `GET /v1/audit/export` — streams NDJSON with SHA-256 chain hash per entry + HMAC manifest.
- `GET /v1/audit/verify` — verifies chain integrity, returns `{valid, checked, broken_at}`.
- `scripts/verify-audit.py` — offline CLI verifier (no network required).
- Tests: round-trip passes, tamper detection, empty export.

### Helm Chart + Kubernetes Manifests
- `deploy/helm/grantlayer/` — Chart.yaml, values.yaml, 7 templates (deployment-api, deployment-worker, service, ingress, configmap, hpa, pdb).
- PostgreSQL and Redis as external DSN (no subcharts).
- `deploy/k8s/` — raw manifests (namespace, secret, deployment).
- `deploy/README.md` — k3s quickstart.
- `make helm-lint` target.

### Performance Benchmarking Suite
- `backend/tests/performance/` with pytest benchmarks (marked `performance`).
- Scenarios: grant list, grant create, bulk-approve 100, audit log query.
- Baselines in `baselines.json`; p95 within 2x baseline regression detection.
- `make perf-test` target; excluded from normal `make test`.

### GDPR Compliance Tooling
- `POST /v1/users/{id}/export-data` — returns JSON archive of user data (async job_id).
- `POST /v1/users/{id}/erase` — anonymize PII, revoke tokens/API keys, audit entry.
- Self-erasure allowed; admin can erase any user; non-admin cannot erase others (403).

### Long-lived API Key Management
- `ApiKey` model: id, workspace_id, user_id, key_hash, name, scopes, expires_at, last_used_at, revoked_at.
- Key format: `gl_live_` + 32 random hex bytes; SHA-256 hashed, stored only as hash.
- CRUD: `POST /v1/api-keys` (returns raw key once), `GET /v1/api-keys`, `DELETE /v1/api-keys/{id}`.
- Audit events: `api_key_created`, `api_key_revoked`.
- Migration 0017.

### Tiered Rate Limiting Per-Workspace Plans
- `plan_tier` (free/pro/enterprise) + `rate_limit_override` columns on Workspace.
- Rate limits: free=100 req/min, pro=1000, enterprise=unlimited.
- `PATCH /v1/workspaces/{id}/plan` endpoint (admin only).
- `X-Plan-Tier` response header on all `/v1/` responses.
- Migration 0016.

### Redis Hard Requirement + API Rate Limiting
- Redis URL (`GRANTLAYER_REDIS_URL`) is now a hard requirement in staging/production modes.
- Rate limiting middleware applied to all `/v1/` endpoints (120 req/min per IP default).
- 429 responses include `errorCode: rate_limit_exceeded` and `Retry-After` header.
- CORS preflight (`OPTIONS`) requests bypass rate limiting.
- 20/20 new tests.

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
