# Python SDK

GrantLayer provides an async Python SDK built on `httpx`.

## Installation

```bash
pip install grantlayer
```

## Quickstart

```python
import asyncio
from grantlayer import GrantLayerClient

async def main():
    client = GrantLayerClient(
        base_url="https://api.example.com",
        api_key="gl_live_your_key_here",
    )
    
    # List grants
    grants = await client.grants.list()
    
    # Create a grant
    grant = await client.grants.create(
        subject_id="agent-123",
        role="viewer",
        action="read",
        resource="documents/report.pdf",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2026-12-31T23:59:59Z",
        reason="Quarterly report review",
    )
    print(f"Created grant: {grant['id']}")

asyncio.run(main())
```

## Reference

See `backend/src/sdk/` for the Python SDK source code.
