# Webhooks

GrantLayer can deliver real-time event notifications to your endpoints via webhooks.

## Creating a Webhook

```bash
curl -X POST https://api.example.com/v1/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.example.com/webhooks/grantlayer",
    "events": ["grant.created", "grant.revoked", "grant_request.approved"],
    "secret": "your-webhook-secret"
  }'
```

## Verifying Webhook Signatures

Every webhook request includes an `X-GrantLayer-Signature` header:

```
X-GrantLayer-Signature: sha256=<hmac_hex>
```

Verify it in Python:

```python
import hashlib, hmac

def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Available Events

| Event | Description |
|-------|-------------|
| `grant.created` | A new grant was created |
| `grant.revoked` | A grant was revoked |
| `grant_request.submitted` | A new grant request was submitted |
| `grant_request.approved` | A grant request was approved |
| `grant_request.denied` | A grant request was denied |
| `audit.chain_verified` | Audit chain was verified |

## Retry Policy

Failed deliveries are retried up to 3 times with exponential backoff (1s, 2s, 4s). Failed deliveries after 3 attempts are moved to the dead-letter queue.
