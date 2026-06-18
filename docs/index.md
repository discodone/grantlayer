# GrantLayer

**Secure AI Agent Grant Management**

GrantLayer is an open-source, API-first authorization layer for AI agents. It provides fine-grained, auditable grants that control what actions AI agents can take on behalf of users.

## Why GrantLayer?

Modern AI agents need to take actions — reading documents, sending emails, executing code. GrantLayer gives you:

- **Explicit grants** — every agent action is authorized by a pre-approved grant
- **Full audit trail** — cryptographically chained, tamper-evident audit log
- **Multi-tenant workspaces** — isolate agents per team or customer
- **API-first** — integrate with any language via REST or our SDKs
- **Open source** — self-host or extend for your needs

## Quick Links

- [Getting Started →](getting-started.md)
- [Authentication →](authentication.md)
- [Python SDK →](sdk-python.md)
- [JavaScript SDK →](sdk-js.md)
- [Self-Hosting →](self-hosting.md)

## Quickstart

```bash
# 1. Start GrantLayer
docker compose up -d

# 2. Create an operator
curl -X POST http://localhost:8000/v1/admin/operators \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent","role":"viewer","tenantId":"my-org"}'

# 3. Get a JWT token
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"clientId":"my-agent","clientSecret":"..."}'

# 4. Create a grant
curl -X POST http://localhost:8000/v1/grants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "agent-123",
    "role": "viewer",
    "action": "read",
    "resource": "documents/report.pdf",
    "validFrom": "2026-01-01T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "reason": "Quarterly report review"
  }'
```
