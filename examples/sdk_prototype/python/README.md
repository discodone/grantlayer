# GrantLayer SDK Prototype — GL-203C (Internal Only)

## Status

| Field | Value |
|---|---|
| Maturity | **Experimental / Internal prototype only** |
| Issue | GL-203C |
| SDK type | Prototype — not an official SDK |
| Published | **No** — not published to any package registry |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | Baseline implemented, not production-complete |
| Real customer data | **No** — use synthetic identifiers only |
| Real secrets | **No** — use placeholder tokens only |
| Official SDK/package | **Not claimed** — this is a prototype for feasibility |

This file is an **experimental internal prototype** produced for GL-203C SDK
Prototype / Packaging Boundary exploration. It is not a replacement for
`sdk/python/grantlayer_client.py` and must not be presented as an official
or published SDK.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Security-sensitive reports route to GitHub Security Advisories.

---

## What this demonstrates

This prototype shows that the GL-203B cleaned OpenAPI contract (`docs/openapi.yaml`
version `0.203b.0-developer-preview`) is sufficient for SDK work:

- **Auth model clarity**: Both `LegacyAdminToken` and `OperatorToken` auth modes
  are representable with a single token parameter.
- **Tenant context**: Server-derived; no override header is needed or supported.
- **Injectable transport**: Tests run without network via `FakeTransport`.
- **Token safety**: Token is never included in `__repr__`, error messages, or logs.
- **Endpoint coverage**: Health, readiness, grants, audit, challenges, grant requests,
  grant executions, evidence bundles, operator profile, and agent permissions.

---

## What this is NOT

- Not a PyPI package.
- Not an official SDK.
- Not production-ready.
- Not a replacement for the existing `sdk/python/grantlayer_client.py`.
- Not for use with real customer data.
- Not for use with real secrets.
- Not for deployment to shared infrastructure.

---

## Usage (local evaluation only)

```python
# Import directly — no pip install
import sys
sys.path.insert(0, "examples/sdk_prototype/python")
from grantlayer_client import GrantLayerClient, GrantLayerHTTPError

# Public endpoint (no token needed)
client = GrantLayerClient("http://127.0.0.1:8765")
resp = client.health()
print(resp.status, resp.body)

# Authenticated endpoint (placeholder token — not a real secret)
client = GrantLayerClient(
    "http://127.0.0.1:8765",
    token="demo-admin-token-local",   # placeholder only
)
resp = client.list_grants()
print(resp.status, resp.body)
```

---

## Testing without network

```python
from grantlayer_client import GrantLayerClient, FakeTransport

transport = FakeTransport()
transport.add_response(200, {"status": "ok", "service": "grantlayer", "checkType": "liveness"})

client = GrantLayerClient("http://fake", _transport=transport)
resp = client.health()
assert resp.status == 200
assert resp.body["status"] == "ok"
assert len(transport.calls) == 1
```

---

## Key safety properties

| Property | Behavior |
|---|---|
| Token in `repr(client)` | **Never** — only `has_token=True/False` shown |
| Token in error messages | **Never** — only HTTP status and error code |
| Tenant override header | **Not supported** — tenant is server-derived |
| Network at import time | **None** — no calls until a method is invoked |
| External dependencies | **None** — Python stdlib only |
| Default base URL | **None** — caller must supply |
| Default token | **None** — caller must supply |

---

## Auth modes

Both auth modes use `Authorization: Bearer <token>`:

```python
# Legacy admin-token mode (ENABLE_OPERATOR_MODEL=false)
client = GrantLayerClient("http://127.0.0.1:8765", token="<admin-token>")

# Operator mode (ENABLE_OPERATOR_MODEL=true)
client = GrantLayerClient("http://127.0.0.1:8765", token="<operator-token>")
```

Tenant context is always derived server-side from the authenticated identity.
Do not attempt to add X-Tenant-ID or similar headers.

---

## Remaining blockers before official SDK

See `docs/sdk_prototype_packaging_boundary.md` for the full packaging boundary
assessment. Key remaining blockers:

1. workspace_id enforcement not yet implemented (deferred).
2. Admin-plane tenant isolation (GL-200D) deferred.
3. PostgreSQL not live-validated (GL-204).
4. Stale tenant isolation claim in public docs requires coordinated correction.
5. No package publishing pipeline established.
6. No semantic versioning commitment made.
