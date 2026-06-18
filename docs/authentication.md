# Authentication

GrantLayer supports three authentication methods.

## 1. JWT Bearer Tokens (Recommended)

Short-lived tokens issued by `/v1/auth/token`.

```bash
# Get a token
curl -X POST https://api.example.com/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"clientId":"operator-id","clientSecret":"secret"}'

# Use the token
curl https://api.example.com/v1/grants \
  -H "Authorization: Bearer eyJ..."
```

Tokens expire after 1 hour by default.

## 2. Long-Lived API Keys

For CI pipelines and server-to-server integrations, create an API key:

```bash
# Create a key (raw key shown ONCE — save it immediately)
curl -X POST https://api.example.com/v1/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"CI Pipeline","scopes":["read_only"]}'

# Use the key (same Authorization: Bearer header)
curl https://api.example.com/v1/grants \
  -H "Authorization: Bearer gl_live_..."
```

API keys start with `gl_live_` and are SHA-256 hashed before storage.

### Scopes

| Scope | Permissions |
|-------|-------------|
| `read_only` | Read grants, audit events, workspaces |
| `read_write` | Read + create/update grants and requests |
| `admin` | Full access |

## 3. OIDC (External Identity Providers)

When `GRANTLAYER_ENABLE_OIDC=true`, tokens from configured providers (Keycloak, Auth0, Azure AD) are accepted directly.

```bash
export GRANTLAYER_ENABLE_OIDC=true
export GRANTLAYER_OIDC_ISSUER=https://your-idp.example.com
export GRANTLAYER_OIDC_AUDIENCE=grantlayer
```

## Rate Limiting

All `/v1/` endpoints are rate-limited per IP. Limits vary by workspace plan:

| Plan | Limit |
|------|-------|
| Free | 100 req/min |
| Pro | 1000 req/min |
| Enterprise | Unlimited |

Rate-limited responses return `HTTP 429` with a `Retry-After` header and `X-Plan-Tier` on all responses.
