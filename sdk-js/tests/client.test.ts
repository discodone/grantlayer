/**
 * GrantLayer SDK tests — mock fetch, assert correct endpoints called.
 */

import { GrantLayerClient } from '../src/client';

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Map() as unknown as Headers,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('GrantLayerClient constructor', () => {
  it('creates client with baseUrl', () => {
    const client = new GrantLayerClient({ baseUrl: 'http://localhost:8000' });
    expect(client).toBeDefined();
  });

  it('strips trailing slash from baseUrl', () => {
    const client = new GrantLayerClient({ baseUrl: 'http://localhost:8000/' });
    expect(client).toBeDefined();
  });

  it('accepts apiKey option', () => {
    const client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      apiKey: 'gl_live_abc123',
    });
    expect(client).toBeDefined();
  });
});

describe('Auth', () => {
  it('calls /v1/auth/token on getToken', async () => {
    const client = new GrantLayerClient({ baseUrl: 'http://localhost:8000' });
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, { access_token: 'tok', token_type: 'bearer' })
    );

    const result = await client.getToken({ clientId: 'c', clientSecret: 's' });
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/auth/token',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result.access_token).toBe('tok');
  });

  it('sets token on client after getToken', async () => {
    const client = new GrantLayerClient({ baseUrl: 'http://localhost:8000' });
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, { access_token: 'my-token', token_type: 'bearer' })
    );
    await client.getToken({ clientId: 'c', clientSecret: 's' });

    // Next request should include Authorization header
    mockFetch.mockResolvedValueOnce(mockResponse(200, []));
    await client.listGrants();
    const [, opts] = mockFetch.mock.calls[1];
    expect((opts as RequestInit).headers as Record<string, string>).toMatchObject({
      Authorization: 'Bearer my-token',
    });
  });
});

describe('Grants', () => {
  let client: GrantLayerClient;

  beforeEach(() => {
    client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      token: 'test-token',
    });
  });

  it('calls GET /v1/grants on listGrants', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, []));
    await client.listGrants();
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/grants',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('passes limit query param', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, []));
    await client.listGrants({ limit: 50 });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('limit=50');
  });

  it('calls POST /v1/grants on createGrant', async () => {
    const grant = { id: 'g1', subjectId: 'u1', role: 'viewer', action: 'read', resource: 'doc', validFrom: '', validUntil: '', createdBy: '', reason: '', revoked: false, createdAt: '' };
    mockFetch.mockResolvedValueOnce(mockResponse(201, grant));
    const result = await client.createGrant({
      subjectId: 'u1',
      role: 'viewer',
      action: 'read',
      resource: 'doc',
      validFrom: '2026-01-01T00:00:00Z',
      validUntil: '2027-01-01T00:00:00Z',
      reason: 'test',
    });
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/grants',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result.id).toBe('g1');
  });

  it('calls POST /v1/grants/{id}/revoke on revokeGrant', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { id: 'g1', revoked: true }));
    await client.revokeGrant('g1', 'test revoke');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/grants/g1/revoke');
    expect((opts as RequestInit).method).toBe('POST');
  });
});

describe('API Keys', () => {
  let client: GrantLayerClient;

  beforeEach(() => {
    client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      token: 'test-token',
    });
  });

  it('calls POST /v1/api-keys on createApiKey', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, { id: 'k1', key: 'gl_live_abc', name: 'test', scopes: ['read_write'], workspaceId: 'ws1', createdAt: '' }));
    const result = await client.createApiKey({ name: 'test', scopes: ['read_write'] });
    expect(result.key).toBe('gl_live_abc');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/api-keys');
  });

  it('calls DELETE /v1/api-keys/{id} on revokeApiKey', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { id: 'k1', status: 'revoked', revokedAt: '2026-01-01T00:00:00Z' }));
    await client.revokeApiKey('k1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/api-keys/k1');
    expect((opts as RequestInit).method).toBe('DELETE');
  });
});

describe('Retry logic', () => {
  let client: GrantLayerClient;

  beforeEach(() => {
    client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      token: 'test-token',
      maxRetries: 2,
      retryDelayMs: 10,  // short delay for tests
    });
  });

  it('retries on 429', async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(429, { error: 'rate_limit_exceeded' }))
      .mockResolvedValueOnce(mockResponse(200, []));

    const result = await client.listGrants();
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result).toEqual([]);
  });

  it('retries on 500', async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(500, { error: 'internal_error' }))
      .mockResolvedValueOnce(mockResponse(200, []));

    const result = await client.listGrants();
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(result).toEqual([]);
  });

  it('throws after max retries', async () => {
    mockFetch
      .mockResolvedValue(mockResponse(500, { error: 'server_error' }));

    await expect(client.listGrants()).rejects.toMatchObject({ status: 500 });
  });

  it('throws immediately on 4xx (except 429)', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(403, { error: 'forbidden' }));

    await expect(client.listGrants()).rejects.toMatchObject({ status: 403 });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});

describe('GDPR endpoints', () => {
  let client: GrantLayerClient;

  beforeEach(() => {
    client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      token: 'test-token',
    });
  });

  it('calls POST /v1/users/{id}/export-data', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(202, { job_id: 'j1', status: 'queued' }));
    await client.exportUserData('user-1');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/users/user-1/export-data');
  });

  it('calls POST /v1/users/{id}/erase', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(202, { job_id: 'j2', status: 'completed' }));
    await client.eraseUserData('user-1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/users/user-1/erase');
    expect((opts as RequestInit).method).toBe('POST');
  });
});

describe('Workspaces', () => {
  let client: GrantLayerClient;

  beforeEach(() => {
    client = new GrantLayerClient({
      baseUrl: 'http://localhost:8000',
      token: 'test-token',
    });
  });

  it('calls GET /v1/workspaces on listWorkspaces', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, []));
    await client.listWorkspaces();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/workspaces');
  });

  it('calls PATCH /v1/workspaces/{id}/plan on updateWorkspacePlan', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { id: 'ws1', plan_tier: 'pro' }));
    await client.updateWorkspacePlan('ws1', 'pro');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/v1/workspaces/ws1/plan');
    expect((opts as RequestInit).method).toBe('PATCH');
  });
});
