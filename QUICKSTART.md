# GrantLayer Quickstart

Get GrantLayer running locally in under 5 minutes.

---

## Prerequisites

- Docker + Docker Compose v2.24+
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

Generate an RS256 key pair and add it to your `.env` file:

```bash
# Generate key pair
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Base64-encode and copy into .env
export GRANTLAYER_JWT_PRIVATE_KEY=$(base64 -w0 private.pem)
export GRANTLAYER_JWT_PUBLIC_KEY=$(base64 -w0 public.pem)
echo "GRANTLAYER_JWT_PRIVATE_KEY=$GRANTLAYER_JWT_PRIVATE_KEY" >> .env
echo "GRANTLAYER_JWT_PUBLIC_KEY=$GRANTLAYER_JWT_PUBLIC_KEY" >> .env
```

> **Required:** JWT key material must be configured before starting the stack.
> Without RS256 keys (or a legacy `GRANTLAYER_JWT_SECRET` for HS256), the stack
> starts in legacy admin-token mode and Steps 4–7 will fail with
> `admin_token_required` or `admin_token_invalid`.

---

## 2. Generate TLS certs (self-signed, local dev only)

```bash
./nginx/generate-certs.sh
```

This creates `nginx/certs/tls.crt` and `nginx/certs/tls.key`.
For production, replace these with a real cert (e.g. Let's Encrypt).

---

## 3. Provision the database and start the stack

PostgreSQL is the default backend, and the app does **not** self-provision a
production database. Apply the schema with Alembic before starting the API —
skip this and the API container fails to start on a fresh database:

```bash
# Start PostgreSQL, then apply migrations with Alembic (the authoritative path)
docker compose up -d db
docker compose run --rm api python3 -m alembic -c backend/alembic.ini upgrade head

# Start the full stack
docker compose up -d
```

> **SQLite-only local dev** (`docker compose -f docker-compose.dev.yml up -d`, or
> `GRANTLAYER_DATABASE_URL=""`) needs no separate step — the bundled dev runner
> auto-provisions SQLite on first start.

Services started:
| Service | URL |
|---------|-----|
| API (via Nginx HTTPS) | https://localhost |
| API (direct, no TLS) | http://localhost:8765 |

> The stack runs in `GRANTLAYER_RUNTIME_MODE=local` (evaluation defaults) unless
> you set `production` in `.env`. The Cardano anchoring worker is optional and
> profile-gated: `docker compose --profile anchoring up -d` — create the secrets
> files described in `secrets/README.md` first. The default stack needs neither.

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

Response includes an `id` you can use to approve or deny.

**Approvals need a second operator.** An operator cannot approve their own
request — approving with the same `$TOKEN` that created it returns
`403 self_approval_forbidden` by design. Mint a token for a *different*
operator id and approve with that:

```bash
# Second operator token (note operator_id "approver", not "dev"):
export APPROVER_TOKEN=$(curl -s -X POST http://localhost:8765/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"operator_id\": \"approver\", \"secret\": \"$(grep GRANTLAYER_ADMIN_TOKEN .env | cut -d= -f2-)\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Approve the request (replace <id> with the id from the response above):
curl -k -s -X POST https://localhost/v1/grant-requests/<id>/approve \
  -H "Authorization: Bearer $APPROVER_TOKEN" | python3 -m json.tool
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

Common causes:
- RS256 key pair not set: `GRANTLAYER_JWT_PRIVATE_KEY` / `GRANTLAYER_JWT_PUBLIC_KEY` missing from `.env`
- Legacy HS256 mode: `GRANTLAYER_JWT_SECRET` is empty (if using `GRANTLAYER_JWT_ALGORITHM=HS256`)
- `GRANTLAYER_RUNTIME_MODE=production` set without the production configuration it
  enforces (strong admin token, Redis, `GRANTLAYER_UNSUBSCRIBE_SECRET`, challenge
  enforcement) — the startup gate lists each missing item in `docker compose logs api`.
  See the hardening checklist in DEPLOYMENT.md, or stay on the `local` default for evaluation.
  Valid mode values: `local`, `demo`, `test`, `staging`, `production`.

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

GrantLayer uses **RS256 JWTs** by default (asymmetric key pair). Each token encodes:

| Claim | Value |
|-------|-------|
| `sub` | caller identifier |
| `tenant_id` | tenant namespace |
| `role` | operator role |
| `iat` | issued-at (Unix timestamp) |
| `exp` | expiry (default: 1 hour) |

Set `GRANTLAYER_JWT_PRIVATE_KEY` (base64-encoded PEM) for signing and
`GRANTLAYER_JWT_PUBLIC_KEY` (base64-encoded PEM) for verification. See Step 1
for key generation commands.

### Required: JWT issuer and audience

`JWT_STRICT_CLAIMS` is **`true` by default** — tokens that are missing `iss`
or `aud` claims are rejected. You must set matching values in your `.env`:

```env
# Unique per deployment — prevents cross-instance token replay
GRANTLAYER_JWT_ISSUER=my-org-grantlayer-prod
GRANTLAYER_JWT_AUDIENCE=grantlayer-api-prod
```

Tokens signed by your stack will embed these values automatically. Tokens
from external issuers (OIDC) must include matching claims.

> **Do not** leave `GRANTLAYER_JWT_ISSUER` at its default `grantlayer` value
> in production. Two deployments sharing the same issuer string and signing key
> will cross-accept each other's tokens.

**For production**, also consider:
- Shorter TTLs (15–30 min) with refresh tokens
- A dedicated identity provider (Auth0, Okta, Keycloak)

**Legacy HS256:** Set `GRANTLAYER_JWT_ALGORITHM=HS256` and `GRANTLAYER_JWT_SECRET`
to use symmetric signatures. Not recommended for production.

---

## Next steps

- [API reference](/api/docs) — Swagger UI (available when stack is running)
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to run tests and contribute
- [SECURITY.md](SECURITY.md) — security policy and responsible disclosure
