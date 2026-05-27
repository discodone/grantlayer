# GL-143 server.py Route Decomposition Plan

**Status:** plan-only  
**Disposition target:** plan-only — no production code changed  
**Scope:** Create a route decomposition plan for `backend/src/server.py` that maps current responsibilities, proposes safe extraction boundaries, defines sequencing, risk controls, validation gates, and follow-up issues.

This is **NOT** implementation.  
This is **NOT** a refactor.  
This is **NOT** route movement.  
This is **NOT** endpoint/API behavior work.

---

## 1. Current responsibility map

`backend/src/server.py` (1,586 lines) is a monolithic file that currently owns the following responsibilities:

### 1.1 Runtime startup / ThreadingHTTPServer
- `run()` function (line 1564): initializes demo keypair, database, prints admin-token warnings, runs startup fail-closed gate (GL-089), and instantiates `ThreadingHTTPServer` (GL-140).
- Imports `ThreadingHTTPServer` from `http.server`.

### 1.2 Handler class / route dispatch
- `GrantLayerHandler(BaseHTTPRequestHandler)` (line 98): single subclass handling all HTTP verbs.
- `do_GET` (line 552): ~354 lines covering 20+ route branches including dashboard, health, readiness, grants, audit-events, challenges, operators/me, grant-requests, grant-executions, evidence, provenance, auditor reports, compliance gaps, agent-permissions.
- `do_POST` (line 908): ~654 lines covering 15+ route branches including grants, revoke, challenges, demo actions, grant-requests (create/approve/deny), agent-permissions, approvals, decision-provenance, auditor exports, policy-requirements, compliance readiness.
- `do_OPTIONS` (line 455): CORS preflight.
- No `do_PUT` or `do_DELETE` currently defined.

### 1.3 Request parsing / `_read_json`
- `_read_json()` (line 241): enforces Content-Length presence, validates integer Content-Length, enforces `MAX_JSON_BODY_BYTES` (1 MB), rejects empty body, parses JSON, rejects non-object JSON.
- Hardended by GL-090 (request body JSON hardening) and GL-142 (BytesIO test hack removal).

### 1.4 Response/error helpers
- `_send_json()` (line 223): deterministic JSON response with CORS headers.
- `_send_html()` (line 234): HTML response for dashboard.
- `_gl030_error()` (line 103): consistent additive error payload shape (`error`, `errorCode`, `reason`).
- `_handle_json_error()` (line 199): safe deterministic response for JSON parse failures.

### 1.5 Auth/admin/operator helpers
- `_require_admin()` (line 464): legacy admin-token auth with per-request SHA256 cache.
- `_require_operator()` (line 485): operator-model auth with role checks and per-request SHA256 cache.
- `_require_auth()` (line 506): unified dispatcher choosing operator vs legacy admin based on `ENABLE_OPERATOR_MODEL`.
- Auth error response consistency is governed by GL-087.

### 1.6 Rate limiting
- `_check_rate_limit()` (line 517): per-IP rate limiting using `_rate_limiter` (global `RateLimiter` instance).
- Returns 429 with `Retry-After` on rejection.
- Skips check when `client_address` is unavailable (test-mock safety).

### 1.7 Audit/provenance/compliance
- Audit events are read via `list_events()` at `/audit-events`.
- Evidence bundles, verification, provenance summaries, auditor reports, compliance gap reports, and completeness checks are all dispatched from `do_GET`.
- No direct audit write in `server.py`; writes happen in domain modules (`grants.py`, `grant_requests.py`, etc.).
- GL-139 added audit hash-chain write lock to protect concurrent appends.

### 1.8 Health/readiness
- `/health` (line 563): liveness probe, no auth.
- `/readiness` (line 570): readiness probe with runtime mode info, no auth.

### 1.9 Grant request / grant execution / evidence flows
- `/grants` (GET/POST), `/grants/{id}/revoke` (POST), `/grants/{id}/executions` (GET).
- `/grant-requests` (GET/POST), `/grant-requests/{id}/approve` (POST), `/grant-requests/{id}/deny` (POST).
- `/grant-executions` (GET), `/grant-executions/{id}` (GET).
- `/evidence/executions/{id}` (GET), `/evidence/executions/{id}/export` (GET), `/evidence/executions/{id}/verify` (GET), `/evidence/executions/{id}/completeness` (GET).
- `/provenance/executions/{id}/summary` (GET).
- `/auditor/reports/executions/{id}` (GET).
- `/compliance/gaps/executions/{id}` (GET).

### 1.10 Demo actions
- `/demo/tamper-grant/{id}` (POST): guarded by `ENABLE_DEMO_ENDPOINTS`.
- `/demo-action` (POST): guarded by `ENABLE_DEMO_ENDPOINTS` and auth.

### 1.11 Structured logging / correlation
- `_ensure_correlation_id()` (line 155): extracts or generates correlation ID from `X-Correlation-ID` / `X-Request-ID`.
- `_inject_correlation_header()` (line 168): sends `X-Correlation-ID` response header.
- `end_headers()` override (line 174): injects correlation header before finishing.
- `_log_event()` (line 179): emits safe structured log events via `safe_log` / `get_logger`.
- `_normalize_path()` (line 119): redacts dynamic IDs from log paths.

---

## 2. Proposed decomposition boundaries

The following boundaries are proposed for **future** extraction. No extraction is performed in GL-143.

### 2.1 Request parsing helpers
- `_read_json()`, `_missing()`, `_BodyParseError`, `_QueryParamError`, `_parse_int_query_param()`.
- These are pure helpers with no handler-state dependency beyond `self.headers` and `self.rfile`.
- **Extraction target:** `backend/src/request_parsing.py` or similar.
- **Risk:** Low — no behavior change if signature remains identical.

### 2.2 Response/error helpers
- `_send_json()`, `_send_html()`, `_gl030_error()`, `_handle_json_error()`.
- These depend on `self.send_response`, `self.send_header`, `self.end_headers`, `self.wfile`.
- **Extraction target:** `backend/src/response_helpers.py` or mixin.
- **Risk:** Low — thin wrappers around stdlib HTTP response primitives.

### 2.3 Auth boundary helpers
- `_require_admin()`, `_require_operator()`, `_require_auth()`.
- These depend on `self.headers`, `self._send_json`, `self._log_event`, and config flags.
- **Extraction target:** `backend/src/auth_boundary.py` or mixin.
- **Risk:** Medium — auth semantics must not drift (GL-087 gate).

### 2.4 Route dispatch / registry
- The large `if/elif` chains in `do_GET` and `do_POST`.
- A registry pattern (e.g., dict mapping path+method to handler function) would replace the chains.
- **Extraction target:** `backend/src/routes/__init__.py` or `backend/src/route_registry.py`.
- **Risk:** Medium-High — any dispatch bug affects all endpoints.

### 2.5 Domain route groups
- **Public/unauthenticated routes:** `/health`, `/readiness`, `/` (dashboard).
- **Read-only data routes:** `/grants`, `/grants/{id}`, `/audit-events`, `/challenges`, `/operators/me`, `/grant-requests`, `/grant-executions`, evidence/provenance/auditor/compliance reads.
- **Mutation routes:** `/grants` (POST), `/grants/{id}/revoke`, `/challenges` (POST), `/grant-requests` (POST), `/grant-requests/{id}/approve`, `/grant-requests/{id}/deny`, `/agent-permissions/evaluate`, `/agent-permissions/assignments/resolve`, `/approvals/*`, `/decision-provenance/v2/build`, `/auditor/exports/build`, `/policy-requirements/evaluate`, `/compliance/readiness/build`.
- **Demo routes:** `/demo/tamper-grant/{id}`, `/demo-action`.
- **Extraction target:** `backend/src/routes/public.py`, `backend/src/routes/read.py`, `backend/src/routes/write.py`, `backend/src/routes/demo.py`.
- **Risk:** Low for public routes; High for protected/admin/operator routes.

### 2.6 Runtime startup
- `run()` and module-level initialization (`_rate_limiter`, `_server_logger`, `DASHBOARD_PATH`).
- **Extraction target:** `backend/src/runtime.py` or `backend/src/server_main.py`.
- **Risk:** Low — startup is already a single function.

---

## 3. Safe sequencing

The following order is recommended for **future** implementation issues:

1. **GL-143 (this issue):** Plan only. No code changes.
2. **Characterization tests before movement:** Add tests that assert exact HTTP status, headers, and body for every route before any extraction. These tests must pass unchanged through all extraction steps.
3. **Extract pure helpers first:**
   - `_gl030_error()` — no dependencies.
   - `_send_json()` / `_send_html()` — minimal stdlib dependencies.
   - `_read_json()` — after GL-142 is merged and stable.
4. **Extract response/error helpers:** Group `_send_json`, `_send_html`, `_gl030_error`, `_handle_json_error` into a mixin or module.
5. **Extract request parsing helpers:** Group `_read_json`, `_missing`, `_parse_int_query_param`, `_validate_iso_timestamp`, `_validate_grant_dates`, `_validate_max_uses` into a module.
6. **Extract route dispatch:** Replace `if/elif` chains with a registry. Keep all handler bodies inline initially; only the dispatch table moves.
7. **Extract low-risk public routes:** `/health`, `/readiness`, `/dashboard` — no auth, no mutation, easy to verify.
8. **Extract read-only protected routes:** `/grants`, `/audit-events`, `/challenges`, evidence reads, etc.
9. **Extract protected/admin/operator mutation routes last:** These have the highest blast radius. Extract only after all prior steps are green and characterization tests are stable.
10. **Extract runtime startup:** Move `run()` and module-level state to a dedicated module.

---

## 4. Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Auth semantics drift** | High | Gate on GL-087 (auth error response consistency). Characterization tests must cover every auth failure path (401, 403, missing token, invalid token, role mismatch). |
| **Request parsing drift** | Medium | Gate on GL-090 (request body JSON hardening) and GL-124 (request payload shape validation). `_read_json` extraction must preserve exact error codes and status codes. |
| **Structured logging / correlation drift** | Medium | Gate on GL-113 / GL-117 integration. `_log_event`, `_ensure_correlation_id`, and `end_headers()` override must remain intact. Correlation ID must still propagate to response headers. |
| **Audit / hash-chain drift** | Medium | Gate on GL-139 (audit hash-chain write lock). No extraction must remove or weaken the write lock. Audit event emission paths must remain unchanged. |
| **ThreadingHTTPServer runtime drift** | Medium | Gate on GL-140. `run()` must continue to instantiate `ThreadingHTTPServer`. No extraction must reintroduce plain `HTTPServer`. |
| **Rate limit drift** | Low | `_check_rate_limit()` must preserve per-IP limits, 429 responses, and `Retry-After` headers. Test mocks that lack `client_address` must still be tolerated. |
| **OpenAPI / API behavior drift** | High | Gate on GL-045A (API contract consistency). Every extraction must be validated against the OpenAPI spec. No endpoint may change status codes, response shapes, or header behavior. |
| **Security boundary regression** | High | Run `backend/tests/test_security_boundary_regression.py` after every extraction step. Any failure is a stop-work signal. |

---

## 5. Validation gates for future implementation

Before any extraction issue is considered complete, the following gates must pass:

- **GL-087 auth error response consistency:** All auth failure paths return deterministic JSON with `error`, `errorCode`, `reason`. No raw exceptions leak.
- **GL-090 request body JSON hardening:** Content-Length is required, validated, and bounded. Malformed JSON returns 400 with safe error payload. Empty body returns 400. Non-object JSON returns 400.
- **GL-124 request payload shape validation:** Required fields are checked. String lengths are validated. ISO timestamps are validated. `maxUses` is validated.
- **GL-139 audit hash-chain write lock:** The `threading.RLock` around audit hash-chain append is present and effective. No concurrent request can produce duplicate `prev_hash`.
- **GL-140 ThreadingHTTPServer:** `run()` instantiates `ThreadingHTTPServer`, not plain `HTTPServer`. `daemon_threads` behavior is preserved.
- **GL-141 operator model default:** `ENABLE_OPERATOR_MODEL` defaults to `True`. Legacy admin-token path remains available but is not the default.
- **GL-142 read_json BytesIO cleanup:** `_read_json` contains no `isinstance(self.rfile, BytesIO)` branch. Test fixtures set `Content-Length` appropriately.
- **GL-045A API contract consistency:** OpenAPI spec matches actual endpoint behavior. No drift introduced by extraction.
- **Security boundary regression:** `backend/tests/test_security_boundary_regression.py` passes with zero failures.
- **Full backend suite on main:** All backend tests pass on `main` before any extraction branch is created.

---

## 6. Non-goals

- **No production code change** in GL-143.
- **No actual refactor** in GL-143.
- **No route movement** in GL-143.
- **No OpenAPI change** in GL-143.
- **No auth redesign** in GL-143.
- **No tenant/workspace implementation** in GL-143.
- **No dependency change** in GL-143.
- **No production SaaS claim** in GL-143.

---

## 7. Proposed follow-up issues

| Issue | Title | Scope |
|-------|-------|-------|
| **GL-143A** | Route characterization tests | Add exhaustive HTTP-level characterization tests for every route (status, headers, body shape) before any extraction. |
| **GL-143B** | Response/error helper extraction | Extract `_send_json`, `_send_html`, `_gl030_error`, `_handle_json_error` to a dedicated module or mixin. |
| **GL-143C** | Request parsing helper extraction | Extract `_read_json`, `_missing`, `_parse_int_query_param`, and validation helpers to a dedicated module. |
| **GL-143D** | Route dispatch registry plan/extraction | Replace `do_GET`/`do_POST` `if/elif` chains with a registry-based dispatch table. |
| **GL-143E** | Public route group extraction | Extract `/health`, `/readiness`, `/dashboard` to a public routes module. |
| **GL-143F** | Protected route group extraction | Extract read-only and mutation protected routes to domain route modules. |

---

## 8. Go/no-go criteria

An extraction issue is **go** only when **all** of the following are true:

1. **No behavior change:** Every characterization test passes without modification.
2. **Full suite green:** The full backend test suite passes.
3. **One extraction boundary per issue:** Each follow-up issue (GL-143A through GL-143F) addresses exactly one boundary.
4. **Rollback path clear:** The change can be reverted with a single `git revert` without breaking `main`.
5. **No OpenAPI drift unless intentionally planned:** Any OpenAPI change requires a separate issue (e.g., GL-045A) and explicit approval.

An extraction issue is **no-go** if any of the following occur:

- Any auth failure path changes its status code or error payload shape.
- Any request parsing error changes its status code or error code.
- `ThreadingHTTPServer` is replaced or bypassed.
- The audit hash-chain write lock is removed or weakened.
- Rate-limit behavior changes for any client.
- Structured logging or correlation ID propagation stops working.
- The security boundary regression suite fails.

---

## 9. Next issue

**GL-144 Tenant / Workspace Data Model Design**

After the route decomposition plan is accepted, the next architectural planning issue is the tenant/workspace data model design. This is a separate planning issue and does not overlap with GL-143 scope.
