# Self-Hosting

## Docker Compose (Recommended for Development)

```bash
git clone https://github.com/discodone/grantlayer
cd grantlayer
cp .env.example .env  # edit with your secrets
docker compose up -d
```

## Kubernetes (Helm Chart)

See [deploy/README.md](../deploy/README.md) for Helm chart installation instructions.

```bash
helm install grantlayer deploy/helm/grantlayer/ \
  --namespace grantlayer \
  --create-namespace \
  --set ingress.hosts[0].host=grantlayer.yourdomain.com
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GRANTLAYER_ADMIN_TOKEN` | Yes | Admin API token (long random string) |
| `GRANTLAYER_JWT_SECRET` | Yes (HS256) | JWT signing secret |
| `GRANTLAYER_JWT_PRIVATE_KEY` | Optional (RS256) | RSA private key for RS256 signing |
| `GRANTLAYER_DATABASE_URL` | Optional | PostgreSQL DSN (SQLite default) |
| `GRANTLAYER_REDIS_URL` | Optional | Redis DSN for rate limiting |
| `RUNTIME_MODE` | Optional | `local`/`production` (default: `local`) |
| `CORS_ALLOWED_ORIGINS` | Optional | Comma-separated allowed origins |
| `ENABLE_DEMO_ENDPOINTS` | Optional | `true` to enable demo tamper endpoints |
| `GRANTLAYER_OPA_URL` | Optional | OPA server URL for policy engine |

## Database

GrantLayer supports:
- **SQLite** (default) — zero config, for development
- **PostgreSQL 16** — required for production

Run migrations:
```bash
make migrate
# or
python3 -m alembic -c backend/alembic.ini upgrade head
```

## Health Check

```bash
curl http://localhost:8000/health
```

Returns:
```json
{"status": "ok", "redis": "disabled", "version": "0.19.0"}
```
