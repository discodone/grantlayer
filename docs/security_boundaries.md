# GrantLayer MVP — Security Boundaries

This document explicitly states what this MVP is and is not.

## This MVP is a local demonstrator only

- **No real privileged actions are executed.** The "demo action" endpoint returns a JSON response. It does not touch the operating system, files, network, or any external system.
- **No real admin rights are granted or used.** Grants exist only as rows in a local SQLite database.
- **No production use.** This MVP must not be used to gate access to real systems, customer environments, or any infrastructure.
- **No authentication.** There is no user login, session management, or token validation. Any caller can create grants or invoke demo actions. This is intentional for a demo — do not deploy publicly.
- **No secret handling.** No API keys, passwords, or credentials are processed, stored, or logged.
- **No blockchain.** No smart contracts, no wallet signatures, no testnet, no mainnet.
- **No compliance or security guarantee.** This MVP does not satisfy ISO 27001, SOC 2, GDPR, or any other security or compliance standard.
- **Local only.** The server binds to `127.0.0.1` by default. Do not expose it to a network or the internet.
- **No external services.** The MVP has zero external dependencies at runtime. Everything runs locally.

## Sprint 2A — Challenge/Proof Flow is NOT real authentication

- **The challenge UUID is not a cryptographic proof.** It is a randomly generated UUID stored in SQLite — not signed, not encrypted, not verified by any secret.
- **No signatures.** Ed25519 signatures come in Sprint 2B.
- **The challenge flow demonstrates the concept** of one-time-use tokens and replay protection only.
- A valid challenge merely proves the caller recently called `POST /challenges` with the matching subject/action/resource. Anyone with network access to the API can create a challenge.
- **Not a production auth mechanism.** Do not use to gate real system access.

## What the MVP demonstrates

| Concept | Demonstrated how |
|---------|-----------------|
| Temporary grant creation | POST /grants stores a grant with validFrom/validUntil |
| Policy evaluation | evaluateAccess() checks role, action, resource, time window, revocation |
| Fail-closed behavior | Any missing or non-matching grant results in denial |
| Grant revocation | POST /grants/:id/revoke sets revoked=true; subsequent checks are denied |
| Challenge/proof flow | POST /challenges creates a one-time UUID with TTL |
| Replay protection | Used challenges are permanently blocked (fail-closed on already_used) |
| Challenge expiry | Challenges expire after 5 minutes (fail-closed on expired) |
| Audit logging | Every access attempt (approved or denied) is written to audit_events with challenge metadata |
| Dashboard visibility | All endpoints exposed; served via dashboard |

## Demo-UX Sprint — `POST /demo/tamper-grant/:id` is DEMO ONLY

This endpoint intentionally corrupts a grant's `role` field in the database **without re-signing**. Its sole purpose is to let a live audience see the Ed25519 signature check catch a tampered grant.

**This endpoint must never exist in a production system.** Specifically:
- It writes directly to the grant record, bypassing all access controls
- It simulates a database-level attack (direct row modification)
- It is documented as demo-only in README, architecture, and this file
- It has no authentication or authorization check

In a real deployment, database access would be protected at the infrastructure level. This endpoint exists only because the demo has no auth layer (Sprint 2C adds a token).

## Sprint 2C — Demo Admin Token: Product-Mode in GL-020

Sprint 2C adds an optional static Bearer token (`GRANTLAYER_ADMIN_TOKEN`) for protecting state-changing endpoints (`POST /grants`, `POST /grants/:id/revoke`, `POST /demo/tamper-grant/:id` if demo endpoints are enabled).

- **This is not real authentication.** It is a single static token shared by all callers.
- **No user identity, no session management, no RBAC.** Anyone who knows the token can perform protected actions.
- **Token is passed via environment variable at runtime.** If not set, protected endpoints fall back to open demo mode with a warning — unless `GRANTLAYER_REQUIRE_ADMIN_TOKEN=true` is set, in which case they **fail closed**.
- **Not suitable for production.** Do not use to gate access to real systems.

### GL-020 Product-Mode Flags

| Flag | Default | When true |
|------|---------|-----------|
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | `false` | Protected endpoints fail closed without valid Bearer token. |
| `GRANTLAYER_REQUIRE_CHALLENGE` | `false` | `POST /demo-action` without challengeId fails with `challenge_required`. |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | Demo-only tamper endpoint is available. **Default is disabled.** |

- Startup warnings are printed for any unsafe default.
- Token values are never logged, returned in responses, or written to disk.
- `/health` reports presence booleans (`adminTokenConfigured`, `requireAdminToken`, etc.) but never the token value.

## What the MVP demonstrates (GL-020 extended)

| Concept | Demonstrated how |
|---------|-----------------|
| Temporary grant creation | POST /grants stores a signed grant with validFrom/validUntil |
| Policy evaluation | evaluateAccess() checks role, action, resource, time window, revocation |
| Fail-closed behavior | Any missing or non-matching grant results in denial |
| Grant revocation | POST /grants/:id/revoke sets revoked=true; subsequent checks are denied |
| Ed25519 grant signature | Every new grant is signed; signature verified before approval |
| Tamper detection | Modifying any signed field fails hash check → denied |
| Legacy unsigned grants | Unsigned grants are fail-closed by default (reason: grant_signature_missing) |
| Challenge/proof flow | POST /challenges creates a one-time UUID with TTL |
| Replay protection | Used challenges are permanently blocked (fail-closed on already_used) |
| Challenge expiry | Challenges expire after 5 minutes (fail-closed on expired) |
| Audit logging | Every access attempt written with challenge_result and grant_signature_result |
| Dashboard visibility | All endpoints exposed; signature info shown per grant and per audit event |

## Sprint 2E — Real Operator / Admin Model (GL-021)

GL-021 adds a lightweight operator identity and role-based authorization system. It is still local-only and demo-quality, but it replaces the single shared admin token with per-operator Bearer tokens and RBAC.

### Operator model flag

| Flag | Default | When true |
|------|---------|-----------|
| `GRANTLAYER_ENABLE_OPERATOR_MODEL` | `false` | Protected endpoints require a valid operator Bearer token and a matching role. |

### Bootstrap operator

When `ENABLE_OPERATOR_MODEL=true` and no operators exist, a bootstrap operator is created from environment variables:

- `GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN` — plaintext token, passed via env var only
- `GRANTLAYER_BOOTSTRAP_OPERATOR_ID` — operator ID (`bootstrap-admin`)
- `GRANTLAYER_BOOTSTRAP_OPERATOR_NAME` — display name
- `GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE` — role (`owner`)

If the bootstrap token is not set, no bootstrap operator is created.

### Bearer token auth

Operators authenticate with:

```text
Authorization: Bearer <operator-token>
```

### Roles

| Role | Permissions |
|------|-------------|
| `owner` | Full access (grants, revoke, demo tamper) |
| `grant_admin` | Create and revoke grants |
| `auditor` | Read-only |
| `demo_operator` | Use demo tamper endpoint (if `ENABLE_DEMO_ENDPOINTS=true`) |

### Legacy admin-token mode

When `ENABLE_OPERATOR_MODEL=false`, the system falls back to Sprint 2C behavior: a single static `GRANTLAYER_ADMIN_TOKEN` with no RBAC.

### Security properties

- **No plaintext token storage.** Operator tokens are hashed with PBKDF2-HMAC-SHA256 (600,000 iterations) and stored as `pbkdf2_sha256$600000$<salt>$<hash>`.
- **No secrets in responses.** Token hashes, salts, bootstrap tokens, env values, and secrets are never returned by the API.
- **`GET /operators/me`** returns safe metadata (`operatorId`, `name`, `role`, `active`) only. No `token_hash` field.
- **`GET /health`** exposes booleans only (`operatorModelEnabled`, `operatorsConfigured`). No token values or hashes.
- **hmac.compare_digest** is used for constant-time hash comparison to mitigate timing attacks.

### What GL-021 is NOT

- Not OAuth, SSO, or SAML.
- Not JWT or session cookies.
- Not a browser login flow or frontend authentication UI.
- Not a full IAM, LDAP, or SCIM integration.
- No token rotation, expiry, or revocation.
- No MFA.
- No password-based login — only pre-shared Bearer tokens.

## Future sprint additions (not in this MVP)

- Blockchain-anchored audit log (optional proof layer)
- Real authentication (OAuth2, mTLS, hardware token)
- Windows service integration
- Multi-approver workflow (4-eyes principle)
- Production database (PostgreSQL)
- Role-based access control for the API itself
- HSM/KMS key management for signing keys

## Sprint 2F — Real Approval Workflow (GL-022)

GL-022 adds a real approval workflow with a separate `grant_requests` table and state machine. It is not a multi-approval system and does not modify the `grants` table design.

### What GL-022 is

- A **separate GrantRequest entity** with its own `grant_requests` table.
- A **state machine**: `requested` → `approved` (creates grant) | `denied` | `revoked` | `expired`
- **Approval creates the actual grant.** The grant is signed and stored exactly like a grant created via `POST /grants`.

### What GL-022 is NOT

- **GrantRequest is separate from Grant.** There is no `approval_status` column on the `grants` table.
- **No `/approval-queue` endpoint.** Requests are listed via `GET /grant-requests` with optional `?status=` filter.
- **No `/grants/:id/approve` or `/grants/:id/reject` as the main API.** The primary API is `POST /grant-requests/:id/approve` and `POST /grant-requests/:id/deny`.
- **No multi-approval threshold.** A single `owner` or `grant_admin` can approve or deny a request. There is no 4-eyes or quorum requirement.

### Security boundaries for GL-022

- **Requester cannot approve or deny their own request.** The server checks `requested_by == operator_id` and returns `403` if they match.
- **Invalid or missing Bearer token fails closed.** `POST /grant-requests/:id/approve` and `POST /grant-requests/:id/deny` require a valid operator token.
- **Disabled operator fails closed.** If `ENABLE_OPERATOR_MODEL=false`, grant-request endpoints return `404 operator_model_disabled`.
- **Audit logs must not contain tokens, token hashes, salts, env values, or secrets.** Audit events for grant requests record the operator action and request ID only.
- **Legacy admin-token mode remains compatible.** When `ENABLE_OPERATOR_MODEL=false`, the system falls back to Sprint 2C behavior: a single `GRANTLAYER_ADMIN_TOKEN` with no RBAC.

### Authorization matrix (GL-022)

| Endpoint | `owner` | `grant_admin` | `auditor` | `demo_operator` |
|----------|---------|---------------|-----------|-----------------|
| `POST /grant-requests` | ✅ | ✅ | ❌ | ❌ |
| `GET /grant-requests` | ✅ | ✅ | ✅ | ❌ |
| `GET /grant-requests/:id` | ✅ | ✅ | ✅ | ❌ |
| `POST /grant-requests/:id/approve` | ✅ | ✅ | ❌ | ❌ |
| `POST /grant-requests/:id/deny` | ✅ | ✅ | ❌ | ❌ |

## Sprint 2G — Grant Execution Audit & Usage Binding (GL-023)

GL-023 adds a minimal execution/usage ledger that records every protected action attempt. It binds the actual execution to the authenticated operator, approved grant, original grant request, challenge result, and audit event.

### What GL-023 is

- **One row per protected action attempt.** Every call to `POST /demo-action` creates a `GrantExecution` record — whether approved, denied, or failed.
- **Immutable append-only ledger.** Executions are created by the system; there are no write endpoints for clients.
- **Read-only endpoints** for `owner`, `grant_admin`, and `auditor` roles:
  - `GET /grant-executions`
  - `GET /grant-executions/:id`
  - `GET /grants/:id/executions`
- **Linkage to related entities:**
  - `grantId` — the matched grant (if any)
  - `grantRequestId` — the original request (if the grant was created from an approved request)
  - `operatorId` — the authenticated operator (when operator model is enabled)
  - `challengeId` and `challengeResult` — the challenge used (if any)
  - `auditEventId` — the linked audit event
- **Three result values:**
  - `succeeded` — protected action executed
  - `denied` — policy, challenge, signature, auth, grant, or role condition blocked execution
  - `failed` — internal handler error after authorization path began

### What GL-023 is NOT

- **No usage caps.** There is no `max_uses`, `use_count`, or policy exhaustion logic.
- **No write endpoints.** Clients cannot create, update, or delete execution records.
- **No dashboard or frontend changes.** The ledger is exposed via read-only JSON endpoints only.
- **No approval_status on grants.** GL-023 does not modify the `grants` table design.
- **No external services.** Execution records are stored in the local SQLite database.
