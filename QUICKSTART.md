# GrantLayer Quickstart

Get GrantLayer running locally in under 5 minutes.

---

## Prerequisites

- Docker + Docker Compose v2
- `curl` and `openssl` (for cert generation and API calls)
- Python 3.10+ (optional, for token generation outside Docker)

---

## 1. Clone and configure

```bash
git clone https://github.com/grantlayer/grantlayer-mvp.git
cd grantlayer-mvp

# Copy and fill in your env file
cp .env.example .env
```

Open `.env` and set `GRANTLAYER_JWT_SECRET` to a random secret:

```bash
# Generate a secret and paste it into .env
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 2. Generate TLS certs (self-signed, local dev only)

```bash
./nginx/generate-certs.sh
```

This creates `nginx/certs/tls.crt` and `nginx/certs/tls.key`.
For production, replace these with a real cert (e.g. Let's Encrypt).

---

## 3. Start the stack

```bash
docker compose up -d
```

Services started:
| Service | URL |
|---------|-----|
| API (via Nginx HTTPS) | https://localhost |
| API (direct, no TLS) | http://localhost:8765 |

Check the stack is healthy:

```bash
curl -k https://localhost/health
# → {"status": "ok", ...}
```

> `-k` skips self-signed cert verification. Import `nginx/certs/tls.crt`
> into your browser or OS trust store to avoid the warning.

---

## 4. Get a JWT token

```bash
# Export your JWT secret (must match .env)
export GRANTLAYER_JWT_SECRET=<your-secret-from-.env>

# Generate a dev token (valid for 1 hour)
python3 - <<'EOF'
import os, sys
sys.path.insert(0, '.')
from backend.src.api.auth_jwt import create_dev_token
token = create_dev_token()
print(token)
EOF
```

Save the token:

```bash
export TOKEN=<paste-token-here>
```

---

## 5. Create a Grant

```bash
curl -k -s -X POST https://localhost/grants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "agent-001",
    "resource": "read:reports",
    "maxUses": 10
  }' | python3 -m json.tool
```

Response:

```json
{
  "grantId": "g_...",
  "agentId": "agent-001",
  "resource": "read:reports",
  "status": "active",
  "maxUses": 10,
  "usageCount": 0
}
```

---

## 6. List Grants

```bash
curl -k -s https://localhost/grants \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 7. Export an Audit Log

```bash
curl -k -s "https://localhost/audit/events?limit=20" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 8. Stop the stack

```bash
docker compose down
```

Data persists in Docker volumes (`grantlayer-data`). To reset completely:

```bash
docker compose down -v
```

---

## PostgreSQL instead of SQLite

```bash
# Enable the postgres profile and set credentials in .env:
# GRANTLAYER_POSTGRES_PASSWORD=a-strong-password
# GRANTLAYER_DATABASE_URL=postgres://grantlayer:a-strong-password@db:5432/grantlayer

docker compose --profile postgres up -d
```

---

## Troubleshooting

### `curl: (60) SSL certificate problem`
Use `-k` (insecure) or import `nginx/certs/tls.crt` into your system trust store:

```bash
# macOS
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain nginx/certs/tls.crt

# Linux (Debian/Ubuntu)
sudo cp nginx/certs/tls.crt /usr/local/share/ca-certificates/grantlayer-dev.crt && sudo update-ca-certificates
```

### `{"error": "jwt_required"}` / 401
Your JWT is missing or expired. Regenerate:

```bash
export GRANTLAYER_JWT_SECRET=<your-secret>
python3 -c "
import sys; sys.path.insert(0, '.')
from backend.src.api.auth_jwt import create_dev_token
print(create_dev_token())
"
```

### `nginx: [emerg] cannot load certificate`
Run `./nginx/generate-certs.sh` to create the self-signed certs, then restart:

```bash
docker compose restart nginx
```

### API container won't start
Check logs:

```bash
docker compose logs api
```

Common cause: `GRANTLAYER_JWT_SECRET` is not set in `.env`.

### Port 80/443 already in use
Change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "8080:80"
  - "8443:443"
```

Then use `curl -k https://localhost:8443/health`.

---

## JWT Authentication — Notes

GrantLayer uses **HS256 JWTs** by default (dev/demo). Each token encodes:

| Claim | Value |
|-------|-------|
| `sub` | caller identifier |
| `tenant_id` | tenant namespace |
| `role` | operator role |
| `iat` | issued-at (Unix timestamp) |
| `exp` | expiry (default: 1 hour) |

**For production**, consider:
- Shorter TTLs (15–30 min) with refresh tokens
- RS256 with asymmetric keys (switch to [PyJWT](https://pyjwt.readthedocs.io/) and set `GRANTLAYER_JWT_ALGORITHM=RS256`)
- A dedicated identity provider (Auth0, Okta, Keycloak)

---

## Next steps

- [API reference](/api/docs) — Swagger UI (available when stack is running)
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to run tests and contribute
- [SECURITY.md](SECURITY.md) — security policy and responsible disclosure
