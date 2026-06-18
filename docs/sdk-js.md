# JavaScript/TypeScript SDK

The `grantlayer-sdk` package provides a type-safe client for the GrantLayer API.

## Installation

```bash
npm install grantlayer-sdk
```

## Quickstart

```typescript
import { GrantLayerClient } from 'grantlayer-sdk';

const client = new GrantLayerClient({
  baseUrl: 'https://api.example.com',
  apiKey: 'gl_live_your_key_here',
});

// List grants
const grants = await client.listGrants({ limit: 50 });

// Create a grant
const grant = await client.createGrant({
  subjectId: 'agent-123',
  role: 'viewer',
  action: 'read',
  resource: 'documents/report.pdf',
  validFrom: '2026-01-01T00:00:00Z',
  validUntil: '2026-12-31T23:59:59Z',
  reason: 'Quarterly report review',
});

// Create a long-lived API key
const { key } = await client.createApiKey({
  name: 'CI Pipeline',
  scopes: ['read_only'],
});
console.log('Save this key:', key); // gl_live_...
```

## Features

- Fetch-based (no runtime dependencies)
- Node.js 18+ and browser compatible
- ESM + CJS dual output
- TypeScript strict mode
- Automatic retry with exponential backoff
- 429 Retry-After header awareness

## API Reference

See [sdk-js/README.md](https://github.com/discodone/grantlayer/tree/main/sdk-js/README.md) for full method documentation.
