# GrantLayer MVP — Architecture

## Stack decision

The task specified Node.js + TypeScript + Express as the preferred stack. Node.js 20 is available in the Debian 13 repo but requires `sudo apt install`, which is not available in the current environment. External download sources (nvm, nodejs.org) are also not accessible.

**Decision:** Python 3.13 stdlib + SQLite — both already installed on the VM. Zero external dependencies. This produces a more portable demo: runs anywhere Python 3.10+ is installed, with no `npm install` step.

## Component overview

```
┌─────────────────────────────────────────────────────────┐
│                  GrantLayer MVP                         │
│                                                         │
│  Dashboard (browser)                                    │
│   └─ dashboard/index.html  (vanilla JS, served by API)  │
│                                                         │
│  Backend (Python 3, stdlib + cryptography v43)          │
│   ├─ src/config.py         Centralized config (GL-020)  │
│   ├─ src/server.py         HTTP server + routing        │
│   ├─ src/policy_engine.py  evaluateAccess()             │
│   ├─ src/grants.py         Grant CRUD (SQLite)          │
│   ├─ src/grant_requests.py Grant Request workflow (GL-022) │
│   ├─ src/audit_log.py      Audit events (SQLite)        │
│   ├─ src/challenges.py     Challenge store + validation  │
│   ├─ src/demo_action.py    Protected action handler     │
│   ├─ src/crypto_signing.py Ed25519 sign + verify        │
│   ├─ src/models.py         Dataclasses                  │
│   └─ src/db.py             SQLite init + connection       │
│                                                         │
│  Data                                                   │
│   ├─ data/grantlayer.db            SQLite (WAL mode)    │
│   ├─ data/demo_ed25519_private_key.pem  (gitignored)    │
│   └─ data/demo_ed25519_public_key.pem  (gitignored)     │
│                                                         │
│  Tests                                                  │
│   ├─ tests/test_policy_engine.py  unittest (36 tests)   │
│   ├─ tests/test_admin_token.py     unittest (8 tests)   │
│   └─ tests/test_product_core.py    unittest (8 tests)   │
└─────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────┐
│                  GrantLayer MVP                         │
│                                                         │
│  Dashboard (browser)                                    │
│   └─ dashboard/index.html  (vanilla JS, served by API)  │
│                                                         │
│  Backend (Python 3, stdlib + cryptography v43)          │
│   ├─ src/config.py         Centralized config (GL-020)  │
│   ├─ src/server.py         HTTP server + routing        │
│   ├─ src/policy_engine.py  evaluateAccess()             │
│   ├─ src/grants.py         Grant CRUD (SQLite)          │
│   ├─ src/grant_requests.py Grant Request workflow (GL-022) │
│   ├─ src/audit_log.py      Audit events (SQLite)        │
│   ├─ src/challenges.py     Challenge store + validation  │
│   ├─ src/demo_action.py    Protected action handler     │
│   ├─ src/crypto_signing.py Ed25519 sign + verify        │
│   ├─ src/models.py         Dataclasses                  │
│   └─ src/db.py             SQLite init + connection       │
│                                                         │
│  Data                                                   │
│   ├─ data/grantlayer.db            SQLite (WAL mode)    │
│   ├─ data/demo_ed25519_private_key.pem  (gitignored)    │
│   └─ data/demo_ed25519_public_key.pem  (gitignored)     │
│                                                         │
│  Tests                                                  │
│   ├─ tests/test_policy_engine.py  unittest (36 tests)   │
│   ├─ tests/test_admin_token.py     unittest (8 tests)   │
│   └─ tests/test_product_core.py    unittest (8 tests)   │
└─────────────────────────────────────────────────────────┘
```

## Request flow — Demo Action (Sprint 2B)

```
Browser / curl
  │
  POST /demo-action  {subjectId, role, action, resource, challengeId?}
  │
  ▼
server.py  →  demo_action.handle_demo_action()
                │
                ├─ grants.list_grants()             reads SQLite
                ├─ policy_engine.evaluate_access()
                │     checks: subject / role / action / resource /
                │             time window / revocation
                │     returns: PolicyResult {approved, reason, matchedGrantId}
                │
                ├─ (if matchedGrantId present)
                │   crypto_signing.verify_grant_signature(matchedGrant)
                │     1. checks signature fields present → else "missing"
                │     2. recomputes canonical payload hash, compares stored hash
                │        → mismatch = "hash_mismatch" (fail-closed)
                │     3. verifies Ed25519 signature against public key
                │        → invalid = "invalid" (fail-closed)
                │     returns: valid | missing | invalid | hash_mismatch
                │     if not "valid" → deny (grant_signature_* reason)
                │
                ├─ (if challengeId present)
                │   challenges.validate_challenge()
                │     checks: exists / subject match / action match /
                │             resource match / not expired / not used
                │     on success: marks challenge as used (replay blocked)
                │     fail-closed: invalid challenge → deny even with valid grant
                │
                └─ audit_log.append_event()         writes SQLite
                       includes: challenge_*, grant_signature_result
                │
                ▼
          JSON response  {approved, message|reason, challengeId, challengeResult,
                          grantSignatureResult, auditEventId}
```

## Challenge flow — Sprint 2A

```
POST /challenges  {subjectId, action, resource}
  → Challenge stored with 5-min TTL, status=active
  ← {challengeId, expiresAt}

POST /demo-action  + challengeId
  → validate_challenge():
      not_found       → deny (fail-closed)
      expired         → deny
      already_used    → deny (replay blocked)
      mismatch        → deny (wrong subject/action/resource)
      valid           → mark used, allow grant check to proceed
  → audit event always written with challenge_result
```

## Policy Engine — fail-closed logic

```
evaluate_access(request, grants, now):
  candidates = [g for g in grants if g.subject_id == request.subject_id]
  if not candidates → DENY "No grant found"
  for grant in candidates:
    if role mismatch       → skip
    if action mismatch     → skip  (unless action == "*")
    if resource mismatch   → skip  (unless resource == "*")
    if now < valid_from    → DENY "not yet valid"
    if now > valid_until   → DENY "expired"
    if grant.revoked       → DENY "revoked"
    if grant.max_uses is not None and grant.use_count >= grant.max_uses
                           → DENY "grant_usage_exhausted"
    → APPROVE
  → DENY "No matching grant"
```

### Atomic usage consumption (GL-024)

After `evaluate_access()` returns `approved=true`, the protected action handler performs an atomic consumption step:

1. `try_consume_grant_use(grant_id)` runs an `UPDATE` that increments `use_count` only if `max_uses IS NULL OR use_count < max_uses`.
2. If the update affects zero rows (race condition or pre-check miss), the result is rewritten to `approved=false, reason="grant_usage_exhausted"`.
3. The action proceeds only if consumption succeeds.

This ensures:
- **No over-use** even under concurrent requests.
- **Denied/failed attempts do not increment usage.** Consumption happens only after all other checks pass.
- **Exhausted attempts are fully logged.** A denied `GrantExecution` and audit event are created with `error_code = "grant_usage_exhausted"`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Service health |
| GET | /grants | List all grants |
| GET | /grants/:id | Get a single grant (includes signatureValid) |
| POST | /grants | Create a grant |
| POST | /grants/:id/revoke | Revoke a grant |
| POST | /grant-requests | Create a grant request (GL-022) |
| GET | /grant-requests | List grant requests (GL-022) |
| GET | /grant-requests/:id | Get a single grant request (GL-022) |
| POST | /grant-requests/:id/approve | Approve a grant request and create the grant (GL-022) |
| POST | /grant-requests/:id/deny | Deny a grant request (GL-022) |
| POST | /challenges | Create a challenge (5-min TTL) |
| GET | /challenges | List all challenges |
| POST | /demo-action | Run a protected demo action (optional challengeId) |
| GET | /audit-events | List audit events |
| GET | / | Dashboard |
| POST | /demo/tamper-grant/:id | **Demo only** — corrupt a grant without re-signing. **Disabled by default** (`ENABLE_DEMO_ENDPOINTS=false`). Must be explicitly enabled. |
| GET | /operators/me | Return the currently authenticated operator's safe metadata (no token hash). Only available when `ENABLE_OPERATOR_MODEL=true`. |

## Product-Mode Configuration (GL-020)

The MVP now supports opt-in product-mode hardening via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | `false` | When `true`, protected endpoints fail closed without a valid Bearer token. |
| `GRANTLAYER_ADMIN_TOKEN` | *(empty)* | The static Bearer token for admin endpoints. Token value is never logged or returned. |
| `GRANTLAYER_REQUIRE_CHALLENGE` | `false` | When `true`, `POST /demo-action` without `challengeId` denies with `challenge_required`. |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | When `false` (default), `POST /demo/tamper-grant/:id` returns `403 demo_endpoints_disabled`. |
| `GRANTLAYER_HOST` | `127.0.0.1` | Bind address. |
| `GRANTLAYER_PORT` | `8765` | HTTP port. |
| `GRANTLAYER_DB` | *(empty)* | SQLite database path. If empty, a default path is used. |

### Startup warnings

If any unsafe default is active, the server prints explicit warnings at startup:
- `ENABLE_DEMO_ENDPOINTS=true` — warns about exposed demo-only tamper endpoint.
- `REQUIRE_ADMIN_TOKEN=false` — warns that protected endpoints are not mandatory.
- `REQUIRE_CHALLENGE=false` — warns that demo-action accepts requests without challenge.
- `ADMIN_TOKEN` missing — warns that admin endpoints are unprotected.

These warnings are printed to stdout and never contain token values.

## Operator Model (GL-021)

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_ENABLE_OPERATOR_MODEL` | `false` | When `true`, use per-operator Bearer tokens and RBAC. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN` | *(empty)* | Plaintext token for the bootstrap operator. Never stored plaintext. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_ID` | `bootstrap-admin` | ID of the bootstrap operator. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_NAME` | `Bootstrap Admin` | Display name. |
| `GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE` | `owner` | Role assigned to the bootstrap operator. |

### Auth behavior

1. **Legacy admin-token mode** (`ENABLE_OPERATOR_MODEL=false`): Uses `GRANTLAYER_ADMIN_TOKEN` with no RBAC.
2. **Operator mode** (`ENABLE_OPERATOR_MODEL=true`): Requires `Authorization: Bearer <token>` header. The token is verified against PBKDF2-HMAC-SHA256 hashes stored in the `operators` table.
3. **Role checks**: Endpoints enforce role requirements. For example, `POST /grants` requires `owner` or `grant_admin`. `POST /demo/tamper-grant/:id` requires `owner` or `demo_operator`.

### Role authorization matrix (GL-021 + GL-022)

| Role | `POST /grants` | `POST /grants/:id/revoke` | `GET /grants` | `GET /audit-events` | `POST /grant-requests` | `GET /grant-requests` | `POST /grant-requests/:id/approve` | `POST /grant-requests/:id/deny` | `POST /demo/tamper-grant/:id` |
|------|----------------|---------------------------|---------------|---------------------|------------------------|-----------------------|------------------------------------|---------------------------------|-------------------------------|
| `owner` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `grant_admin` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `auditor` | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `demo_operator` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |

## Grant Request Approval Workflow (GL-022)

GL-022 introduces a real approval workflow as a separate lifecycle from grants. A grant request is created, reviewed, and either approved (which creates an actual signed grant) or denied.

### Design decision: separate entity

- **GrantRequest lives in its own `grant_requests` table.** It is never mixed into the `grants` table.
- **No `approval_status` on grants.** The rejected design proposed adding `approval_status` to the `grants` table. GL-022 explicitly does not do this.
- **Approval creates a real Grant.** The newly created grant is signed with Ed25519 exactly like a grant created via `POST /grants`.

### GrantRequest state machine

```
┌───────────┐    ┌───────────┐    ┌───────────┐
│ requested │───→│ approved  │───→│ revoked   │
└───────────┘    └───────────┘    └───────────┘
      │               │
      ▼               │
┌───────────┐         │
│  denied   │         │
└───────────┘         │
                      │
                 ┌────┴────┐
                 │  grant  │  ← actual Grant created
                 └─────────┘
```

| Transition | Trigger | Result |
|------------|---------|--------|
| `requested` → `approved` | `POST /grant-requests/:id/approve` by `owner` or `grant_admin` | Creates signed Grant. Writes `grant_request_created`, `grant_request_approved`, `grant_created_from_request` audit events. |
| `requested` → `denied` | `POST /grant-requests/:id/deny` by `owner` or `grant_admin` | No grant created. Writes `grant_request_denied` audit event. |
| `approved` → `revoked` | Internal revocation | Revokes linked grant. Writes `revoke_grant_request` audit event. |
| `requested` → `expired` | Background job (`expire_old_requests`) after 24h | No grant created. No audit event. |

### Request → Approve → Grant creation flow

```
POST /grant-requests  {subjectId, role, action, resource, validFrom, validUntil, reason}
  → validate operator role (owner or grant_admin)
  → create_grant_request() inserts row into grant_requests with status='requested'
  → audit_log: grant_request_created
  ← {id, subject_id, role, action, resource, status: 'requested', ...}

POST /grant-requests/:id/approve  (by a different operator)
  → validate operator role (owner or grant_admin)
  → check requested_by != operator_id  (self-approval blocked)
  → BEGIN TRANSACTION
     1. grants.create_grant()  → inserts signed row into grants
     2. UPDATE grant_requests SET status='approved', approved_by=..., grant_id=...
     3. audit_log: grant_request_approved
     4. audit_log: grant_created_from_request
  → COMMIT
  ← {ok: true, request: {..., status: 'approved'}, grant: {...}}

POST /grant-requests/:id/deny  (by a different operator)
  → validate operator role (owner or grant_admin)
  → check requested_by != operator_id  (self-denial blocked)
  → UPDATE grant_requests SET status='denied', denied_by=..., denial_reason=...
  → audit_log: grant_request_denied
  ← {ok: true, request: {..., status: 'denied'}}
```

### GL-022 audit events

| Event | When | Payload |
|-------|------|---------|
| `grant_request_created` | On `POST /grant-requests` | `subject_id=operator_id`, `resource='grant_request/{id}'`, `approved=true` |
| `grant_request_approved` | On `POST /grant-requests/:id/approve` | `subject_id=operator_id`, `resource='grant_request/{id}'`, `approved=true` |
| `grant_created_from_request` | On `POST /grant-requests/:id/approve` (same transaction) | `subject_id=operator_id`, `resource='grant_request/{id}'`, `approved=true` |
| `grant_request_denied` | On `POST /grant-requests/:id/deny` | `subject_id=operator_id`, `resource='grant_request/{id}'`, `approved=true` |

Note: `approved=true` in these audit events means the action itself was permitted, not that a grant was approved.

### Data model additions

**GrantRequest** (GL-022)

```
id, subject_id, role, action, resource,
valid_from, valid_until,
requested_by, reason, status,
approved_by, approved_at,
denied_by, denied_at, denial_reason,
revoked_by, revoked_at, revoked_reason,
grant_id,
created_at, updated_at
```

| Field | Meaning |
|-------|---------|
| `status` | `requested` \| `approved` \| `denied` \| `revoked` \| `expired` |
| `requested_by` | Operator ID who created the request |
| `grant_id` | FK-like reference to the grant created on approval (nullable) |

## Tamper & Verify Flow (Demo-UX Sprint)

```
Dashboard "Tamper & Verify Demo" section:

  Step 1 — Tamper:
    POST /demo/tamper-grant/:id
      → DB UPDATE grants SET role = 'tampered-role'  (no re-sign)
      ← {ok, tamperedField, oldValue, newValue, subjectId, action, resource}

  Step 2 — Verify (blocked):
    POST /demo-action  {subjectId, role='tampered-role', action, resource}
      → policy_engine finds grant  (role now matches 'tampered-role')
      → verify_grant_signature():
          stored payloadHash was computed with role='technician'
          current canonical has role='tampered-role'
          → sha256(current) ≠ stored hash → "hash_mismatch"
      → approved: false, reason: grant_payload_hash_mismatch
      → audit event: grant_signature_result = hash_mismatch
```

## Ed25519 Crypto Flow (Sprint 2B)

```
Grant creation (POST /grants):
  1. Grant stored in DB (id, subject_id, role, action, resource, ...)
  2. canonical_grant_payload(grant) → sorted key=value lines, UTF-8
     Fields included: action, createdBy, id, reason, resource, role,
                       subjectId, validFrom, validUntil
     Fields excluded: revocation fields, signature, payloadHash, signingKeyId
     (Revocation excluded so a grant can be revoked without re-signing)
  3. Ed25519PrivateKey.sign(payload) → signature_bytes
  4. SHA-256(payload) → payload_hash
  5. DB UPDATE: signature=hex(sig), signing_key_id="demo-ed25519-v1",
                payload_hash=hash_hex

Verification (POST /demo-action):
  1. Load matched grant from DB (includes signature, signing_key_id, payload_hash)
  2. If any of the three fields is missing → "missing" (legacy unsigned grant)
  3. Recompute SHA-256(canonical_grant_payload(grant)) → expected_hash
  4. If stored payload_hash != expected_hash → "hash_mismatch" (field tampered)
  5. Ed25519PublicKey.verify(sig_bytes, payload)
     → InvalidSignature → "invalid"
     → success → "valid"

Key management (DEMO ONLY):
  data/demo_ed25519_private_key.pem  — unencrypted, gitignored
  data/demo_ed25519_public_key.pem   — gitignored
  ensure_demo_keypair() — generates on first run, idempotent
  signing_key_id = "demo-ed25519-v1" (single key, no rotation)
```

## Data model

**Grant** (Sprint 2B adds signature fields; GL-024 adds usage limit fields)
```
id, subject_id, role, action, resource,
valid_from, valid_until, created_by, reason,
revoked (bool), revoked_by, revoked_reason, revoked_at,
created_at,
signature (TEXT), signing_key_id (TEXT), payload_hash (TEXT),
max_uses (INTEGER, nullable), use_count (INTEGER, default 0)
```

**Operator** (Sprint 2E — GL-021)
```
id, name, role, token_hash, active, created_at
```

Token hashes use PBKDF2-HMAC-SHA256 with 600,000 iterations:
`pbkdf2_sha256$600000$<salt>$<hash>`

Token values are never stored plaintext.

**Challenge** (Sprint 2A)
```
id, subject_id, action, resource,
created_at, expires_at, used_at,
status: active | used | expired
```

**AuditEvent** (Sprint 2B adds grant_signature_result)
```
id, timestamp, subject_id, role, action, resource,
approved (bool), reason, matched_grant_id,
challenge_id, challenge_present (bool), challenge_result,
grant_signature_result
```

challenge_result values: valid | missing | not_found | expired | already_used | mismatch | legacy_mode

grant_signature_result values: valid | missing | invalid | hash_mismatch | not_checked

## Grant Execution Ledger (GL-023)

GL-023 adds a minimal execution/usage ledger that records every protected action attempt. It binds execution to operator, grant, grant request, challenge, and audit event.

### Design decision: one row per attempt

- Every call to `POST /demo-action` creates a `GrantExecution` record.
- The record is created **before** the action result is known, then updated with the outcome.
- Success, denial, and internal failure paths are all recorded.

### GrantExecution entity

```
id, grant_id, grant_request_id, operator_id,
action, resource,
challenge_id, challenge_result,
policy_result, result, error_code,
executed_at, audit_event_id, metadata_json
```

### Result values

| Value | Meaning |
|-------|---------|
| `succeeded` | Protected action executed |
| `denied` | Policy, challenge, signature, auth, grant, or role condition blocked execution |
| `failed` | Internal handler error after authorization path began |

### Linkage

- `grant_id` → the matched grant (if any)
- `grant_request_id` → the original request (reverse lookup via `grant_requests.grant_id`)
- `operator_id` → the authenticated operator (when operator model is enabled)
- `challenge_id` / `challenge_result` → the challenge used (if any)
- `audit_event_id` → the audit event written for this attempt

### Read-only endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /grant-executions` | owner, grant_admin, auditor | List executions (filterable by `grantId`, `operatorId`) |
| `GET /grant-executions/:id` | owner, grant_admin, auditor | Get single execution |
| `GET /grants/:id/executions` | owner, grant_admin, auditor | List executions for a specific grant |

### What GL-023 does NOT include

- ~~No usage caps (`max_uses`, `use_count`)~~ Addressed by GL-024.
- No write endpoints for executions (append-only)
- No dashboard or frontend changes
- No `approval_status` on grants

## GL-024 — Grant Usage Limits & Exhaustion Policy

GL-024 adds optional usage limits to the `Grant` entity. It uses the `GrantExecution` ledger (GL-023) to track every exhausted attempt.

### Data model additions

**Grant** fields added by GL-024:

| Field | Type | Meaning |
|-------|------|---------|
| `max_uses` | `INTEGER` (nullable) | Usage cap. `null` = unlimited. |
| `use_count` | `INTEGER` (default 0) | Successful executions so far. |

Derived from the two:
- `remainingUses` = `max_uses - use_count` (when `max_uses` is set).

### Relation to GrantExecution ledger

- Every protected action attempt creates a `GrantExecution` record (GL-023).
- Successful executions consume one use and record `result = "succeeded"`.
- Exhausted attempts record `result = "denied"` and `error_code = "grant_usage_exhausted"`.
- Denied and failed attempts do **not** increment `use_count`, but they still create `GrantExecution` records.

### Policy flow with usage limits

```
POST /demo-action
  ├─ Existing checks remain (role, action, resource, time window, revocation)
  ├─ Exhaustion pre-check: if max_uses is set and use_count >= max_uses → DENY
  ├─ Signature verification (Sprint 2B)
  ├─ Challenge validation (Sprint 2A)
  ├─ Atomic consumption: UPDATE use_count = use_count + 1 WHERE use_count < max_uses
  │   → if 0 rows updated → DENY "grant_usage_exhausted"
  └─ Action executed → GrantExecution.result = "succeeded"
```

### Response fields

Grant responses (`GET /grants`, `GET /grants/:id`) include:

| Field | Type | Meaning |
|-------|------|---------|
| `maxUses` | `integer \| null` | Usage limit from `max_uses`. |
| `useCount` | `integer` | Current `use_count`. |
| `remainingUses` | `integer \| null` | `maxUses - useCount` when limited. |

### `grant_usage_exhausted`

- **Policy engine reason:** `grant_usage_exhausted` — returned when `max_uses` is set and `use_count >= max_uses`.
- **Audit event:** `approved = false`, `reason = "grant_usage_exhausted"`.
- **GrantExecution:** `result = "denied"`, `error_code = "grant_usage_exhausted"`.
- **Response:** `POST /demo-action` returns `"approved": false`, `"reason": "grant_usage_exhausted"`.

### Updated role authorization matrix (GL-021 + GL-022 + GL-023 + GL-024)

| Role | `POST /grants` | `POST /grants/:id/revoke` | `GET /grants` | `GET /audit-events` | `POST /grant-requests` | `GET /grant-requests` | `POST /grant-requests/:id/approve` | `POST /grant-requests/:id/deny` | `POST /demo/tamper-grant/:id` | `GET /grant-executions` |
|------|----------------|---------------------------|---------------|---------------------|------------------------|-----------------------|------------------------------------|--------------------------------|-------------------------------|-------------------------|
| `owner` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `grant_admin` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| `auditor` | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `demo_operator` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
