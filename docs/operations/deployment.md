# GrantLayer MVP — SQLite Production Deployment Guide

This document covers running GrantLayer MVP with a persistent SQLite database in production-like environments.

## Prerequisites

- Python 3.13+
- SQLite 3 (bundled with Python)
- A dedicated directory for the database file (must be writable)
- Optional: systemd (Linux) or Docker Compose

## Environment Variables

See `.env.example` in the repository root for a full template.

Key variables for production persistence:

| Variable | Purpose | Example |
|----------|---------|---------|
| `GRANTLAYER_DATABASE_URL` | SQLite database URL (preferred) | `sqlite:///var/lib/grantlayer/grantlayer.db` |
| `GRANTLAYER_DB` | Legacy plain file path (fallback) | `/var/lib/grantlayer/grantlayer.db` |
| `GRANTLAYER_HOST` | Bind address | `127.0.0.1` |
| `GRANTLAYER_PORT` | Bind port | `8765` |
| `GRANTLAYER_LOG_LEVEL` | Log verbosity | `INFO` |
| `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` | Health probe timeout | `2000` |
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | Enforce admin token | `true` |
| `GRANTLAYER_REQUIRE_CHALLENGE` | Require challenges | `true` |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | Disable demo endpoints | `false` |
| `GRANTLAYER_ADMIN_TOKEN` | Admin token value | `change-me` |

## SQLite Production Notes

- GrantLayer uses **WAL mode** by default. Three files move together:
  - `grantlayer.db`
  - `grantlayer.db-wal`
  - `grantlayer.db-shm`
- The database directory must be writable.
- Only one writer at a time. Do not share the same `.db` file across multiple processes.
- Backup: copy all three files after stopping the server, or use `VACUUM INTO` while running.
- See `backup_restore.md` for detailed backup/restore procedures.

## systemd Service Example

Create `/etc/systemd/system/grantlayer.service`:

```ini
[Unit]
Description=GrantLayer MVP
After=network.target

[Service]
Type=simple
User=grantlayer
Group=grantlayer
WorkingDirectory=/opt/grantlayer
Environment="GRANTLAYER_DATABASE_URL=sqlite:///var/lib/grantlayer/grantlayer.db"
Environment="GRANTLAYER_HOST=127.0.0.1"
Environment="GRANTLAYER_PORT=8765"
Environment="GRANTLAYER_LOG_LEVEL=INFO"
Environment="GRANTLAYER_REQUIRE_ADMIN_TOKEN=true"
Environment="GRANTLAYER_REQUIRE_CHALLENGE=true"
Environment="GRANTLAYER_ENABLE_DEMO_ENDPOINTS=false"
Environment="GRANTLAYER_ADMIN_TOKEN=change-me-in-production"
ExecStart=/usr/bin/python3 -m backend.src.server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo mkdir -p /var/lib/grantlayer
sudo chown grantlayer:grantlayer /var/lib/grantlayer
sudo systemctl daemon-reload
sudo systemctl enable grantlayer
sudo systemctl start grantlayer
```

## Docker Compose Example

Create `docker-compose.yml`:

```yaml
version: "3.8"
services:
  grantlayer:
    build: .
    ports:
      - "127.0.0.1:8765:8765"
    environment:
      GRANTLAYER_DATABASE_URL: "sqlite:///data/grantlayer.db"
      GRANTLAYER_HOST: "0.0.0.0"
      GRANTLAYER_PORT: "8765"
      GRANTLAYER_LOG_LEVEL: "INFO"
      GRANTLAYER_REQUIRE_ADMIN_TOKEN: "true"
      GRANTLAYER_REQUIRE_CHALLENGE: "true"
      GRANTLAYER_ENABLE_DEMO_ENDPOINTS: "false"
      GRANTLAYER_ADMIN_TOKEN: "change-me-in-production"
    volumes:
      - grantlayer-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped

volumes:
  grantlayer-data:
```

Start with:

```bash
docker compose up -d
```

## Healthcheck Integration

The `GET /health` endpoint returns:

```json
{
  "ok": true,
  "service": "grantlayer-mvp",
  "timestamp": "...",
  "dbConfigured": true,
  "adminTokenConfigured": true,
  "requireAdminToken": true,
  "requireChallenge": true,
  "demoEndpointsEnabled": false,
  "operatorModelEnabled": false,
  "operatorsConfigured": false,
  "dbConnected": true,
  "dbWritable": true,
  "dbFilePresent": true,
  "dbDirectoryWritable": true,
  "dbSizeBytes": 57344,
  "journalMode": "wal",
  "dbPathKind": "file"
}
```

Key fields for load-balancer or orchestrator health checks:
- `dbConnected` — false if the database is unreachable
- `dbWritable` — false if the directory or database is read-only
- `dbFilePresent` — false if the expected on-disk DB file is missing

Systemd and Docker Compose can use `curl` to probe the endpoint.
Kubernetes liveness/readiness example:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8765
  initialDelaySeconds: 5
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /health
    port: 8765
  initialDelaySeconds: 2
  periodSeconds: 10
```

## Migration Notes (GL-033)

- The first time the server starts on a fresh database, a baseline migration (`0001_gl032_baseline`) creates the full schema.
- On an existing GL-032 database, the baseline is validated and marked as applied without re-running CREATE statements.
- Future schema changes will use sequential migrations starting at `0002_*`.
- The `schema_migrations` table tracks applied versions.

## What GL-033 Does NOT Provide

- No PostgreSQL backend (planned for a future milestone).
- No automated horizontal scaling (SQLite is single-writer).
- No built-in backup scheduling (use cron + scripts).
- No TLS termination (run behind a reverse proxy).
