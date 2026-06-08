# GrantLayer

GrantLayer is a verification, audit, and compliance layer for agentic grant and funding workflows. When AI agents prepare funding applications, evaluate eligibility, or trigger approval decisions, GrantLayer makes every step traceable, tamper-evident, and independently auditable. It is in **Developer Preview** — designed for local evaluation and controlled pilots.

---

## Quickstart

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

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/grants` | List all grants |
| `POST` | `/grants` | Create a grant |
| `POST` | `/grants/:id/revoke` | Revoke a grant |
| `GET` | `/grant-requests` | List grant requests |
| `POST` | `/grant-requests` | Submit a grant request (requires `GRANTLAYER_ENABLE_OPERATOR_MODEL=true`) |
| `POST` | `/grant-requests/:id/approve` | Approve a grant request |
| `POST` | `/grant-requests/:id/deny` | Deny a grant request |
| `GET` | `/audit-events` | List audit events |
| `GET` | `/grant-executions` | List grant executions (owner/admin/auditor) |

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

Backend starts at `http://127.0.0.1:8765`.

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
