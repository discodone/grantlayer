# Getting Started

## Prerequisites

- Docker & Docker Compose (for self-hosted deployment)
- Or: Python 3.11+ (for local development)

## Local Development Setup

```bash
git clone https://github.com/discodone/grantlayer
cd grantlayer

# Install dependencies
make install

# Start the API server
python3 -m backend

# Or with Docker
docker compose up -d
```

The API will be available at `http://localhost:8000`.

## First Steps

### 1. Set environment variables

```bash
export GRANTLAYER_ADMIN_TOKEN="your-long-random-admin-token"
export GRANTLAYER_JWT_SECRET="your-32-char-min-jwt-secret"
```

### 2. Create an operator (agent identity)

```bash
curl -X POST http://localhost:8000/v1/admin/operators \
  -H "Authorization: Bearer $GRANTLAYER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent","role":"viewer","tenantId":"my-org"}'
```

### 3. Authenticate

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"clientId":"my-agent","clientSecret":"from-create-response"}' \
  | jq -r '.access_token')
```

### 4. Create a grant

```bash
curl -X POST http://localhost:8000/v1/grants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "agent-123",
    "role": "viewer",
    "action": "read",
    "resource": "documents/*",
    "validFrom": "2026-01-01T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "reason": "Read access for document review"
  }'
```

### 5. Check the audit log

```bash
curl http://localhost:8000/v1/audit-events \
  -H "Authorization: Bearer $TOKEN"
```

## API Documentation

Interactive API docs are available at:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`
