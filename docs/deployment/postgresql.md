# GrantLayer MVP — PostgreSQL Deployment (GL-035)

## Quick start

### SQLite (default)
```bash
Docker compose up -d
```

### PostgreSQL (opt-in)
```bash
# Run the PostgreSQL override
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d
```

## Prerequisites

- Docker Engine 24.0+
- Docker Compose v2+
- psycopg2-binary (for local Python execution outside Docker)

## Configuration

Copy `.env.example` to `.env` and adjust:

### SQLite default
```
GRANTLAYER_DB=data/grantlayer.db
```

### PostgreSQL via URL
```
GRANTLAYER_DATABASE_URL=postgres://user:password@localhost:5432/grantlayer
```

The `GRANTLAYER_DATABASE_URL` takes precedence over `GRANTLAYER_DB` when set.

### Connection retry tuning (PostgreSQL)
```
GRANTLAYER_DB_RETRY_MAX=5
GRANTLAYER_DB_RETRY_DELAY=1.0
```

## Docker Compose profile

`docker-compose.postgres.yml` provides:
- `postgres:16-alpine` service with healthcheck
- Named volume `grantlayer-postgres-data` for persistence
- Bridge network `grantlayer`
- API service override that:
  - disables `GRANTLAYER_DB`
  - sets `GRANTLAYER_DATABASE_URL` to the DB service
  - waits for `db` healthcheck before starting

## Health probes

`/health` returns backend-aware fields:

- `dbConnected`: bool
- `dbWritable`: bool
- `dbPathKind`: `"memory" | "file" | "postgres"`

When connected to PostgreSQL, also returns:
- `pgVersion`: server version string (e.g. `"16.2"`)
- `pgBackendPid`: integer backend PID
- `pgActiveConnections`: integer current connections to this database

No DSN, hostname, password, or raw URL is exposed.

## Operational smoke verification

```bash
export GRANTLAYER_DATABASE_URL=postgres://user:password@host/db
./scripts/acceptance_postgres.sh
```

The script skips cleanly if:
- `GRANTLAYER_DATABASE_URL` is unset or not a PostgreSQL URL
- `psycopg2` is not installed
- PostgreSQL is not reachable

## Security boundaries

- No secrets in `/health` output
- No secrets in logs or exception messages
- No secrets in test output
- Placeholder values only in documentation examples
- Invalid DB URLs raise `RuntimeError` with scheme only (no credentials)

## Migration behavior

- Fresh PostgreSQL database: Full schema applied via migrations
- Existing database: Baseline validated, migration tracker updated
- Second startup: Idempotent (no schema changes)
