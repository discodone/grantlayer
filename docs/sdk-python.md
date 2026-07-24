# Python SDK

GrantLayer provides a Python SDK built on `httpx`, with sync
(`GrantLayerClient`) and async (`AsyncGrantLayerClient`) variants.

## Installation

Published on PyPI as `grantlayer`:

```bash
pip install grantlayer
```

## Quickstart

Verified against the local Docker quickstart stack (see `QUICKSTART.md`):

```python
import os

from grantlayer import GrantLayerClient

gl = GrantLayerClient("http://localhost:8765")

# local quickstart: any operator id + the admin token from .env
gl.authenticate("dev", os.environ["GRANTLAYER_ADMIN_TOKEN"])

# issue a time-boxed, signed grant
grant = gl.create_grant(
    subjectId="agent-7",
    role="operator",
    action="deploy",
    resource="service:payments",
    validFrom="2026-01-01T00:00:00Z",
    validUntil="2026-12-31T00:00:00Z",
    createdBy="dev",
    reason="scheduled release",
)

print(grant["id"], grant["signaturePresent"])
```

The async variant exposes the same methods as coroutines:

```python
from grantlayer import AsyncGrantLayerClient
```

## Reference

See `sdk/grantlayer/` for the SDK source code and `sdk/README.md` for the
full method table.
