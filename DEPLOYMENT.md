# GrantLayer — Production Deployment Guide

This guide covers deploying GrantLayer in a production environment using Docker Compose with PostgreSQL and Nginx TLS termination.

> **Status:** Developer preview. Suitable for controlled environments. Review the [Production Readiness Notes](#production-readiness-notes) section before exposing to the public internet.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment Variables](#2-environment-variables)
3. [Docker Compose Setup](#3-docker-compose-setup)
4. [Nginx TLS Configuration](#4-nginx-tls-configuration)
5. [First Start and Bootstrap Operator](#5-first-start-and-bootstrap-operator)
6. [JWT Claims: Issuer and Audience](#6-jwt-claims-issuer-and-audience)
7. [RS256 Key Pair Generation](#7-rs256-key-pair-generation)
8. [Backup Strategy](#8-backup-strategy)
9. [Monitoring](#9-monitoring)
10. [Upgrade Process](#10-upgrade-process)
11. [Troubleshooting](#11-troubleshooting)
12. [CI — PostgreSQL Integration Tests](#12-ci--postgresql-integration-tests)
13. [Production Readiness Notes](#production-readiness-notes)

---

## 1. Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Docker | 24.x | Engine + CLI |
| Docker Compose | 2.20+ | `docker compose` (v2, not `docker-compose`) |
| PostgreSQL | 16 | Included in `docker-compose.yml`; external DB also supported |
| Python | 3.11+ | Only needed if running outside Docker |
| openssl | any | For key generation and self-signed certs |
| curl | any | Used in health check scripts |

**Server sizing (minimum):**
- 1 vCPU, 512 MB RAM for the API container
- 10 GB disk for PostgreSQL data and logs

---

## 2. Environment Variables

All settings are read from environment variables at startup. There are no config files — use a `.env` file with Docker Compose (see section 3).

### Runtime

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_RUNTIME_MODE` | `local` | Runtime mode. Must be `production` or `staging` for prod. Accepted: `local`, `test`, `demo`, `staging`, `production`. |
| `GRANTLAYER_HOST` | `127.0.0.1` | Bind address for the Uvicorn server. Set to `0.0.0.0` inside Docker. |
| `GRANTLAYER_PORT` | `8765` | TCP port the API listens on. |
| `GRANTLAYER_LOG_LEVEL` | `INFO` | Log verbosity. Accepted: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` | `2000` | Timeout in ms for DB connectivity check at `/health`. |

### Database

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_DATABASE_URL` | _(empty)_ | Full SQLAlchemy connection URL. PostgreSQL example: `postgresql://user:pass@host:5432/dbname`. Takes precedence over `GRANTLAYER_DB`. |
| `GRANTLAYER_DB` | _(empty)_ | Path to a SQLite database file. Only used when `GRANTLAYER_DATABASE_URL` is not set. |
| `GRANTLAYER_POSTGRES_USER` | `grantlayer` | PostgreSQL username (Docker Compose only). |
| `GRANTLAYER_POSTGRES_PASSWORD` | _(required)_ | PostgreSQL password (Docker Compose only). Must be set in `.env`. |
| `GRANTLAYER_POSTGRES_DB` | `grantlayer` | PostgreSQL database name (Docker Compose only). |

**Production rule:** Always set `GRANTLAYER_DATABASE_URL` explicitly. Do not rely on SQLite in production.

### Authentication — Admin Token

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_ADMIN_TOKEN` | _(empty)_ | Static bearer token for legacy admin access. Required in production-like modes (min. 16 chars, no placeholder values). |
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | `true` ¹ | When `true`, all protected endpoints reject requests without a valid admin token. |

¹ Defaults to `true` when `GRANTLAYER_RUNTIME_MODE` is not `local` or `test`.

### Authentication — Operator Model

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_ENABLE_OPERATOR_MODEL` | `true` | Enable the operator identity model (hashed bearer tokens with roles). Recommended for production. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN` | _(empty)_ | One-time bootstrap token to create the first operator on a fresh database. Leave unset in production after initial setup. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_ID` | `bootstrap-admin` | ID assigned to the bootstrap operator. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_NAME` | `Bootstrap Admin` | Display name of the bootstrap operator. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE` | `owner` | Role assigned to the bootstrap operator. |

### Authentication — JWT

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_JWT_ALGORITHM` | `RS256` | Signing algorithm. `RS256` (recommended) or `HS256` (legacy). |
| `GRANTLAYER_JWT_PRIVATE_KEY` | _(empty)_ | Base64-encoded RS256 private key PEM. Required for token issuance (`/v1/auth/token`). |
| `GRANTLAYER_JWT_PUBLIC_KEY` | _(empty)_ | Base64-encoded RS256 public key PEM. Required for token verification. |
| `GRANTLAYER_JWT_SECRET` | _(empty)_ | HMAC secret for HS256 tokens. Only used when `GRANTLAYER_JWT_ALGORITHM=HS256`. |
| `GRANTLAYER_JWT_ISSUER` | `grantlayer` | `iss` claim added to every issued JWT. Tokens with a mismatched `iss` are rejected. Set to `""` to disable. |
| `GRANTLAYER_JWT_AUDIENCE` | `grantlayer-api` | `aud` claim added to every issued JWT. Tokens with a mismatched `aud` are rejected. Set to `""` to disable. |
| `GRANTLAYER_JWT_STRICT_CLAIMS` | `false` | **Recommended: `true` for production.** When `true`, tokens without `iss` or `aud` claims are rejected outright. When `false` (default), tokens without these claims are accepted for backward compatibility. |

**Backward compatibility:** Tokens issued before `GRANTLAYER_JWT_ISSUER`/`GRANTLAYER_JWT_AUDIENCE` were configured (i.e., tokens without `iss`/`aud` claims) continue to be accepted when `GRANTLAYER_JWT_STRICT_CLAIMS=false`. Set `GRANTLAYER_JWT_STRICT_CLAIMS=true` to require these claims on all tokens in production.

### Signing Key (Audit Chain)

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_SIGNING_PRIVATE_KEY` | _(empty)_ | PEM-encoded private key as a string. Takes precedence over file-based loading. |
| `GRANTLAYER_SIGNING_PRIVATE_KEY_FILE` | _(empty)_ | Path to a PEM private key file. Only used when the string variable is not set. |
| `GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE` | _(empty)_ | Passphrase for an encrypted private key file. |
| `GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE` | `false` ² | Allow loading an unencrypted key file. `false` in staging/production modes. |

² Defaults to `true` in `local` and `test` modes only.

### CORS

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:8765,http://localhost:8765` | Comma-separated list of allowed CORS origins. Exact match only — no wildcards. Set to your actual frontend origin(s) or leave empty to disable CORS. |

### Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_RATE_LIMIT_AUTH` | `10` | Max requests per minute per IP for `/v1/auth/token`. |
| `GRANTLAYER_RATE_LIMIT_API` | `120` | Max requests per minute per IP for all other API endpoints. |
| `GRANTLAYER_REDIS_URL` | _(empty)_ | Redis connection URL (e.g. `redis://redis:6379/0`). When unset, an in-process sliding-window fallback is used (not shared across multiple replicas). |

### Demo / Safety Flags

| Variable | Default | Description |
|---|---|---|
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | Expose demo-only tamper endpoints. Must be `false` in production. |
| `GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS` | `false` | Required acknowledgement when demo endpoints are enabled on a non-loopback host. |
| `GRANTLAYER_REQUIRE_CHALLENGE` | `false` | Require a `challengeId` on `POST /demo-action`. Must be `true` in production-like modes. |

---

## 3. Docker Compose Setup

### Create the `.env` file

Copy and fill in all required secrets:

```bash
cp .env.example .env   # if available, otherwise create manually
```

Minimum `.env` for production:

```dotenv
# Runtime
GRANTLAYER_RUNTIME_MODE=production

# Database
GRANTLAYER_POSTGRES_USER=grantlayer
GRANTLAYER_POSTGRES_PASSWORD=<strong-random-password>
GRANTLAYER_POSTGRES_DB=grantlayer
GRANTLAYER_DATABASE_URL=postgresql://grantlayer:<strong-random-password>@db:5432/grantlayer

# Admin token (min 16 chars, no placeholder values)
GRANTLAYER_ADMIN_TOKEN=<strong-random-token>
GRANTLAYER_REQUIRE_ADMIN_TOKEN=true
GRANTLAYER_REQUIRE_CHALLENGE=true

# Operator model
GRANTLAYER_ENABLE_OPERATOR_MODEL=true
GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN=<strong-random-token>   # remove after first start

# JWT (RS256 — see section 7)
GRANTLAYER_JWT_ALGORITHM=RS256
GRANTLAYER_JWT_PRIVATE_KEY=<base64-encoded-private-key-pem>
GRANTLAYER_JWT_PUBLIC_KEY=<base64-encoded-public-key-pem>
GRANTLAYER_JWT_ISSUER=grantlayer
GRANTLAYER_JWT_AUDIENCE=grantlayer-api
GRANTLAYER_JWT_STRICT_CLAIMS=true    # reject tokens without iss/aud (recommended)

# CORS (set to your actual frontend origin)
GRANTLAYER_CORS_ALLOWED_ORIGINS=https://app.example.com
```

### Start the stack

```bash
# Generate a self-signed TLS cert for local testing
# (Skip this in production — see section 4 for real certs)
./nginx/generate-certs.sh

# Build and start all services
docker compose up -d

# Verify all containers are running
docker compose ps

# Tail logs
docker compose logs -f api
```

### Verify health

```bash
# Through Nginx (HTTPS)
curl -k https://localhost/health

# Direct to API (HTTP)
curl http://localhost:8765/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "grantlayer",
  "version": "0.4.0",
  "database": "ok",
  "signing_key": "present",
  "migrations": "<rev> (head)",
  "redis": "disabled"
}
```

---

## 4. Nginx TLS Configuration

### Self-signed certificate (development / staging)

```bash
./nginx/generate-certs.sh
# Writes: nginx/certs/tls.crt  nginx/certs/tls.key
```

The generated cert is valid for 365 days and covers `localhost` + `127.0.0.1`.

### Let's Encrypt with Certbot (production)

On the host machine (not inside Docker):

```bash
# Install certbot
sudo apt install certbot

# Obtain certificate (standalone mode — stop nginx first)
docker compose stop nginx
sudo certbot certonly --standalone -d api.example.com

# Copy certs to nginx/certs/
sudo cp /etc/letsencrypt/live/api.example.com/fullchain.pem nginx/certs/tls.crt
sudo cp /etc/letsencrypt/live/api.example.com/privkey.pem   nginx/certs/tls.key
sudo chown $(whoami):$(whoami) nginx/certs/tls.*

docker compose start nginx
```

Update `nginx/nginx.conf` to use your real domain:

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;   # ← replace with your domain

    ssl_certificate     /etc/nginx/certs/tls.crt;
    ssl_certificate_key /etc/nginx/certs/tls.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ...
}
```

### Certificate renewal (cron)

```bash
# Add to root crontab: renew + reload nginx
0 3 * * * certbot renew --quiet && \
  cp /etc/letsencrypt/live/api.example.com/fullchain.pem /path/to/grantlayer/nginx/certs/tls.crt && \
  cp /etc/letsencrypt/live/api.example.com/privkey.pem   /path/to/grantlayer/nginx/certs/tls.key && \
  docker exec grantlayer-nginx nginx -s reload
```

---

## 5. First Start and Bootstrap Operator

On a fresh database, GrantLayer automatically creates one operator when `GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN` is set.

### Step-by-step

```bash
# 1. Set the bootstrap token in .env (strong, unique, min 16 chars)
echo "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN=$(openssl rand -hex 32)" >> .env

# 2. Start the stack — the bootstrap operator is created on first DB connection
docker compose up -d

# 3. Verify the bootstrap operator was created
curl -s http://localhost:8765/v1/operators/me \
  -H "Authorization: Bearer $(grep GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN .env | cut -d= -f2)" \
  | jq .

# 4. Exchange bootstrap token for a JWT
curl -s -X POST http://localhost:8765/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"operator_id": "bootstrap-admin", "secret": "<bootstrap-token>"}' \
  | jq .access_token

# 5. Remove GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN from .env after initial setup
#    The operator row remains in the database; removing the env var only disables
#    automatic re-creation on empty tables.
```

### Create additional operators

Using the bootstrap JWT:

```bash
JWT="<token-from-step-4>"

curl -s -X POST http://localhost:8765/v1/operators \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Admin Operator",
    "role": "owner",
    "tenant_id": "your-tenant"
  }' | jq .
```

---

## 6. JWT Claims: Issuer and Audience

GrantLayer adds `iss` (issuer) and `aud` (audience) claims to every JWT it issues. These claims allow consumers to verify token provenance and prevent tokens intended for one service from being accepted by another.

### Configuration

```dotenv
GRANTLAYER_JWT_ISSUER=grantlayer        # value of the "iss" claim
GRANTLAYER_JWT_AUDIENCE=grantlayer-api  # value of the "aud" claim
```

**Validation behavior:**

- Tokens that carry an `iss` claim are validated: if `iss ≠ GRANTLAYER_JWT_ISSUER`, the request is rejected with `401 jwt_invalid`.
- Tokens without an `iss` claim are accepted (backward compatibility with tokens issued before this feature was added).
- The same logic applies to `aud`.
- Setting either variable to `""` disables both injection and validation for that claim.

### Customizing for multi-tenant deployments

If you run multiple GrantLayer instances (e.g. per-region), use distinct issuer values:

```dotenv
GRANTLAYER_JWT_ISSUER=grantlayer-eu-west
GRANTLAYER_JWT_AUDIENCE=grantlayer-api
```

This prevents tokens from one region being replayed against another.

---

## 7. RS256 Key Pair Generation

RS256 is the default and recommended JWT algorithm. The private key signs tokens; the public key verifies them.

### Generate a key pair

```bash
# Generate 2048-bit RSA private key
openssl genrsa -out private.pem 2048

# Extract the public key
openssl rsa -in private.pem -pubout -out public.pem

# Base64-encode both (single line, no line breaks)
export GRANTLAYER_JWT_PRIVATE_KEY=$(base64 -w0 private.pem)
export GRANTLAYER_JWT_PUBLIC_KEY=$(base64 -w0 public.pem)

# Add to .env
echo "GRANTLAYER_JWT_PRIVATE_KEY=${GRANTLAYER_JWT_PRIVATE_KEY}" >> .env
echo "GRANTLAYER_JWT_PUBLIC_KEY=${GRANTLAYER_JWT_PUBLIC_KEY}"   >> .env

# Delete plaintext key files from disk
rm -f private.pem public.pem
```

> **Security:** The private key must never be committed to version control. Store it in a secrets manager (Vault, AWS Secrets Manager, Docker Secrets) and inject it at runtime via the environment variable.

### Key rotation

1. Generate a new key pair (steps above).
2. Update `GRANTLAYER_JWT_PRIVATE_KEY` and `GRANTLAYER_JWT_PUBLIC_KEY` in `.env`.
3. Rolling-restart the API:
   ```bash
   docker compose up -d --no-deps api
   ```
4. Previously issued tokens (signed with the old key) will fail verification immediately after the restart. Plan a maintenance window or implement a grace period by keeping the old public key available for a transition period.

### HS256 (legacy, not recommended for production)

If RS256 is not feasible, HS256 can be used with a strong secret:

```bash
export GRANTLAYER_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "GRANTLAYER_JWT_ALGORITHM=HS256"                   >> .env
echo "GRANTLAYER_JWT_SECRET=${GRANTLAYER_JWT_SECRET}"   >> .env
```

Minimum secret length: 32 bytes (64 hex characters). Rotate regularly.

---

## 8. Backup Strategy

### PostgreSQL (recommended for production)

**Daily backup with `pg_dump`:**

```bash
#!/usr/bin/env bash
# /etc/cron.daily/grantlayer-backup

BACKUP_DIR=/var/backups/grantlayer
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER=grantlayer-postgres

mkdir -p "$BACKUP_DIR"

docker exec "$CONTAINER" \
  pg_dump -U grantlayer -d grantlayer -Fc \
  > "$BACKUP_DIR/grantlayer_${TIMESTAMP}.dump"

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.dump" -mtime +30 -delete
```

Make executable and register:

```bash
chmod +x /etc/cron.daily/grantlayer-backup
```

**Restore from backup:**

```bash
docker exec -i grantlayer-postgres \
  pg_restore -U grantlayer -d grantlayer -c \
  < /var/backups/grantlayer/grantlayer_<timestamp>.dump
```

### Backup schedule

| Type | Frequency | Retention |
|---|---|---|
| Full `pg_dump` | Daily | 30 days |
| Transaction log archiving (WAL) | Continuous | 7 days |
| Pre-upgrade snapshot | Before every upgrade | Manual cleanup |

### Docker volume backup (alternative)

```bash
# Stop services to ensure consistency
docker compose stop api

# Backup PostgreSQL data volume
docker run --rm \
  -v grantlayer_grantlayer-postgres-data:/data:ro \
  -v /var/backups/grantlayer:/backup \
  alpine tar czf /backup/postgres-volume-$(date +%Y%m%d).tar.gz -C /data .

docker compose start api
```

### Off-site replication

Copy backups to an off-site location (S3, rclone remote, etc.):

```bash
aws s3 sync /var/backups/grantlayer s3://your-bucket/grantlayer-backups/ --storage-class STANDARD_IA
# or
rclone sync /var/backups/grantlayer remote:grantlayer-backups
```

---

## 9. Monitoring

### Health endpoint

`GET /health` — liveness check, returns `200 OK` when the service is up.

```bash
curl -s http://localhost:8765/health | jq .
```

```json
{
  "status": "ok",
  "service": "grantlayer",
  "checkType": "liveness",
  "version": "0.4.0",
  "uptime_seconds": 3600,
  "database": "ok",
  "signing_key": "present",
  "migrations": "abc123 (head)",
  "redis": "disabled"
}
```

| Field | Values | Meaning |
|---|---|---|
| `status` | `ok` / `degraded` | Overall health |
| `database` | `ok` / `error: …` | DB connectivity |
| `signing_key` | `present` / `absent` | JWT key is configured |
| `migrations` | `<rev> (head)` / `<rev>` | Whether migrations are up to date |
| `redis` | `ok` / `error` / `disabled` | Redis rate-limiter status |

### Readiness endpoint

`GET /readiness` — readiness check, returns `200 OK` when the service is ready to accept traffic, `503` when misconfigured.

```bash
curl -s http://localhost:8765/readiness | jq .
```

### Prometheus / metrics

GrantLayer does not currently expose a Prometheus `/metrics` endpoint. Use external monitoring:

- **Docker health check:** Docker itself polls `/health` every 30s (see `docker-compose.yml`).
- **Uptime monitoring:** Point an external uptime monitor (UptimeRobot, Grafana Cloud, Checkly) at `GET /health`.
- **Log-based metrics:** Ship Uvicorn logs to Loki/ELK and build dashboards from request logs.
- **Container metrics:** Use `cAdvisor` or `docker stats` for CPU/memory/network of the API container.

### Alerting recommendations

| Alert | Condition | Action |
|---|---|---|
| API down | `/health` returns non-200 for > 1 min | Page on-call |
| Database unreachable | `database` field ≠ `"ok"` | Check PostgreSQL container / connection |
| Migrations behind | `migrations` does not contain `(head)` | Run `alembic upgrade head` (see section 10) |
| Redis unavailable | `redis` field = `"error"` | Rate limiting falls back to in-process (no data loss) |

---

## 10. Upgrade Process

### Standard upgrade

```bash
# 1. Pull latest code
git pull origin main

# 2. Review CHANGELOG or commit log for breaking changes
git log --oneline ORIG_HEAD..HEAD

# 3. Rebuild the API image
docker compose build api

# 4. Run database migrations (non-destructive — always run before restart)
docker compose run --rm api \
  python3 -m alembic -c backend/alembic.ini upgrade head

# 5. Rolling restart of the API service
docker compose up -d --no-deps api

# 6. Verify health
curl -s http://localhost:8765/health | jq .migrations
# Expected: "<new-rev> (head)"
```

### Zero-downtime upgrade

For zero-downtime deployments, run two API replicas behind a load balancer:

1. Start a new replica with the updated image.
2. Run migrations (idempotent — safe to run while old version is live).
3. Drain the old replica via the load balancer.
4. Stop the old replica.

GrantLayer migrations are designed to be backward compatible (additive columns, no destructive DDL in rolling upgrades).

### Rollback

```bash
# Downgrade one migration step
docker compose run --rm api \
  python3 -m alembic -c backend/alembic.ini downgrade -1

# Restore previous image tag
docker compose up -d --no-deps api
```

---

## 11. Troubleshooting

### API fails to start — `ERROR: GRANTLAYER_ADMIN_TOKEN is not set`

**Cause:** `GRANTLAYER_RUNTIME_MODE=production` requires a configured admin token.

**Fix:**

```bash
# Generate a strong token
openssl rand -hex 32
# Add to .env:
GRANTLAYER_ADMIN_TOKEN=<generated-token>
GRANTLAYER_REQUIRE_ADMIN_TOKEN=true
```

---

### API fails to start — `GRANTLAYER_REQUIRE_CHALLENGE is not enabled`

**Cause:** Production mode enforces challenge validation.

**Fix:**

```dotenv
GRANTLAYER_REQUIRE_CHALLENGE=true
```

---

### JWT signing returns `501 jwt_not_configured`

**Cause:** No JWT key material is configured (`GRANTLAYER_JWT_PRIVATE_KEY` or `GRANTLAYER_JWT_SECRET` is missing).

**Fix:** Follow section 7 to generate and configure an RS256 key pair.

---

### `/health` reports `"database": "error: unreachable"`

**Cause:** The API cannot connect to PostgreSQL.

**Fix:**

```bash
# Check PostgreSQL container status
docker compose ps db

# Check PostgreSQL logs
docker compose logs db

# Verify the DATABASE_URL in .env
echo $GRANTLAYER_DATABASE_URL

# Test connectivity from the API container
docker compose exec api python3 -c \
  "import sqlalchemy; e = sqlalchemy.create_engine('$GRANTLAYER_DATABASE_URL'); e.connect()"
```

---

### Migrations not at head — `"migrations": "<rev>"` (no `(head)`)

**Cause:** New migrations were added but not applied.

**Fix:**

```bash
docker compose run --rm api \
  python3 -m alembic -c backend/alembic.ini upgrade head
docker compose restart api
```

---

### `401 jwt_invalid` — tokens being rejected

**Possible causes and fixes:**

| Symptom | Cause | Fix |
|---|---|---|
| All tokens rejected after restart | Key pair rotated | Re-issue tokens with `POST /v1/auth/token` |
| `iss` mismatch | `GRANTLAYER_JWT_ISSUER` changed | Update issuer in `.env` or re-issue tokens |
| `aud` mismatch | `GRANTLAYER_JWT_AUDIENCE` changed | Update audience in `.env` or re-issue tokens |
| Algorithm mismatch | Token signed with HS256, server expects RS256 | Set `GRANTLAYER_JWT_ALGORITHM=HS256` or re-issue as RS256 |

---

### Rate limit `429` on every request

**Cause:** `GRANTLAYER_RATE_LIMIT_AUTH` or `GRANTLAYER_RATE_LIMIT_API` set too low, or a bug is hammering the API.

**Fix:**

```dotenv
GRANTLAYER_RATE_LIMIT_AUTH=10    # requests per minute per IP for /auth/token
GRANTLAYER_RATE_LIMIT_API=120    # requests per minute per IP for all other endpoints
```

For multiple replicas, set `GRANTLAYER_REDIS_URL` so rate limit state is shared.

---

### CORS errors in browser

**Cause:** `GRANTLAYER_CORS_ALLOWED_ORIGINS` does not include the frontend origin.

**Fix:**

```dotenv
GRANTLAYER_CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
```

Exact origin match is required — no wildcards, no trailing slashes.

---

### Demo endpoints blocked — `403 demo_endpoints_public_exposure_blocked`

**Cause:** `GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true` with a non-loopback host binding.

**Fix:** Either disable demo endpoints (`GRANTLAYER_ENABLE_DEMO_ENDPOINTS=false`) or add the explicit acknowledgement:

```dotenv
GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true
```

Do not enable demo endpoints on a public-facing server.

---

## 12. CI — PostgreSQL Integration Tests

The repository ships three GitHub Actions jobs in `.github/workflows/postgres-ci.yml`:

| Job | Trigger | DB backend | Purpose |
|---|---|---|---|
| `sqlite-unit-tests` | every push/PR | SQLite (in-memory) | Lint, type check, functional suite |
| `postgres-integration` | every push/PR | PostgreSQL 16 | Single immutability integration test |
| `postgresql-integration` | after `sqlite-unit-tests` passes | PostgreSQL 16 | Full functional suite against real Postgres |

The `postgresql-integration` job starts a **temporary, ephemeral** PostgreSQL 16 container (credentials are CI-only and never used in production), runs `init_db()` to apply all schema migrations, then executes the full pytest functional suite with a 5-minute per-test timeout.

### Running PostgreSQL tests locally

Use the provided `docker-compose.test.yml`:

```bash
# Run the full suite in a Docker container (mirrors CI)
docker compose -f docker-compose.test.yml run --rm test

# Or: start just the DB, run tests from the host
docker compose -f docker-compose.test.yml up -d postgres
export GRANTLAYER_DATABASE_URL=postgresql://grantlayer:grantlayer_test@localhost:5433/grantlayer
export GRANTLAYER_RUNTIME_MODE=test
export GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE=true
pip install pytest-timeout
pytest backend/tests/ -x -q --tb=short -m "not doc_guard" --timeout 300
docker compose -f docker-compose.test.yml down -v
```

The test DB exposes PostgreSQL on host port **5433** (not 5432) to avoid conflicts with a local instance.

---

## Production Readiness Notes

GrantLayer is in **developer preview**. The following items should be reviewed before handling real customer data in a regulated environment:

- **No OAuth/OIDC:** External identity provider integration is not yet implemented. Token issuance is via the `/v1/auth/token` endpoint using operator bearer tokens.
- **No MFA:** Multi-factor authentication for operator login is not implemented.
- **Rate limiting is per-process:** Without Redis, rate limit state is not shared across API replicas. Set `GRANTLAYER_REDIS_URL` for multi-replica deployments.
- **Audit chain:** The audit log is append-only and chained. Verify the chain integrity periodically via the auditor endpoints.
- **Key rotation:** There is no automated JWT key rotation. Plan and test manual rotation (section 7) before production use.
- **Secrets management:** Use a secrets manager (HashiCorp Vault, AWS Secrets Manager, Docker Secrets) to inject sensitive env vars rather than plain `.env` files on disk.
