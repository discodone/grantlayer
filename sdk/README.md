# GrantLayer Python SDK

Python client library for the [GrantLayer](https://github.com/discodone/grantlayer) API.

## Installation

```bash
pip install grantlayer
```

Or from source:

```bash
cd sdk && pip install -e .
```

## Quick start

```python
from grantlayer import GrantLayerClient

client = GrantLayerClient("http://localhost:8765")

# Exchange credentials for a JWT (stored automatically for subsequent calls)
client.authenticate("my-operator", "my-secret")

# Create a grant
grant = client.create_grant(
    subjectId="agent-007",
    role="viewer",
    action="read",
    resource="reports",
    validFrom="2026-01-01T00:00:00Z",
    validUntil="2026-12-31T23:59:59Z",
    createdBy="admin",
    reason="Automated report access",
)
print(grant["id"])

# Retrieve and list
fetched = client.get_grant(grant["id"])
all_grants = client.list_grants()
```

## API reference

| Method | Description |
|---|---|
| `authenticate(operator_id, password)` | Exchange credentials for a JWT; stores it on the client |
| `create_grant(**kwargs)` | Create a new grant (201) |
| `get_grant(grant_id)` | Retrieve a grant by ID |
| `list_grants(**filters)` | List all grants visible to the caller |
| `create_grant_request(grant_id, **kwargs)` | Submit a grant request |
| `get_audit_log(grant_id)` | Return audit events |
| `verify_evidence_bundle(bundle_id)` | Verify an evidence bundle |

## Exceptions

```python
from grantlayer.exceptions import (
    GrantLayerError,         # base
    GrantLayerHTTPError,     # non-2xx response
    GrantLayerAuthError,     # 401 / 403
    GrantLayerNotFoundError, # 404
    GrantLayerValidationError, # 400 / 422
    GrantLayerConnectionError, # network failure
)
```

## Testing

```bash
cd sdk && python3 -m pytest tests/ -v
```
