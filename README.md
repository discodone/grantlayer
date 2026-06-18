# GrantLayer

[![PostgreSQL CI](https://github.com/Discodone/grantlayer/actions/workflows/postgres-ci.yml/badge.svg)](https://github.com/Discodone/grantlayer/actions/workflows/postgres-ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-91%25%2B-brightgreen)](https://github.com/Discodone/grantlayer)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

GrantLayer is a verification, audit, and compliance layer for agentic grant and funding workflows. When AI agents prepare funding applications, evaluate eligibility, or trigger approval decisions, GrantLayer makes every step traceable, tamper-evident, and independently auditable. It is in **Developer Preview** — local evaluation and controlled pilot only. It is not production SaaS; production SaaS readiness is not claimed. No GitHub push and no repository visibility change are part of this local quickstart.

---

## Status

| Area | Status |
|------|--------|
| Production SaaS readiness | Not claimed |
| Tenant/workspace isolation | Enforced at API level — workspace-scoped queries, cross-workspace denial |
| Public GitHub release | Available |
| Real customer data in examples | None; examples use synthetic/demo data only |
| Real secrets in examples | None; use placeholders or generated local values only |

Production SaaS readiness is not claimed.
Tenant/workspace isolation is enforced at the API level: every request resolves a workspace_id and tenant_id from the operator identity; queries are server-side scoped to that workspace and tenant; cross-workspace access is denied by default. This provides strong isolation for developer preview and controlled pilot deployments.
Examples use no real secrets and no real customer data.

---

## Quickstart

### Choose your path

- **Path A:** run the first verifiable output quickstart below. It requires no backend and uses Python stdlib only.
- **Path B:** run the backend quickstart with Docker Compose or local Python setup.

Get the stack running in under 5 minutes:

```bash
git clone https://github.com/Discodone/grantlayer.git
cd grantlayer
cp .env.example .env          # set GRANTLAYER_JWT_SECRET
./nginx/generate-certs.sh     # self-signed TLS for local dev
docker compose up -d
curl -k https://localhost/health
```

See [QUICKSTART.md](QUICKSTART.md) for the full walkthrough: token generation, creating grants, grant requests, and audit log export.

See [CHANGELOG.md](CHANGELOG.md) for public snapshot version anchors and caveats.

### First Verifiable Output Quickstart

Run the first verifiable output quickstart:

```bash
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
```

The generated file is `/tmp/grantlayer_first_output.json`. The committed deterministic reference output is `examples/first_verifiable_output.json`; see `docs/first_verifiable_output.md`.

This path is local/demo only, requires no real secrets, requires no customer data, uses no real secrets, and uses no real customer data.

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/v1/grants` | List all grants |
| `POST` | `/v1/grants` | Create a grant |
| `POST` | `/v1/grants/:id/revoke` | Revoke a grant |
| `GET` | `/v1/grant-requests` | List grant requests |
| `POST` | `/v1/grant-requests` | Submit a grant request (requires `GRANTLAYER_ENABLE_OPERATOR_MODEL=true`) |
| `POST` | `/v1/grant-requests/:id/approve` | Approve a grant request |
| `POST` | `/v1/grant-requests/:id/deny` | Deny a grant request |
| `GET` | `/v1/audit-events` | List audit events |
| `GET` | `/v1/grant-executions` | List grant executions (owner/v1/admin/v1/auditor) |

Full OpenAPI spec: `docs/openapi.yaml`. Interactive Swagger UI available at `/api/docs` when the stack is running.

---

## Architecture

GrantLayer is a Python/FastAPI backend with SQLite (default) or PostgreSQL storage, served behind an Nginx TLS reverse proxy. All grants are signed with Ed25519 and form a tamper-evident audit chain — each event records what was decided, by whom, and when. The operator model provides a request/approval workflow: subjects submit grant requests, and operators approve or deny them. JWT authentication (HS256) guards all API endpoints; tokens encode the caller's subject, tenant, role, and expiry. Docker Compose brings up the API, Nginx, and optionally PostgreSQL as a single `docker compose up` command.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_JWT_SECRET` | *(required)* | HS256 signing secret for JWT tokens |
| `GRANTLAYER_ENABLE_OPERATOR_MODEL` | `true` | Enable the grant request / approval workflow |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | Enable demo tamper endpoints (never in production) |
| `GRANTLAYER_DATABASE_URL` | *(empty = SQLite)* | PostgreSQL URL when using the `postgres` profile |
| `GRANTLAYER_HOST` | `0.0.0.0` | Bind address |
| `GRANTLAYER_PORT` | `8765` | HTTP port (inside container) |

Copy `.env.example` to `.env` and set at minimum `GRANTLAYER_JWT_SECRET`.

---

## Running locally without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GRANTLAYER_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
python3 -m backend
```

This starts the same FastAPI/uvicorn server as `docker compose up`. Backend starts at `http://127.0.0.1:8765`.

Equivalent direct invocation:

```bash
uvicorn backend.src.api.app:app --port 8765
```

---

## Tests

```bash
python3 -m unittest discover -s backend/tests -v
```

Or via script: `./scripts/test.sh`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding guidelines, test expectations, and the DCO recommendation. Security reports go to [SECURITY.md](SECURITY.md).

No mature public contribution process is claimed yet — this is a developer preview.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
