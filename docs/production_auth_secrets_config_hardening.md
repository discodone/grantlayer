# GL-201 Production Auth / Secrets / Config Hardening

## Issue ID

GL-201

## Title

Production Auth / Secrets / Config Hardening

## Context

GL-200A, GL-200B, and GL-200C are merged internally. The tenant/workspace tracking block
is now sufficiently closed for the current roadmap stage.

GL-201 is the first dedicated hardening pass for production auth, secret handling, and
runtime configuration safety following the GL-200 tenant/workspace block.

GrantLayer remains:
- **Developer Preview** / **Controlled Preview** with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation is **not** overclaimed as production-complete

---

## Scope

GL-201 makes focused production auth/secrets/config hardening changes only.

**Allowed changes:**
- `backend/src/config.py` — placeholder/weak token detection, CORS localhost warning
- `backend/tests/test_gl201_production_auth_secrets_config_hardening.py` — GL-201 test suite
- `docs/production_auth_secrets_config_hardening.md` (this file)
- `docs/examples/gl201/production_auth_secrets_config_hardening.json`

## Non-Goals

GL-201 is **not**:
- Tenant/workspace implementation or expansion
- Admin tenant assignment UI
- Persistence/Postgres overhaul
- SDK/package work
- Public website work
- Public publish or visibility change
- Marketing copy polish
- Production SaaS readiness declaration
- Broad auth provider replacement
- Broad CORS redesign
- Broad refactor

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| docs/production_readiness_gap_report_v2.md | yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | yes |
| docs/controlled_preview_boundary_pack.md | yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | yes |
| docs/tenant_workspace_isolation_design_pack.md | yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | yes |
| docs/tenant_workspace_api_audit_regression_completion.md | yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | yes |
| README.md | yes |
| SECURITY.md | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes |
| backend/src/config.py | yes |
| backend/src/auth.py | yes |
| backend/src/server.py | yes |
| backend/src/operators.py | yes |
| backend/src/secret_sources.py | yes |
| backend/src/runtime_config.py | yes |

---

## Current State Summary

Prior to GL-201, `config.startup_errors()` checked for:
- Missing `GRANTLAYER_REQUIRE_ADMIN_TOKEN` enforcement
- Missing `GRANTLAYER_ADMIN_TOKEN` value
- Missing `GRANTLAYER_REQUIRE_CHALLENGE` enforcement
- Demo endpoints enabled in non-local mode

Gaps identified:
1. No rejection of **known placeholder/demo/weak admin tokens** in production-like modes
   (e.g., "admin", "token", "secret", "demo", "changeme", short strings)
2. No minimum token length enforcement in production-like modes
3. No bootstrap operator token validation in production-like modes
4. No CORS localhost-origin warning in production-like mode startup output
5. No test coverage explicitly verifying the above gaps

Auth, operator, and secret handling were already sound:
- `hmac.compare_digest` used for constant-time admin token comparison
- PBKDF2-HMAC-SHA256 with 600,000 iterations for operator token hashing
- Operator `to_dict()` never exposes `token_hash` or raw token
- `secret_sources.py` `describe_secret_source()` always redacts values
- Auth failure responses never echo back raw token values
- Startup errors never include raw secret values

---

## Hardening Summary

### 1. Production Mode Fail-Closed Config

**Added to `config.py`:**
- `_UNSAFE_PLACEHOLDER_TOKENS` frozenset of known unsafe placeholder values
- `_PROD_MIN_ADMIN_TOKEN_LENGTH = 16` minimum length for production-like modes
- `_token_is_unsafe_placeholder(token: str) -> bool` helper
- `startup_errors()` now rejects placeholder/short admin tokens **in production-like modes**
- `startup_errors()` now rejects placeholder bootstrap operator tokens **in production-like modes**
- `startup_warnings()` now warns when CORS origins include localhost in production-like mode
- Raw token values are **never** included in error messages or warnings

**Behavior:**
- `GRANTLAYER_RUNTIME_MODE in ("staging", "production")` triggers the placeholder/length check
- Local/test/demo modes retain existing behavior (short tokens acceptable for dev)
- The `server.run()` startup gate already blocks non-local/test mode on `startup_ok() == False`

### 2. Admin Token Safety (Verified Existing — No Changes Needed)

- `check_admin_token()` uses `hmac.compare_digest` for constant-time comparison
- Raw admin token never appears in response bodies, logs, or error messages
- Missing token with `REQUIRE_ADMIN_TOKEN=true` returns 403 (fail-closed)
- Wrong token returns 403 without echoing the attempted value
- No auth header with configured token returns 401

### 3. Operator Token Safety (Verified Existing — No Changes Needed)

- PBKDF2-HMAC-SHA256 with 600,000 iterations and random salt
- Fast SHA-256 lookup hash for O(1) DB narrowing before PBKDF2 verification
- `Operator.to_dict()` exposes only: operatorId, name, role, active, tenantId
- Raw token never stored beyond the creation moment — returned once, not persisted
- Expired token returns `operator_token_expired` reason (not auth_required)
- Auth failure responses never reveal the attempted token value

### 4. Demo/Dev/Test Flag Safety (Verified Existing — No Changes Needed)

- `ENABLE_DEMO_ENDPOINTS` defaults to False
- `ALLOW_PLAINTEXT_PRIVATE_KEY_FILE` defaults to False in production-like modes
- `REQUIRE_ADMIN_TOKEN` defaults to True in non-local/non-test modes
- Demo tamper endpoint (`/demo/tamper-grant/{id}`) returns 403 when flag is off
- `/demo-action` requires auth regardless of demo flag (auth-first design)

### 5. CORS / Public Exposure (Verified + Warning Added)

- CORS uses exact-match whitelist — no wildcard, no reflection of arbitrary origins
- Default CORS origins are localhost-only (`http://127.0.0.1:8765`, `http://localhost:8765`)
- **New:** `startup_warnings()` emits a warning when localhost CORS origins appear in
  production-like mode, prompting operators to set actual public origins
- No broad CORS redesign — change is minimal and targeted

### 6. Secret Leakage Checks

Tests added to verify:
- `startup_errors()` does not echo raw admin token
- `startup_warnings()` does not echo raw admin token
- `describe_runtime_config()` does not expose any secret
- Auth failure HTTP responses do not echo attempted token
- `admin_token_warning()` does not include raw token
- `Operator.to_dict()` does not include token_hash or raw token
- `describe_secret_source()` always returns `[REDACTED]` for present values
- `validate_required_secrets()` returns safe summary with no raw values

---

## Production-Mode Fail-Closed Behavior

| Scenario | Behavior |
|---|---|
| `GRANTLAYER_ADMIN_TOKEN` missing | `startup_errors()` → server refuses to start |
| `GRANTLAYER_ADMIN_TOKEN` empty | `startup_errors()` → server refuses to start |
| Admin token is placeholder in production-like mode | `startup_errors()` → server refuses to start |
| Admin token is shorter than 16 chars in production-like mode | `startup_errors()` → server refuses to start |
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN=false` | `startup_errors()` → server refuses to start |
| `GRANTLAYER_REQUIRE_CHALLENGE=false` | `startup_errors()` → server refuses to start |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true` | `startup_errors()` → server refuses to start |
| Bootstrap operator token is placeholder in production-like mode | `startup_errors()` → server refuses to start |
| CORS origins include localhost in production-like mode | `startup_warnings()` → warning only, not fatal |
| All checks pass | Server starts normally |

Local/test mode skips the startup gate in `server.run()` — placeholder tokens remain usable for development.

---

## Admin Token Safety

- Token comparison uses `hmac.compare_digest` (constant-time, no early exit)
- Raw token never appears in: error messages, logs, response bodies, startup output
- Missing token + enforce=true → `403 admin_token_required`
- Wrong token → `403 admin_token_invalid` (no token value in response)
- No auth header + token configured → `401 admin_token_required`
- Placeholder/short token in production-like mode → startup error (server won't start)

---

## Operator Token Safety

- PBKDF2-HMAC-SHA256 (600,000 iterations) for secure storage
- SHA-256 lookup hash for O(1) pre-filter before expensive PBKDF2 check
- `to_dict()` exposes only safe fields (operatorId, name, role, active, tenantId)
- Raw token returned once on creation, never retrievable afterwards
- Expired token → `401 operator_token_expired` (reason code, not token value)
- Unknown/invalid token → `401 operator_auth_required`
- Tenant binding (from GL-200B/C) preserved: `tenant_id` flows through `check_auth()`

---

## Demo/Dev/Test Boundary

- `ENABLE_DEMO_ENDPOINTS` defaults to False — tamper endpoint not accessible by default
- `/demo-action` endpoint: requires auth (401 without auth), not gated by demo flag
- `/demo/tamper-grant/{id}` endpoint: explicitly returns 403 when demo flag is off
- `ALLOW_PLAINTEXT_PRIVATE_KEY_FILE` defaults to False in production-like modes
- Local/test modes retain all dev-friendly defaults for test compatibility

---

## CORS / Public Exposure Boundary

- Exact string matching only for CORS origin allowlist
- No wildcard (`*`) allowed
- No reflection of arbitrary `Origin` headers
- Default origins: `http://127.0.0.1:8765` and `http://localhost:8765` (localhost only)
- New startup warning: if CORS origins include localhost in production-like mode
- Health and readiness endpoints: intentionally public, no auth required

---

## Secret Leakage Checks

All tested in `test_gl201_production_auth_secrets_config_hardening.py`:
- `startup_errors()` does not echo raw values
- `startup_warnings()` does not echo raw values
- `describe_runtime_config()` does not expose secrets
- Auth failure responses do not echo token values
- `Operator.to_dict()` does not include raw token or hash
- `describe_secret_source()` always redacts present values
- `validate_required_secrets()` returns safe summary

---

## Tenant/Workspace Regression Impact

GL-201 changes are additive hardening only. No tenant/workspace implementation was modified.

Regression verified:
- Operator tenant_id flows through `check_auth()` → `payload["tenant_id"]`
- Legacy admin-token fallback binds to `"demo"` tenant (GL-200B backward compat)
- Audit log `list_events(tenant_id=...)` filters by tenant (cross-tenant isolation)
- Audit hash chain fields (`eventHash`) remain intact
- Cross-tenant operator auth cannot authenticate for another tenant's resources

---

## Compatibility Notes

- GL-190 demo endpoint safety tests use short tokens (e.g., "test-token") in local mode.
  GL-201 placeholder check is **production-like mode only** — no regression in local/test mode.
- GL-089 startup_ok/startup_errors tests remain compatible: placeholder check is mode-gated.
- `startup_warnings()` emits CORS localhost warning in production-like mode — does not break
  any existing tests (warnings are informational only, not fatal).

---

## Remaining Gaps

The following gaps are **explicitly deferred** to future issues:

| Gap | Deferred To |
|-----|-------------|
| Secret rotation / expiry automation | Future GL |
| External secret manager integration (Vault/AWS Secrets Manager) | Future GL |
| Argon2id upgrade for operator token hashing | Future GL |
| Full secondary-path tenant isolation for evidence/provenance endpoints | Future GL |
| Workspace_id enforcement (currently nullable/reserved) | Future GL |
| Database-level secret encryption at rest | GL-202+ |

---

## Production Readiness Impact

GL-201 is a **hardening step** — not a production SaaS readiness declaration.

After GL-201:
- Production-like mode startup now explicitly rejects placeholder, demo, and weak admin tokens
- Bootstrap operator tokens are validated in production-like modes
- CORS localhost defaults trigger a startup warning in production-like mode
- Secret leakage tests provide regression coverage for future changes

GrantLayer **remains**:
- Developer Preview / Controlled Preview with strict boundaries
- Not ready for real customer data
- Not ready for private grant or institutional data
- Tenant/workspace isolation not production-complete

---

## Decision

`ready_for_merge` — internal branch only.

## Decision Rationale

All GL-201 objectives are met:
1. Production-mode fail-closed config hardened with placeholder/weak token rejection
2. Admin token behavior verified safe — no changes needed
3. Operator token behavior verified safe — no changes needed
4. Demo/dev/test flag boundary verified and documented
5. CORS/public exposure reviewed, CORS localhost warning added
6. Secret leakage check tests added
7. GL-200 tenant/workspace regression verified — no regressions
8. Documentation artifacts created

---

## Safety Confirmations

- No production SaaS claim made
- Tenant/workspace isolation not overclaimed as production-complete
- No real customer/private grant data readiness claimed
- Security-sensitive reports must route to GitHub Security Advisories (per SECURITY.md)
- No exploit details included in this report
- No real secrets included in tests, fixtures, or documentation
- GL-201 does not weaken any existing security boundary
- GL-201 does not weaken tenant/workspace isolation
- Internal branch only — no public push, no public publish, no visibility change
- No frontend/website/design changes
- No GitHub workflow changes

---

## Recommended Next Issues

- **GL-201 Merge** — merge internal branch to main after validation
- **GL-202 Persistence / Postgres / Migration Readiness** — after GL-201 is merged
