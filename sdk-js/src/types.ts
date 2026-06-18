/**
 * GrantLayer SDK — TypeScript type definitions.
 * Manually curated from the OpenAPI schema.
 */

export interface GrantLayerClientOptions {
  baseUrl: string;
  token?: string;
  apiKey?: string;
  /** Max retry attempts on 429/5xx (default: 3) */
  maxRetries?: number;
  /** Base delay in ms for exponential backoff (default: 500) */
  retryDelayMs?: number;
}

export interface TokenRequest {
  clientId: string;
  clientSecret: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface Grant {
  id: string;
  subjectId: string;
  role: string;
  action: string;
  resource: string;
  validFrom: string;
  validUntil: string;
  createdBy: string;
  reason: string;
  revoked: boolean;
  createdAt: string;
  workspaceId?: string;
}

export interface CreateGrantRequest {
  subjectId: string;
  role: string;
  action: string;
  resource: string;
  validFrom: string;
  validUntil: string;
  reason: string;
  workspaceId?: string;
}

export interface GrantRequest {
  id: string;
  subjectId: string;
  role: string;
  action: string;
  resource: string;
  validFrom: string;
  validUntil: string;
  requestedBy: string;
  reason: string;
  status: 'requested' | 'approved' | 'denied' | 'revoked';
  createdAt: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  subjectId: string;
  role: string;
  action: string;
  resource: string;
  approved: boolean;
  reason: string;
  workspaceId?: string;
}

export interface Workspace {
  id: string;
  tenantId: string;
  name: string;
  slug: string;
  ownerId: string;
  status: string;
  planTier: 'free' | 'pro' | 'enterprise';
  createdAt: string;
}

export interface ApiKey {
  id: string;
  name: string;
  scopes: string[];
  workspaceId: string;
  expiresAt?: string;
  createdAt: string;
  revokedAt?: string;
}

export interface CreateApiKeyRequest {
  name: string;
  scopes?: string[];
  expiresAt?: string;
  workspaceId?: string;
}

export interface CreateApiKeyResponse extends ApiKey {
  key: string;  // raw key — shown ONCE only
}

export interface WebhookSubscription {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  createdAt: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  nextCursor?: string;
  total?: number;
}

export interface GrantLayerError extends Error {
  status: number;
  body: unknown;
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
