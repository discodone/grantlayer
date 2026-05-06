# GrantLayer MVP — Sprint 2B

A local demonstrator for action-level temporary access control with policy evaluation, challenge/replay protection, and audit logging.

## What is this MVP?

GrantLayer is an **action-level approval layer** for temporary privileged IT actions in MSP environments.
Instead of asking "who can log in?" — GrantLayer asks "who may perform this specific action, right now, under these conditions?"

This MVP demonstrates the core concept: a protected action can only execute if a valid, non-expired, non-revoked grant exists that matches the subject, role, action, and resource — and every attempt is logged to an immutable audit trail.

## What does it show?

- Creating time-limited grants (subject, role, action, resource, time window)
- Policy evaluation: fail-closed (any ambiguity → denied)
- Grant revocation
- **Challenge/proof flow (Sprint 2A):** one-time-use challenge UUIDs with 5-minute TTL
- **Replay protection:** a used challenge is permanently blocked (fail-closed)
- **Ed25519 grant signatures (Sprint 2B):** every grant is signed on creation; signature is verified before each demo action
- **Tamper detection:** modifying any grant field invalidates the signature → action is blocked
- Protected demo action (approved or blocked by policy + signature + challenge)
- Audit log for every attempt — approved and denied, with challenge and signature metadata
- Live dashboard in the browser

### Sprint 2B — Ed25519 grant signatures (DEMO ONLY)

- Private key is stored unencrypted at `data/demo_ed25519_private_key.pem`
- **Do not use this key in production**
- Key files are gitignored (`data/*.pem`)
- Single key ("demo-ed25519-v1"), no key rotation, no HSM, no PKI
- The canonical payload (the signed content) covers 9 immutable fields: id, subjectId, role, action, resource, validFrom, validUntil, createdBy, reason
- Revocation fields are NOT in the canonical payload — revocation is possible without invalidating the original signature

## What it explicitly does NOT show

- No real privileged actions (no filesystem, OS, or network changes)
- No real admin rights
- No blockchain / smart contracts / testnet
- No authentication / JWT / TLS
- No production use
- No HSM, no key management, no PKI
- See [docs/security_boundaries.md](docs/security_boundaries.md) for full list

## Stack

- **Backend:** Python 3.13, stdlib + `cryptography` v43.0.0 (Ed25519)
- **Frontend:** Vanilla HTML/JS, served by the backend — no build step
- **Database:** SQLite (WAL mode), stored in `data/grantlayer.db`
- **Tests:** Python `unittest` (stdlib)

> Node.js was not available without sudo on this VM. Python stdlib produces an identical demo with zero external dependencies.

## Setup

No installation required. Python 3.10+ and stdlib are sufficient.

```bash
git clone <repo>  # or just copy the directory
cd grantlayer-mvp
```

## Start backend

```bash
cd /home/adminuser/projects/grantlayer-mvp
python3 -m backend
```

Or via script:
```bash
./scripts/dev.sh
```

Backend starts on `http://127.0.0.1:8765`. Dashboard opens at the same URL.

Custom host/port:
```bash
GRANTLAYER_HOST=0.0.0.0 GRANTLAYER_PORT=9000 python3 -m backend
```

## Start dashboard

Open `http://127.0.0.1:8765/` in a browser after starting the backend.
The dashboard auto-refreshes every 10 seconds.

## Run tests

```bash
cd /home/adminuser/projects/grantlayer-mvp
python3 -m unittest discover -s backend/tests -v
```

Or via script:
```bash
./scripts/test.sh
```

Expected output: **132 tests, 0 failures.**

## Configuration (GL-020 Product Hardening)

The MVP supports opt-in product-mode hardening via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | `false` | Require valid Bearer token on protected endpoints. |
| `GRANTLAYER_ADMIN_TOKEN` | *(empty)* | Static admin Bearer token. Never logged or returned. |
| `GRANTLAYER_REQUIRE_CHALLENGE` | `false` | Require `challengeId` on `POST /demo-action`. |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | Enable the demo tamper endpoint. Default is **disabled**. |
| `GRANTLAYER_HOST` | `127.0.0.1` | Bind address. |
| `GRANTLAYER_PORT` | `8765` | HTTP port. |

### Product-mode vs demo-mode

**Demo-mode (default):** All unsafe defaults are allowed. The server explicitly prints warnings at startup.
**Product-mode:** Set `REQUIRE_ADMIN_TOKEN=true`, `REQUIRE_CHALLENGE=true`, and `ENABLE_DEMO_ENDPOINTS=false` for enforced hardening.

Note: this is still NOT production-ready. See [docs/security_boundaries.md](docs/security_boundaries.md) for what is missing (TLS, HSM/KMS, real IAM, etc.).

## Run the 3-minute demo

One command starts the server and walks through the full GrantLayer flow:

```bash
chmod +x scripts/demo.sh
./scripts/demo.sh
```

This demonstrates:
- Health check, grant creation, Ed25519 signatures
- Challenge/replay protection, grant revocation
- Permission checks, tamper detection, audit logging

For details see [docs/demo_script.md](docs/demo_script.md).

## Example walkthrough

### 1. Create a grant (curl)
```bash
curl -s -X POST http://127.0.0.1:8765/grants \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "tech-01",
    "role": "technician",
    "action": "restart-service",
    "resource": "customer-env-a",
    "validFrom": "2026-05-02T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "createdBy": "admin",
    "reason": "Scheduled maintenance"
  }' | python3 -m json.tool
```

### 2. Demo action — approved
```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-01","role":"technician","action":"restart-service","resource":"customer-env-a"}' \
  | python3 -m json.tool
```
Expected: `"approved": true`

### 3. Revoke the grant
```bash
curl -s -X POST http://127.0.0.1:8765/grants/<ID>/revoke \
  -H "Content-Type: application/json" \
  -d '{"revokedBy":"admin","reason":"Emergency stop"}' \
  | python3 -m json.tool
```

### 4. Demo action — blocked
```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-01","role":"technician","action":"restart-service","resource":"customer-env-a"}' \
  | python3 -m json.tool
```
Expected: `"approved": false`, reason: `"Grant ... has been revoked"`

### 5. Check audit log
```bash
curl -s http://127.0.0.1:8765/audit-events | python3 -m json.tool
```

## Sprint 2A — Challenge/Proof Flow

```bash
# 1. Create a challenge (5-minute TTL)
curl -s -X POST http://127.0.0.1:8765/challenges \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-1","action":"modify-config","resource":"customer-a/server-1"}' \
  | python3 -m json.tool
# → {"challengeId": "...", "expiresAt": "..."}

# 2. Use the challenge in a demo action
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-1","role":"technician","action":"modify-config","resource":"customer-a/server-1","challengeId":"..."}' \
  | python3 -m json.tool
# → {"approved": true, "challengeId": "..."}

# 3. Try to reuse the same challenge → blocked
# → {"approved": false, "challengeResult": "already_used"}

# 4. List challenges (with status)
curl -s http://127.0.0.1:8765/challenges | python3 -m json.tool
```

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /grants | List all grants |
| GET | /grants/:id | Get a single grant (includes signatureValid) |
| POST | /grants | Create a grant (optional `maxUses`) |
| POST | /grants/:id/revoke | Revoke a grant |
| POST | /grant-requests | Create a grant request (GL-022) |
| GET | /grant-requests | List grant requests (GL-022) |
| GET | /grant-requests/:id | Get a single grant request (GL-022) |
| POST | /grant-requests/:id/approve | Approve a grant request and create the grant (GL-022) |
| POST | /grant-requests/:id/deny | Deny a grant request (GL-022) |
| POST | /challenges | Create a challenge (5-min TTL) |
| GET | /challenges | List all challenges |
| POST | /demo-action | Run protected demo action (optional challengeId) |
| GET | /audit-events | List audit events |
| GET | /grant-executions | List grant executions (GL-023) — owner, grant_admin, auditor only |
| GET | /grant-executions/:id | Get a single grant execution (GL-023) — owner, grant_admin, auditor only |
| GET | /grants/:id/executions | List executions for a grant (GL-023) — owner, grant_admin, auditor only |
| GET | /evidence/executions/:id | Read-only evidence bundle for a grant execution (GL-025) — owner, grant_admin, auditor only |
| GET | / | Dashboard |
| POST | /demo/tamper-grant/:id | **Demo only** — corrupt a grant field without re-signing |

## Grant Execution Ledger (GL-023)

Every protected action attempt creates a `GrantExecution` record. This closes the audit/enforcement gap between an approved grant and the actual action execution.

### What is recorded

- **grantId** — the grant that matched (if any)
- **grantRequestId** — the original grant request (if the grant was created from an approved request)
- **operatorId** — the authenticated operator who triggered the action (when operator model is enabled)
- **action** and **resource** — what was attempted
- **challengeId** and **challengeResult** — the challenge/proof used (if any)
- **policyResult** — the policy engine reason (e.g. "Access granted", "No grant found...")
- **result** — `succeeded` | `denied` | `failed`
- **errorCode** — the specific failure reason when denied or failed
- **executedAt** — ISO timestamp
- **auditEventId** — linked audit event for full traceability

### Result values

- **succeeded** — the protected action was executed
- **denied** — a policy, challenge, signature, auth, grant, or role condition blocked execution
- **failed** — an internal handler error occurred after the authorization path began

### Read-only endpoints

- `GET /grant-executions` — list executions (filterable by `grantId`, `operatorId`)
- `GET /grant-executions/:id` — get a single execution
- `GET /grants/:id/executions` — list executions for a specific grant

**Authorization:** `owner`, `grant_admin`, or `auditor` role required.

### What GL-023 explicitly does NOT include

- No write endpoints for executions (append-only ledger)
- No dashboard or frontend changes

## GL-024 — Grant Usage Limits & Exhaustion Policy

Grants support optional usage limits that control how many times a grant can authorize a protected action.

### Usage limit fields

When grant data is returned (e.g. `GET /grants`, `GET /grants/:id`), the response includes:

| Field | Type | Meaning |
|-------|------|---------|
| `maxUses` | `integer \| null` | Usage limit. `null` = unlimited. |
| `useCount` | `integer` | Number of successful executions so far. |
| `remainingUses` | `integer \| null` | `maxUses - useCount`. `null` when unlimited. |

### Semantics

- **`maxUses` omitted or `null`** — the grant can be used unlimited times.
- **`maxUses: 1`** — one-time grant. Exactly one successful execution is allowed.
- **`maxUses: N`** — fixed N-time grant. Exactly N successful executions are allowed.

### Enforcement rules

- Exhausted grants fail closed with reason `grant_usage_exhausted`.
- Denied attempts (policy mismatch, expired grant, revoked grant, invalid challenge, signature failure) **do not** consume usage.
- Failed attempts (internal handler error) **do not** consume usage.
- Usage is consumed atomically **after** all other checks pass and before the action is executed.
- Exhausted attempts still create a `denied` `GrantExecution` record and an audit event with reason `grant_usage_exhausted`.

### Example: create a one-time grant

```bash
curl -s -X POST http://127.0.0.1:8765/grants \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "tech-01",
    "role": "technician",
    "action": "restart-service",
    "resource": "customer-env-a",
    "validFrom": "2026-05-02T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "createdBy": "admin",
    "reason": "Scheduled maintenance",
    "maxUses": 1
  }' | python3 -m json.tool
```

## Docs

- [docs/architecture.md](docs/architecture.md) — Component overview, request flow, stack decision
- [docs/mvp_scope.md](docs/mvp_scope.md) — Sprint 1 scope, acceptance criteria, next sprints
- [docs/security_boundaries.md](docs/security_boundaries.md) — What this MVP is NOT

---

## GL-025 — Execution Evidence Bundle

GL-025 adds a single read-only endpoint that aggregates the full grant lifecycle for a given `GrantExecution` into a minimal, audit-verifiable evidence bundle. No new tables, no migrations, no UI.

### Purpose

The evidence bundle answers, for any execution ID:

- **Who requested the grant** — requester operator ID and reason from the linked `GrantRequest`
- **Who approved the grant request** — approver operator ID and timestamp
- **Which grant was created** — grant ID, subject, role, action, resource, time window
- **Who executed the protected action** — operator ID from the execution record
- **Which action/resource was attempted** — action and resource fields from the execution
- **Which challenge/proof was used** — challenge ID and result
- **Whether the execution succeeded or was denied** — result field (`succeeded` | `denied` | `failed`)
- **Whether usage limits affected the decision** — `usageLimits.affectedOutcome` flag
- **Which audit events prove the lifecycle** — `auditTrail` array

### Endpoint

```
GET /evidence/executions/:id
```

Returns `200` with the evidence bundle, or `404` if the execution does not exist.

### Authorization

| Mode | Who can read |
|------|-------------|
| Operator model enabled | `owner`, `grant_admin`, `auditor` |
| Operator model disabled | Valid legacy `GRANTLAYER_ADMIN_TOKEN` Bearer token |

`demo_operator` role is **denied**. Missing or invalid Bearer token fails closed.

### Response shape

```json
{
  "evidenceId": "<execution-id>",
  "generatedAt": "<iso-timestamp>",
  "executionId": "<execution-id>",
  "grantId": "<grant-id or null>",
  "grantRequestId": "<grant-request-id or null>",
  "request": null,
  "approval": null,
  "grant": null,
  "execution": {
    "action": "restart-service",
    "resource": "customer-env-a",
    "operatorId": null,
    "challengeId": null,
    "challengeResult": "legacy_mode",
    "policyResult": "Access granted",
    "result": "succeeded",
    "errorCode": null,
    "executedAt": "<iso-timestamp>",
    "auditEventId": "<audit-event-id>"
  },
  "usageLimits": {
    "affectedOutcome": false
  },
  "auditTrail": []
}
```

When a `GrantRequest` was approved, `request` and `approval` blocks are populated:

```json
"request": {
  "id": "...",
  "requestedBy": "req-operator-id",
  "requestedAt": "...",
  "reason": "Scheduled maintenance"
},
"approval": {
  "approvedBy": "owner-operator-id",
  "approvedAt": "..."
}
```

When a `GrantRequest` was denied, the `approval` block contains `deniedBy`, `deniedAt`, and `denialReason` instead.

When a `Grant` was matched, the `grant` block is populated:

```json
"grant": {
  "id": "...",
  "subjectId": "tech-01",
  "role": "technician",
  "action": "restart-service",
  "resource": "customer-env-a",
  "validFrom": "...",
  "validUntil": "...",
  "createdBy": "...",
  "createdAt": "...",
  "signingKeyId": "demo-ed25519-v1",
  "payloadHash": "<sha256-hex>",
  "maxUses": null,
  "useCount": 1,
  "grantSignatureResult": "valid"
}
```

`grantSignatureResult` is included when available from audit data (`valid` | `missing` | `invalid` | `hash_mismatch` | `not_checked`). No raw signature bytes are emitted.

When usage limits caused a denial, `usageLimits.affectedOutcome` is `true`:

```json
"usageLimits": {
  "affectedOutcome": true,
  "reason": "grant_usage_exhausted",
  "maxUses": 1,
  "useCount": 1
}
```

### GL-025 explicit non-scope

- No `GET /evidence/grants/:id` or `GET /evidence/grant-requests/:id`
- No bulk evidence export
- No downloadable bundles
- ~~No `bundleHash` or integrity hash~~ Addressed by GL-026 (`evidenceHash`).
- No raw grant signature bytes in response
- No dashboard or frontend changes

## GL-026 — Evidence Bundle Integrity Hash & Export Readiness

GL-026 adds a deterministic integrity hash to every evidence bundle so auditors can later verify whether a bundle has changed. This is **not** blockchain anchoring, external notarization, or a downloadable export. It is a local, self-contained integrity mechanism.

### What GL-026 adds

The `GET /evidence/executions/:id` response now includes three metadata fields:

```json
{
  "evidenceId": "<execution-id>",
  "generatedAt": "<iso-timestamp>",
  "canonicalVersion": "gl-evidence-v1",
  "hashAlgorithm": "sha256",
  "evidenceHash": "<64-char-lowercase-sha256-hex>",
  ...
}
```

| Field | Value | Meaning |
|-------|-------|---------|
| `canonicalVersion` | `gl-evidence-v1` | Canonical serialization version. Used for future format evolution. |
| `hashAlgorithm` | `sha256` | The hash algorithm used to compute `evidenceHash`. |
| `evidenceHash` | 64-char lowercase hex | SHA-256 digest of the canonical JSON representation of the bundle. |

### How the hash is computed

1. **Build the bundle** — same aggregation as GL-025 (request, approval, grant, execution, usageLimits, auditTrail).
2. **Sort the audit trail** — audit events are ordered deterministically by `timestamp` then `id`.
3. **Strip volatile/self-referential fields** — `generatedAt`, `evidenceHash`, `canonicalVersion`, and `hashAlgorithm` are removed from the input before hashing.
4. **Canonicalize** — all object keys are sorted recursively alphabetically. JSON is emitted with compact separators (`separators=(",", ":")`).
5. **Hash** — `hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()` produces the 64-character lowercase hex string.

### Why these exclusions?

| Excluded field | Reason |
|----------------|--------|
| `generatedAt` | Wall-clock timestamp changes on every rebuild; including it would make the hash unstable. |
| `evidenceHash` | A hash cannot include itself without recursion. |
| `canonicalVersion` | Metadata about the serialization scheme, not part of the evidence data. |
| `hashAlgorithm` | Metadata about the hash scheme, not part of the evidence data. |

### Offline verification (auditor workflow)

An auditor can recompute the hash independently:

1. Obtain the evidence bundle JSON (e.g., via `GET /evidence/executions/:id`).
2. Remove `generatedAt`, `evidenceHash`, `canonicalVersion`, and `hashAlgorithm` from the JSON.
3. Recursively sort all object keys alphabetically.
4. Serialize to compact JSON (`separators=(",", ":")`).
5. Compute `SHA-256(serialized)`.
6. Compare the result with `evidenceHash`.

If they match, the bundle content has not been altered since the hash was generated.

### What the hash proves and does not prove

**Proves:** The bundle content (request, approval, grant, execution, usageLimits, auditTrail) has not been modified since the hash was generated.

**Does NOT prove:**
- That the underlying database was not tampered with (the hash is computed at read time).
- That the grant or execution itself is cryptographically signed (that is the Ed25519 grant signature, separate from the bundle hash).
- Blockchain anchoring, external notarization, or legal validity.

### Response contains no secrets

The evidence bundle and its canonical JSON input never contain:
- Bearer tokens or operator tokens
- Token hashes or salts
- Raw Ed25519 signature bytes
- Environment variable values
- Private keys

Only safe, already-public metadata is included (grant IDs, operator IDs, timestamps, policy results, audit events).

### GL-026 explicit non-scope

- **No blockchain** — the hash is local-only.
- **No external notarization** — no third-party timestamping service.
- **No PDF/ZIP/download export** — the bundle is still a JSON API response only.
- **No UI/dashboard/frontend changes** — the hash fields appear only in the JSON response.
- **No new endpoint** — `GET /evidence/executions/:id` is unchanged; only response fields are added.
- **No schema migration** — the hash is computed on-the-fly at build time.
- **No persisted hash** — the hash is not stored in the database.
- **No verify endpoint** — auditors recompute offline; no `POST /evidence/verify` is provided.

## Tamper & Verify Demo

The dashboard includes a "Tamper & Verify Demo" section that shows the signature check in action:

1. Select a signed grant from the dropdown
2. Click "Tamper Selected Grant" — calls `POST /demo/tamper-grant/:id`
3. The grant's `role` is changed in the database **without re-signing**
4. Click "Run Protected Action" — the action is **blocked** with `grantSignatureResult: hash_mismatch`
5. The audit log records the signature failure

### `POST /demo/tamper-grant/:id` — demo only

Intentionally corrupts a grant to demonstrate tamper detection.

```json
{
  "ok": true,
  "grantId": "...",
  "tamperedField": "role",
  "oldValue": "technician",
  "newValue": "tampered-role",
  "subjectId": "tech-01",
  "action": "restart-service",
  "resource": "customer-env-a",
  "message": "Grant tampered without re-signing. Signature should now fail."
}
```

**This endpoint is demo-only.** It must not exist in any production system. See [docs/security_boundaries.md](docs/security_boundaries.md).

## Sprint 2B — Grant Signature Response Fields

`POST /grants` response now includes:
```json
{
  "signaturePresent": true,
  "signingKeyId": "demo-ed25519-v1",
  "payloadHash": "<sha256-hex>"
}
```

`GET /grants` response now includes per grant:
```json
{
  "signaturePresent": true,
  "signingKeyId": "demo-ed25519-v1",
  "payloadHash": "<sha256-hex>",
  "signatureValid": true
}
```

`POST /demo-action` response now includes:
```json
{
  "grantSignatureResult": "valid"
}
```

Possible `grantSignatureResult` values: `valid` | `missing` | `invalid` | `hash_mismatch` | `not_checked`

New deny reasons: `grant_signature_missing` | `grant_signature_invalid` | `grant_payload_hash_mismatch`

## Next sprint

- ~~Sprint 2C: Demo admin token~~ ✅ Done
- ~~Sprint 2D: Docker packaging~~ ✅ Done
- ~~Sprint 2E: Operator model (GL-021)~~ ✅ Done
- ~~Sprint 2F: Real approval workflow (GL-022)~~ ✅ Done

---

## Sprint 2F — Real Approval Workflow (GL-022)

GL-022 introduces a real approval workflow using a separate **GrantRequest** lifecycle. Grant requests are created first, then approved or denied by a different operator. Approval creates the actual grant.

### GrantRequest lifecycle

```
requested → approved → grant created
        → denied
        → revoked (approved grants only)
        → expired (auto after 24h in 'requested' state)
```

### Statuses

| Status | Meaning |
|--------|---------|
| `requested` | Initial state. Waiting for approval or denial. |
| `approved` | An operator approved the request. A real grant was created. |
| `denied` | An operator denied the request. No grant was created. |
| `revoked` | A previously approved request was revoked. The linked grant is also revoked. |
| `expired` | The request sat in `requested` for more than 24 hours and was auto-expired. |

### Authorization rules

- **Requester cannot approve or deny their own request.** The API returns `403` with `Cannot approve your own request`.
- **Owner** and **grant_admin** can approve and deny requests.
- **Auditor** can read grant requests (`GET /grant-requests`, `GET /grant-requests/:id`) but cannot approve or deny.
- **demo_operator** cannot approve or deny real grants. This role is only for the demo tamper endpoint.
- **Legacy admin-token compatibility remains.** When `GRANTLAYER_ENABLE_OPERATOR_MODEL=false`, the system falls back to the legacy `GRANTLAYER_ADMIN_TOKEN` behavior.

### GL-022 API reference

| Method | Path | Auth required | Description |
|--------|------|---------------|-------------|
| POST | `/grant-requests` | `owner` or `grant_admin` | Create a new grant request. |
| GET | `/grant-requests` | `owner`, `grant_admin`, or `auditor` | List grant requests. Optional `?status=requested` filter. |
| GET | `/grant-requests/:id` | `owner`, `grant_admin`, or `auditor` | Get a single grant request by ID. |
| POST | `/grant-requests/:id/approve` | `owner` or `grant_admin` | Approve a request. Creates the actual grant. Returns `{ok, request, grant}`. |
| POST | `/grant-requests/:id/deny` | `owner` or `grant_admin` | Deny a request. Returns `{ok, request}`. Requires JSON body with `reason`. |

### Example walkthrough

```bash
# 1. Create a grant request (as grant_admin)
curl -s -X POST http://127.0.0.1:8765/grant-requests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "subjectId": "tech-01",
    "role": "technician",
    "action": "restart-service",
    "resource": "customer-env-a",
    "validFrom": "2026-05-02T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "reason": "Scheduled maintenance"
  }' | python3 -m json.tool

# 2. List grant requests (as auditor)
curl -s http://127.0.0.1:8765/grant-requests \
  -H "Authorization: Bearer <token>" | python3 -m json.tool

# 3. Get a specific request
curl -s http://127.0.0.1:8765/grant-requests/<request-id> \
  -H "Authorization: Bearer <token>" | python3 -m json.tool

# 4. Approve the request (as a different owner/grant_admin)
curl -s -X POST http://127.0.0.1:8765/grant-requests/<request-id>/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" | python3 -m json.tool

# 5. Deny a request
curl -s -X POST http://127.0.0.1:8765/grant-requests/<request-id>/deny \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"reason": "Not authorized for this action"}' | python3 -m json.tool
```

See [docs/architecture.md](docs/architecture.md) for the state machine and [docs/security_boundaries.md](docs/security_boundaries.md) for what is explicitly not included in this design.

---

## Sprint 2D — Docker packaging

This MVP can be started with Docker Compose.

### Start with Docker

```bash
cd /paperclip/grantlayer-mvp
GRANTLAYER_ADMIN_TOKEN=demo-token docker compose up
```

Or in detached mode:
```bash
GRANTLAYER_ADMIN_TOKEN=demo-token docker compose up -d
```

The API is available at `http://127.0.0.1:8765`.

To stop:
```bash
docker compose down
```

### Docker specifics

- **Base image:** `python:3.13-slim-bookworm`
- **Port:** `8765` (host mapping: `127.0.0.1:8765:8765`)
- **Runtime dependency:** `cryptography==43.0.0`
- **Data persistence:** `data/grantlayer.db` is stored in a named Docker volume (`grantlayer-data`)
- **No secrets baked into the image.** `GRANTLAYER_ADMIN_TOKEN` is passed via environment variable at runtime.
- **No database baked into the image.** The SQLite database is created on first startup.
- **Health check:** Container health is checked via `GET /health` every 30 seconds.
- **Container runs as non-root user** (`appuser`, UID 1000).

> **Demo only.** Do not deploy this Docker setup to production. See [docs/security_boundaries.md](docs/security_boundaries.md) for details.

