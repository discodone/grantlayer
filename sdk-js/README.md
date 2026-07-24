# GrantLayer JavaScript/TypeScript SDK

Official TypeScript SDK for the GrantLayer API. Works in Node.js 18+ and modern browsers.

## Installation

The package is **not yet published to npm** — build it from source:

```bash
git clone https://github.com/discodone/grantlayer.git
cd grantlayer/sdk-js
npm install
npm run build           # emits dist/ (ESM + CJS + type declarations)
npm pack                # produces grantlayer-sdk-<version>.tgz
```

Then install the tarball in your project:

```bash
npm install /path/to/grantlayer-sdk-<version>.tgz
```

## Quickstart

```typescript
import { GrantLayerClient } from 'grantlayer-sdk';

// Authenticate with API key (recommended)
const client = new GrantLayerClient({
  baseUrl: 'https://api.grantlayer.example.com',
  apiKey: 'gl_live_your_key_here',
});

// Or authenticate with JWT
const jwtClient = new GrantLayerClient({ baseUrl: 'https://api.grantlayer.example.com' });
await jwtClient.getToken({ clientId: 'my-operator', clientSecret: 'my-secret' });

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
  reason: 'Agent needs read access for quarterly report',
});

// Create a long-lived API key
const keyResult = await client.createApiKey({
  name: 'CI Pipeline Key',
  scopes: ['read_only'],
});
console.log('Save this key NOW (shown once):', keyResult.key);
```

## Features

- **All endpoints** — auth, workspaces, grants, grant requests, audit, webhooks, API keys, GDPR
- **Retry logic** — 3 attempts, exponential backoff, 429 Retry-After awareness
- **Dual output** — ESM + CJS, works in Node.js 18+ and browser
- **TypeScript strict** — full type coverage, no `any` in public API
- **Zero runtime dependencies** — uses native `fetch`

## API Reference

### `new GrantLayerClient(options)`

| Option | Type | Description |
|--------|------|-------------|
| `baseUrl` | `string` | API base URL (required) |
| `token` | `string` | JWT Bearer token |
| `apiKey` | `string` | API key (starts with `gl_live_`) |
| `maxRetries` | `number` | Max retry attempts (default: 3) |
| `retryDelayMs` | `number` | Base retry delay in ms (default: 500) |

### Methods

| Method | Description |
|--------|-------------|
| `getToken(req)` | Authenticate and get JWT token |
| `listGrants(params?)` | List grants |
| `createGrant(req)` | Create a new grant |
| `getGrant(id)` | Get a specific grant |
| `revokeGrant(id, reason)` | Revoke a grant |
| `listGrantRequests(params?)` | List grant requests |
| `createGrantRequest(req)` | Submit a grant request |
| `approveGrantRequest(id, reason?)` | Approve a request |
| `denyGrantRequest(id, reason)` | Deny a request |
| `bulkApproveRequests(ids, reason?)` | Bulk approve |
| `listAuditEvents(params?)` | List audit events |
| `exportAuditLog(params?)` | Export NDJSON audit log |
| `verifyAuditChain(params?)` | Verify chain integrity |
| `listWorkspaces()` | List workspaces (admin) |
| `updateWorkspacePlan(id, tier, override?)` | Update workspace plan tier |
| `listApiKeys()` | List API keys |
| `createApiKey(req)` | Create API key (returns raw key once) |
| `revokeApiKey(id)` | Revoke API key |
| `exportUserData(userId)` | GDPR data export |
| `eraseUserData(userId)` | GDPR erasure |

## Development

```bash
cd sdk-js
npm ci
npm test
npm run build
```
