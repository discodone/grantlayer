# GrantLayer Minimal Python SDK

## Status

- **developer-preview** — local use only, not package-published
- Production SaaS readiness is **not claimed**
- Tenant isolation is **not implemented**
- Standard library only; no pip dependencies beyond the repo itself
- Issue: GL-147

## Install / Use

No pip package is published. Import directly from the local repository:

```python
import sys
sys.path.insert(0, "sdk/python")
from grantlayer_client import GrantLayerClient
```

Or run from the repo root:

```bash
PYTHONPATH=sdk/python python3 your_script.py
```

## Configuration

```python
client = GrantLayerClient(
    base_url="http://127.0.0.1:8765",
    token=None,       # public endpoints (health, readiness) need no token
    timeout=10.0,
)
```

For protected endpoints, pass a placeholder token (local dev only — do not use real secrets):

```python
client = GrantLayerClient(
    base_url="http://127.0.0.1:8765",
    token="demo-admin-token-local",   # placeholder only, not a real secret
)
```

Authentication modes (see `docs/openapi.yaml`):
- Legacy mode (`ENABLE_OPERATOR_MODEL=false`): admin token via `Authorization: Bearer <token>`
- Operator mode (`ENABLE_OPERATOR_MODEL=true`): operator token via `Authorization: Bearer <token>`

## Basic Usage

```python
# Liveness check — no auth required
resp = client.health()
print(resp.status, resp.body)   # 200, {"status": "ok"}

# Readiness check — no auth required
resp = client.ready()
print(resp.status, resp.body)   # 200, {"status": "ready", ...}

# Generic JSON request
resp = client.request_json("GET", "/grants")
print(resp.status, resp.body)

# POST with a JSON body
resp = client.request_json(
    "POST",
    "/grants",
    body={
        "subject": "gl147-demo-subject-001",
        "action": "read",
        "resource": "gl147-demo-resource-001",
        "grantedBy": "gl147-demo-admin",
    },
)
print(resp.status, resp.body)
```

## Error Handling

```python
from grantlayer_client import (
    GrantLayerClient,
    GrantLayerClientError,
    GrantLayerHTTPError,
    GrantLayerJSONError,
)

try:
    resp = client.request_json("GET", "/grants/nonexistent-id")
except GrantLayerHTTPError as exc:
    print(f"Server error: HTTP {exc.status}")   # e.g. HTTP 404
except GrantLayerJSONError as exc:
    print(f"Bad response body: {exc}")
except GrantLayerClientError as exc:
    print(f"Connection failed: {exc}")
```

- `GrantLayerHTTPError` — server returned a non-2xx status; `.status` holds the code
- `GrantLayerJSONError` — response body was not valid JSON
- `GrantLayerClientError` — base class; also covers connection/URL errors

Tokens are **never included** in exception messages.

## Safety

- Local development and evaluation use only
- Do not use real customer data
- Do not use real secrets or production tokens
- Do not use this SDK in a production environment
- Tenant isolation is not implemented in the current backend
- No package is published to PyPI or any registry

## Next Steps

| Issue | Title |
|-------|-------|
| GL-148 | LangGraph/LangChain Integration Example |
| GL-149 | Public GitHub Readiness Pack |
| GL-150 | First Developer Feedback Log |
