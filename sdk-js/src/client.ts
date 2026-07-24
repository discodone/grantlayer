/**
 * GrantLayer SDK — Main client class.
 * Fetch-based, works in Node.js 18+ and browser.
 * Retry logic: 3 attempts, exponential backoff, 429 Retry-After awareness.
 */

import type {
  ApiKey,
  AuditEvent,
  CreateApiKeyRequest,
  CreateApiKeyResponse,
  CreateGrantRequest,
  Grant,
  GrantLayerClientOptions,
  GrantLayerError,
  GrantRequest,
  HttpMethod,
  TokenRequest,
  TokenResponse,
  Workspace,
  WebhookSubscription,
} from './types.js';

function createError(status: number, body: unknown): GrantLayerError {
  const err = new Error(`GrantLayer API error: ${status}`) as GrantLayerError;
  err.status = status;
  err.body = body;
  return err;
}

const _sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export class GrantLayerClient {
  private readonly baseUrl: string;
  private token: string | undefined;
  private readonly apiKey: string | undefined;
  private readonly maxRetries: number;
  private readonly retryDelayMs: number;

  constructor(options: GrantLayerClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.token = options.token;
    this.apiKey = options.apiKey;
    this.maxRetries = options.maxRetries ?? 3;
    this.retryDelayMs = options.retryDelayMs ?? 500;
  }

  private getAuthHeader(): Record<string, string> {
    if (this.apiKey) {
      return { Authorization: `Bearer ${this.apiKey}` };
    }
    if (this.token) {
      return { Authorization: `Bearer ${this.token}` };
    }
    return {};
  }

  private async request<T>(
    method: HttpMethod,
    path: string,
    body?: unknown,
    headers?: Record<string, string>,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const reqHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeader(),
      ...headers,
    };

    let attempt = 0;
    let lastError: GrantLayerError | undefined;

    while (attempt <= this.maxRetries) {
      const init: RequestInit = { method, headers: reqHeaders };
      if (body !== undefined) {
        init.body = JSON.stringify(body);
      }
      const response = await fetch(url, init);

      if (response.ok) {
        if (response.status === 204) return undefined as unknown as T;
        return response.json() as Promise<T>;
      }

      // Retry on 429 (rate limit) or 5xx (server errors)
      if ((response.status === 429 || response.status >= 500) && attempt < this.maxRetries) {
        let delay = this.retryDelayMs * Math.pow(2, attempt);
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After');
          if (retryAfter) {
            delay = parseInt(retryAfter, 10) * 1000;
          }
        }
        await _sleep(delay);
        attempt++;
        continue;
      }

      const errBody = await response.json().catch(() => response.text());
      lastError = createError(response.status, errBody);
      throw lastError;
    }

    throw lastError ?? createError(0, 'Max retries exceeded');
  }

  // ── Auth ──────────────────────────────────────────────────────────────────

  async getToken(req: TokenRequest): Promise<TokenResponse> {
    const result = await this.request<TokenResponse>('POST', '/v1/auth/token', req);
    this.token = result.access_token;
    return result;
  }

  // ── Grants ────────────────────────────────────────────────────────────────

  async listGrants(params?: { limit?: number; offset?: number; cursor?: string }): Promise<Grant[]> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.cursor) qs.set('cursor', params.cursor);
    else if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return this.request<Grant[]>('GET', `/v1/grants${query}`);
  }

  async createGrant(req: CreateGrantRequest): Promise<Grant> {
    return this.request<Grant>('POST', '/v1/grants', req);
  }

  async getGrant(id: string): Promise<Grant> {
    return this.request<Grant>('GET', `/v1/grants/${id}`);
  }

  async revokeGrant(id: string, reason?: string): Promise<Grant> {
    return this.request<Grant>('POST', `/v1/grants/${id}/revoke`, { reason });
  }

  // ── Grant Requests ────────────────────────────────────────────────────────

  async listGrantRequests(params?: { limit?: number }): Promise<GrantRequest[]> {
    const qs = params?.limit !== undefined ? `?limit=${params.limit}` : '';
    return this.request<GrantRequest[]>('GET', `/v1/grant-requests${qs}`);
  }

  async createGrantRequest(req: CreateGrantRequest): Promise<GrantRequest> {
    return this.request<GrantRequest>('POST', '/v1/grant-requests', req);
  }

  async approveGrantRequest(id: string, reason?: string): Promise<GrantRequest> {
    return this.request<GrantRequest>('POST', `/v1/grant-requests/${id}/approve`, { reason });
  }

  async denyGrantRequest(id: string, reason: string): Promise<GrantRequest> {
    return this.request<GrantRequest>('POST', `/v1/grant-requests/${id}/deny`, { reason });
  }

  async bulkApproveRequests(requestIds: string[], reason?: string): Promise<{ approved: number }> {
    return this.request('POST', '/v1/grant-requests/bulk-approve', { requestIds, reason });
  }

  // ── Audit Events ──────────────────────────────────────────────────────────

  async listAuditEvents(params?: { limit?: number; cursor?: string }): Promise<AuditEvent[]> {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.cursor) qs.set('cursor', params.cursor);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return this.request<AuditEvent[]>('GET', `/v1/audit-events${query}`);
  }

  async exportAuditLog(params?: { startDate?: string; endDate?: string }): Promise<string> {
    const qs = new URLSearchParams();
    if (params?.startDate) qs.set('start_date', params.startDate);
    if (params?.endDate) qs.set('end_date', params.endDate);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    const url = `${this.baseUrl}/v1/audit/export${query}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: this.getAuthHeader(),
    });
    if (!response.ok) throw createError(response.status, await response.text());
    return response.text();
  }

  async verifyAuditChain(params?: { startDate?: string; endDate?: string }): Promise<{
    valid: boolean;
    checked: number;
    brokenAt: string | null;
  }> {
    const qs = new URLSearchParams();
    if (params?.startDate) qs.set('start_date', params.startDate);
    if (params?.endDate) qs.set('end_date', params.endDate);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return this.request('GET', `/v1/audit/verify${query}`);
  }

  // ── Workspaces ────────────────────────────────────────────────────────────

  async listWorkspaces(): Promise<Workspace[]> {
    return this.request<Workspace[]>('GET', '/v1/workspaces');
  }

  async getWorkspace(id: string): Promise<Workspace> {
    return this.request<Workspace>('GET', `/v1/workspaces/${id}`);
  }

  async updateWorkspacePlan(id: string, planTier: string, rateLimitOverride?: number): Promise<Workspace> {
    return this.request<Workspace>('PATCH', `/v1/workspaces/${id}/plan`, {
      plan_tier: planTier,
      rate_limit_override: rateLimitOverride,
    });
  }

  // ── API Keys ──────────────────────────────────────────────────────────────

  async listApiKeys(): Promise<ApiKey[]> {
    return this.request<ApiKey[]>('GET', '/v1/api-keys');
  }

  async createApiKey(req: CreateApiKeyRequest): Promise<CreateApiKeyResponse> {
    return this.request<CreateApiKeyResponse>('POST', '/v1/api-keys', req);
  }

  async revokeApiKey(id: string): Promise<{ id: string; revokedAt: string; status: string }> {
    return this.request('DELETE', `/v1/api-keys/${id}`);
  }

  // ── Webhooks ──────────────────────────────────────────────────────────────

  async listWebhooks(): Promise<WebhookSubscription[]> {
    return this.request<WebhookSubscription[]>('GET', '/v1/webhooks');
  }

  async createWebhook(url: string, events: string[], secret: string): Promise<WebhookSubscription> {
    return this.request<WebhookSubscription>('POST', '/v1/webhooks', { url, events, secret });
  }

  async deleteWebhook(id: string): Promise<void> {
    return this.request<void>('DELETE', `/v1/webhooks/${id}`);
  }

  // ── GDPR ──────────────────────────────────────────────────────────────────

  async exportUserData(userId: string): Promise<{ jobId: string; status: string }> {
    return this.request('POST', `/v1/users/${userId}/export-data`);
  }

  async eraseUserData(userId: string): Promise<{ jobId: string; status: string }> {
    return this.request('POST', `/v1/users/${userId}/erase`);
  }

  // ── Exports ───────────────────────────────────────────────────────────────

  async exportGrantsCsv(): Promise<string> {
    const url = `${this.baseUrl}/v1/exports/grants.csv`;
    const response = await fetch(url, {
      headers: this.getAuthHeader(),
    });
    if (!response.ok) throw createError(response.status, await response.text());
    return response.text();
  }
}
