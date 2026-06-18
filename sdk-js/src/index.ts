/**
 * GrantLayer JavaScript/TypeScript SDK
 *
 * @example
 * ```typescript
 * import { GrantLayerClient } from 'grantlayer-sdk';
 *
 * const client = new GrantLayerClient({
 *   baseUrl: 'https://api.grantlayer.example.com',
 *   apiKey: 'gl_live_...',
 * });
 *
 * const grants = await client.listGrants({ limit: 50 });
 * ```
 */

export { GrantLayerClient } from './client.js';
export type {
  ApiKey,
  AuditEvent,
  CreateApiKeyRequest,
  CreateApiKeyResponse,
  CreateGrantRequest,
  Grant,
  GrantLayerClientOptions,
  GrantLayerError,
  GrantRequest,
  Workspace,
  WebhookSubscription,
  TokenRequest,
  TokenResponse,
} from './types.js';
