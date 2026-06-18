# GrantLayer — Architecture

## Overview

GrantLayer is an async FastAPI application providing grant lifecycle management,
multi-tenant workspace isolation, and policy-driven access control.

```
HTTP Client
    │
    ▼
FastAPI ASGI (uvicorn)
    │  Rate-limit middleware (Redis sliding window)
    │  Correlation-ID middleware
    │  JWT / API-key authentication (per-route Depends)
    ▼
Router layer  (backend/src/api/routers/)
    │  Input validation (Pydantic schemas)
    │  Workspace context resolution
    │  OPA policy check (optional, fail-closed)
    ▼
Service layer (backend/src/*/service.py)
    │  Business logic — grants, grant-requests, operators, etc.
    │  Audit event emission
    ▼
Repository layer (backend/src/core/repositories*.py)
    │  SQLAlchemy async sessions
    │  ORM queries — no handwritten SQL (see exceptions below)
    ▼
Database (SQLite for dev/test · PostgreSQL 16 for production)
```

---

## Layer responsibilities

### Router (`backend/src/api/routers/`)

Each domain has its own router module (e.g., `grants.py`, `grant_requests.py`,
`webhooks.py`). Routers:

- Accept and validate HTTP requests via Pydantic schemas.
- Authenticate callers through `resolve_auth_and_workspace()` (a synchronous
  helper that validates JWTs, API keys, and admin tokens, then resolves the
  `tenant_id`/`workspace_id` from the token payload or request headers).
- Enforce write-scope on API keys (`enforce_api_key_write_scope`).
- Optionally call the OPA policy engine before mutating state.
- Delegate business logic to the service layer; never touch the DB directly.

### Service layer (`backend/src/*/service.py`)

- `AsyncGrantService` — grant CRUD, expiry, use-count enforcement.
- `AsyncGrantRequestService` — approval/denial workflow, state-machine transitions.
- `OperatorService` — operator record management.
- `WebhookService` — webhook fan-out, delivery with exponential backoff, SSRF guard.

Services own the audit trail: every mutating action emits a structured audit
event (row-hash chained for tamper evidence).

### Repository layer (`backend/src/core/repositories*.py`)

Two implementations behind a common Protocol:

| Module | Engine |
|--------|--------|
| `repositories.py` | In-memory (for unit tests) |
| `repositories_sqlalchemy.py` | SQLAlchemy `AsyncSession` |

Repositories are injected as FastAPI dependencies via factory functions
(`get_async_grant_service`, etc.).

### ORM models (`backend/src/core/orm.py`)

Twelve SQLAlchemy ORM classes: `Grant`, `GrantRequest`, `GrantExecution`,
`Operator`, `AuditEvent`, `Workspace`, `WorkspaceMember`, `ApiKey`, `Webhook`,
`WebhookDelivery`, `Challenge`, `AuditSeq`.

Schema migrations are managed by Alembic (`alembic/`).

---

## Auth and multi-tenancy

### Authentication

Three credential types are supported simultaneously:

| Type | Where validated | Typical callers |
|------|----------------|-----------------|
| RS256/HS256 JWT | `validate_jwt_header()` | Operators, agents |
| API key (HMAC-SHA256 prefix) | `validate_api_key()` | M2M integrations |
| Admin token | `validate_admin_token()` | Bootstrap / internal tooling |

`JWT_STRICT_CLAIMS=true` (the default) rejects tokens missing `iss` or `aud`.

### Workspace isolation

Every data-access call carries `tenant_id` and `workspace_id`. Both values
come from the authenticated token — never from user-supplied request parameters.
`resolve_auth_and_workspace()` enforces membership checks before any query runs.

---

## Policy engine (OPA)

When `GRANTLAYER_OPA_URL` is set, the `evaluate_policy` / `evaluate_policy_sync`
helpers POST to OPA's `/v1/data/grantlayer/allow` endpoint. On error (OPA
unreachable or misconfigured) the helpers **raise `HTTPException(503)`**
rather than defaulting to allow. This is the fail-closed posture.

---

## Rate limiting

A Redis-backed sliding-window rate limiter (`backend/src/api/rate_limit.py`)
applies per-IP limits. Client IP is extracted from `X-Forwarded-For` (first
hop) with a fallback to the direct TCP peer. The `plan_tier` claim in the JWT
payload selects among `free`, `pro`, and `enterprise` bucket sizes.

The `/v1/auth/token` endpoint has a tighter per-IP limit (10 req/min) to
throttle credential stuffing.

---

## Webhook delivery

Webhooks are delivered by `WebhookService._deliver_with_retry`:

1. SSRF guard — blocks private and loopback IPs using `socket.getaddrinfo` +
   `ipaddress`; unresolvable hosts are allowed (delivery fails naturally).
2. HMAC-SHA256 payload signature added as `X-GrantLayer-Signature`.
3. Up to 3 retries with exponential back-off (`asyncio.sleep`).
4. Every attempt (success or failure) is recorded in `WebhookDelivery`.

---

## Startup gate

In production-like modes (`GRANTLAYER_RUNTIME_MODE=production`), the FastAPI
lifespan context calls `config.startup_errors()` at boot. If any required
configuration is absent or invalid the process exits immediately rather than
serving 500s at request time.

The `/readiness` probe checks database connectivity with `SELECT 1` and Redis
availability; it returns `503` when either is unavailable.

---

## Database conventions

**Standard path:** SQLAlchemy ORM or `session.execute(text(…).bindparams(…))`.

**Known exceptions using raw `text()` SQL:**

| File | Reason |
|------|--------|
| `audit/audit_log.py` | Audit hash-chain insert uses parameterised `text()` to guarantee column ordering across SQLite and PostgreSQL |
| `api/routers/api_keys.py` | API-key lookup/revoke/last-used-update using `conn.execute(text(…))` through the legacy `_ConnectionWrapper` shim |
| `core/db.py` | `_ConnectionWrapper` compatibility layer that translates `?`-style placeholders to named params for both engines |

These are **parameterised queries** — no string interpolation into SQL. The
CLAUDE.md guideline "no raw SQL" means no ad-hoc string interpolation, not
that `text()` is banned.

---

## Directory map

```
backend/
  src/
    api/
      app.py              FastAPI factory + lifespan + middleware
      deps.py             Shared FastAPI Depends helpers (auth, workspace, services)
      auth_jwt.py         JWT encode/decode, validate_jwt_header()
      rate_limit.py       Redis sliding-window rate limiter
      schemas.py          Pydantic request/response models
      routers/            One module per domain (grants, grant_requests, …)
    audit/                Audit log + hash-chain + export
    core/
      config.py           Environment-driven configuration
      db.py               DB engine factory + _ConnectionWrapper shim
      models.py           Domain dataclasses
      orm.py              SQLAlchemy ORM classes
      repositories*.py    Repository Protocol + SA implementation
    grants/               Grant service + grant-request service
    operators/            Operator service
    policy/               OPA client + compliance helpers
    webhooks/             Webhook service, schemas, repository, router
  tests/                  pytest test suite (~4500 functional tests)
docs/
  openapi.yaml            OpenAPI 3.0 specification
sdk/
  grantlayer/             Python client SDK (canonical, pip-installable package)
```
