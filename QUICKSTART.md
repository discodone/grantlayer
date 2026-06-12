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
git clone https://github.com/discodone/grantlayer.git
cd grantlayer

# Copy and fill in your env file
cp .env.example .env
```

Open `.env` and set `GRANTLAYER_JWT_SECRET` to a random secret:

```bash
# Generate a secret and paste it into .env
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> **Required:** If `GRANTLAYER_JWT_SECRET` is not set, the stack starts in legacy
> admin-token mode. Steps 4–7 (token generation and all authenticated API calls)
> will fail with `admin_token_required` or `admin_token_invalid`. Set the secret
> before running `docker compose up`.

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
# Via Nginx (TLS)
curl -k https://localhost/health
# → {"status": "ok", ...}

# Direct API port (no TLS)
curl http://localhost:8765/health
# → {"status": "ok", ...}
```

> `-k` skips self-signed cert verification. Import `nginx/certs/tls.crt`
> into your browser or OS trust store to avoid the warning.

---

## 4. Get a JWT token

```bash
export TOKEN=$(curl -s -X POST http://localhost:8765/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"operator_id\": \"dev\", \"secret\": \"$(grep GRANTLAYER_ADMIN_TOKEN .env | cut -d= -f2-)\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token acquired."
```

Response shape:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 5. Create a Grant

```bash
curl -k -s -X POST https://localhost/v1/grants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "agent-001",
    "role": "viewer",
    "action": "read",
    "resource": "reports",
    "validFrom": "2025-01-01T00:00:00Z",
    "validUntil": "2025-12-31T23:59:59Z",
    "createdBy": "dev-operator",
    "reason": "quickstart test grant",
    "maxUses": 10
  }' | python3 -m json.tool
```

Response:

```json
{
  "id": "g_...",
  "subjectId": "agent-001",
  "role": "viewer",
  "action": "read",
  "resource": "reports",
  "validFrom": "2025-01-01T00:00:00Z",
  "validUntil": "2025-12-31T23:59:59Z",
  "createdBy": "dev-operator",
  "reason": "quickstart test grant",
  "maxUses": 10,
  "useCount": 0,
  "revoked": false,
  "createdAt": "...",
  "signaturePresent": true,
  "signatureValid": true
}
```

---

## 6. List Grants

```bash
curl -k -s https://localhost/v1/grants \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 7. Submit a Grant Request (Operator Mode)

The `/v1/grant-requests` endpoint is part of the operator model — a request/approval workflow on top of direct grant creation.

> **Required:** `GRANTLAYER_ENABLE_OPERATOR_MODEL=true` must be set in `.env` (enabled by default in `docker-compose.yml`). If disabled, the endpoint returns `operator_model_disabled`.

```bash
# Add to .env if not already present:
# GRANTLAYER_ENABLE_OPERATOR_MODEL=true
```

Create a grant request:

```bash
curl -k -s -X POST https://localhost/v1/grant-requests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "agent-007",
    "role": "viewer",
    "action": "read",
    "resource": "reports",
    "validFrom": "2025-01-01T00:00:00Z",
    "validUntil": "2025-12-31T23:59:59Z",
    "reason": "Requested access for Q4 reporting"
  }' | python3 -m json.tool
```

Response includes an `id` you can use to approve or deny:

```bash
# Approve the request (replace <id> with the id from the response above):
curl -k -s -X POST https://localhost/v1/grant-requests/<id>/approve \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 8. Export an Audit Log

```bash
curl -k -s "https://localhost/v1/audit-events?limit=20" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 9. Stop the stack

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
export TOKEN=$(curl -s -X POST http://localhost:8765/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"operator_id\": \"dev\", \"secret\": \"$(grep GRANTLAYER_ADMIN_TOKEN .env | cut -d= -f2-)\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
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

### Upgrading from an older version

If you pulled a newer version of the image, always rebuild before starting to avoid stale layers:

```bash
docker compose build --no-cache
docker compose up -d
```

### Schema error at startup (`RuntimeError: missing column` / `OperationalError`)

If the database volume was created by an older version, the schema may be out of date.
**Symptom:** API container exits with `RuntimeError: missing column` or `OperationalError`.
**Fix:**

```bash
docker compose down -v
docker compose up -d
```

> **Warning:** `-v` deletes all Docker volumes including the database. All stored grants and audit events are lost. Only use this for a fresh start or local dev reset.

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
