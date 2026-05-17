# GrantLayer

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**

GrantLayer is a verification, audit, and compliance layer for agentic grant and funding workflows.

When AI agents prepare funding applications, evaluate eligibility, collect evidence, or trigger approval decisions, institutions need a neutral verification layer — one that makes every step traceable, tamper-evident, and independently auditable. GrantLayer is that layer.

**GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.**

## What GrantLayer is

GrantLayer is **not** a payment app, a blockchain app, a demo app, or a pure funding platform. It is an infrastructure-level verification and audit layer for agent-driven processes that involve grants, approvals, evidence, and compliance decisions.

Core concepts:
- **Evidence Bundles** — collect evidence, criteria, sources, and timestamps for every grant lifecycle event
- **Verification Core** — check completeness, consistency, versions, and hash integrity of stored evidence
- **Audit Trails** — make traceable who or what decided what, when, and on which grounds
- **Policy Layer** *(Phase 2)* — machine-readable grant rules, exclusion criteria, deadlines, and proof requirements

## MVP scope

The current MVP and Product Core establish the technical foundation:
- Action-level grant model (subject, role, action, resource, time window)
- Policy evaluation: fail-closed
- Grant revocation, usage limits, Ed25519 signatures
- Operator model with RBAC
- Grant Request approval workflow
- Grant Execution audit ledger
- Evidence Bundles with SHA-256 integrity hash
- Evidence Persistence (durable storage)
- Evidence Verification Core (server-side hash verification)
- Evidence Completeness scoring
- Compliance Gap Reports
- Agent Permissions (scopes, profiles, assignments)
- Approval Rules and Approval Lifecycle
- Decision Provenance v2
- Auditor Reports and Exports
- Policy Requirements / Rule Packs
- Compliance Readiness Summary
- API Error Consistency
- Security / Secrets Regression Hardening
- SQLite (default) + PostgreSQL (optional)

## What is explicitly not in this MVP

- No blockchain (planned as optional Phase 3 integrity layer)
- No wallets, stablecoins, or treasury logic
- No UI beyond a local debug dashboard
- No external notarization or certification services
- No production authentication (no OAuth, JWT, TLS)

## Roadmap

See [docs/strategic_positioning.md](docs/strategic_positioning.md) for the full strategic context.

### Phase 1 — MVP + Product Core (completed)

The technical foundation and Product Core capabilities are complete: Evidence Persistence, Evidence Verification Core, Evidence Completeness, Compliance Gap Reports, Agent Permissions, Approval Rules, Approval Lifecycle, Decision Provenance v2, Auditor Reports and Exports, Policy Requirements, Compliance Readiness, API/OpenAPI consistency, Security/Secrets hardening, SQLite + PostgreSQL support. No blockchain dependency.

### Phase 2 — Product Core (completed)

All Product Core capabilities are implemented (GL-037 through GL-047): Compliance/Policy layer (machine-readable grant rules, exclusion criteria, deadlines, proof requirements), Decision Provenance, Auditor exports, structured compliance reports, Agent permission model, Evidence completeness scoring, Compliance gap reports, Multi-step approval workflows, API error consistency, Security/secrets regression hardening.

### Phase 3 — Optional Crypto Integrity Layer

Hash Anchoring of Evidence Bundle hashes, verification results, or decision records. Wallet/operator-based signatures. Optional Cardano or Ethereum anchoring for institutional-grade audit trails. Sensitive data stays off-chain; only hashes are anchored.

## Technical implementation

### Ed25519 grant signatures (DEMO ONLY)

- Private key is stored unencrypted at `data/demo_ed25519_private_key.pem`
- **Do not use this key in production**
- Key files are gitignored (`data/*.pem`)
- Single key ("demo-ed25519-v1"), no key rotation, no HSM, no PKI

## What it explicitly does NOT include

- No real privileged actions (no filesystem, OS, or network changes)
- No real admin rights
- No blockchain / smart contracts / testnet (blockchain is Phase 3 and optional)
- No production authentication / JWT / TLS
- No production use
- No HSM, no key management, no PKI
- See [docs/security_boundaries.md](docs/security_boundaries.md) for the complete list

## Stack

- **Backend:** Python 3.13, stdlib + `cryptography` v43.0.0 (Ed25519)
- **Frontend:** Vanilla HTML/JS, served by the backend — no build step
- **Database:** SQLite (WAL mode) or PostgreSQL, stored in `data/grantlayer.db` or PostgreSQL volume
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
cd grantlayer-mvp
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
cd grantlayer-mvp
python3 -m unittest discover -s backend/tests -v
```

Or via script:
```bash
./scripts/test.sh
```

Expected output: **1130 tests, 3 skipped, 0 failures.**

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

- [docs/operations/production_readiness_checklist.md](docs/operations/production_readiness_checklist.md) — GL-032 hardening status and remaining gaps
- [docs/operations/backup_restore.md](docs/operations/backup_restore.md) — Manual SQLite backup/restore procedures

---

## GL-032 — Production Readiness & SQLite Persistence Baseline

GL-032 hardens the MVP from a stable release candidate toward safer local operation. It adds no new user-facing features.

### What GL-032 adds

- **Configuration hardening:** `GRANTLAYER_LOG_LEVEL` (DEBUG|INFO|WARNING|ERROR, default INFO) and `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` (default 2000 ms) with safe parsing in `config.py`.
- **Health readiness extension:** `GET /health` returns additive, safe readiness fields (`dbConnected`, `dbWritable`, `dbFilePresent`, `dbDirectoryWritable`, `dbSizeBytes`, `journalMode`, `dbPathKind`) without leaking absolute paths or secrets.
- **Safe startup warnings:** `startup_warnings()` reports token presence and unsafe defaults but never leaks values.
- **SQLite persistence documentation:** Single-writer boundary, WAL behavior, filesystem requirements, and backup/restore limits are documented.

### Environment variables added in GL-032

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_LOG_LEVEL` | `INFO` | Logging level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. Invalid values fall back to `INFO`. |
| `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` | `2000` | Timeout in milliseconds for DB health probes inside `GET /health`. |

### What GL-032 is NOT

- Not a PostgreSQL sprint — SQLite remains the only persistent store.
- Not a storage adapter sprint — no pluggable storage interface.
- Not a migration sprint — no Alembic or versioning table.
- Not a distributed system — no replication, clustering, or multi-node support.

---

## Next sprint

- ~~Sprint 2C: Demo admin token~~ ✅ Done
- ~~Sprint 2D: Docker packaging~~ ✅ Done
- ~~Sprint 2E: Operator model (GL-021)~~ ✅ Done
- ~~Sprint 2F: Real approval workflow (GL-022)~~ ✅ Done
- ~~GL-028: Offline Evidence Bundle Verification~~ ✅ Done
- ~~GL-029: Evidence & Audit Finalization Sprint~~ ✅ Done
- ~~GL-032: Production Readiness & SQLite Persistence Baseline~~ ✅ Done
- ~~GL-033–GL-035: PostgreSQL support + deployment hardening~~ ✅ Done
- ~~GL-036: Evidence Persistence + Evidence Verification Core~~ ✅ Done
- ~~GL-037–GL-045-C: Product Core (Provenance, Auditor, Permissions, Approvals, Compliance)~~ ✅ Done
- ~~GL-046: Auth Fix — Grant Request read endpoints require authentication~~ ✅ Done
- ~~GL-047: Import Fix — agent permission assignments use relative imports~~ ✅ Done

Next work: demo/integration readiness and cleanup.

## GL-029 — Evidence & Audit Finalization Sprint

GL-029 hardens the evidence and audit trail from GL-025 through GL-028 without adding new API endpoints, database migrations, or UI changes.

### A. Evidence Verification Report

The existing `verify_evidence_export_artifact()` helper now returns a structured, machine-readable result dict.

**Success form:**
```json
{
  "ok": true,
  "evidenceId": "ex-001",
  "evidenceHash": "sha256-hex...",
  "canonicalVersion": "gl-evidence-v1",
  "hashAlgorithm": "sha256",
  "verifiedAt": "2026-05-06T22:10:00Z"
}
```

**Error form:**
```json
{
  "ok": false,
  "error": "hash_mismatch",
  "reason": "computed hash does not match evidenceHash",
  "evidenceId": "ex-001"
}
```

- `verifiedAt` is excluded from the evidence hash input.
- No secrets are exposed in the report.
- Existing CLI exit codes remain unchanged.

### B. Evidence Completeness Checks

New helper: `check_evidence_completeness(bundle) -> dict`

```json
{
  "complete": true,
  "checks": {
    "executionPresent": true,
    "grantLinkage": true,
    "grantRequestLinkage": "present",
    "auditEventLinkage": true,
    "auditTrailPresent": true,
    "usageLimitsConsistent": true,
    "outcomeConsistent": true
  },
  "warnings": [],
  "errors": []
}
```

Checks performed:
- `execution` section exists
- `grantId` → `grant` section present
- `grantRequestId` → `request` and `approval` present
- `auditTrail` chronological and deduplicated
- `usageLimits` consistent with `grant_usage_exhausted`
- `result` and `errorCode` mutually consistent

### C. Denial / Error-Code Consistency

New helper: `check_denial_code_consistency(bundle) -> dict`

Validates:
- `result` matches `errorCode` (succeeded → null, denied → present)
- `errorCode` is a known catalog value (warns on unknown)
- Denial reason is described in human-readable form (`denialReason`)
- Outcome matches bundle data (e.g. `no_grant` → no `grant` section)

Known denial codes:
`no_grant`, `grant_expired`, `grant_revoked`, `grant_usage_exhausted`, `invalid_challenge`, `challenge_required_missing`, `grant_signature_missing`, `grant_signature_invalid`, `grant_payload_hash_mismatch`, `grant_request_denied`, `policy_mismatch`, `role_mismatch`, `internal_error`.

Unknown error codes produce a warning, not an error, so future codes do not break validation.

### D. Security Boundary Regression Tests

- Completeness and consistency helpers never crash on null/legacy bundles
- No secrets, tokens, or environment values leak from helper outputs
- Helpers do not mutate the input bundle dict

### GL-029 explicit non-scope

- No new REST endpoints
- No database schema changes
- No UI or dashboard changes
- No audit chain or blockchain anchoring
- No new CLI scripts

---

## GL-028 — Offline Evidence Bundle Verification

GL-028 adds a local, offline-only verification utility for exported evidence bundle JSON artifacts.

### What it does

Recomputes the GL-026 `evidenceHash` from the canonical bundle content and compares it to the embedded hash. This proves the exported JSON artifact has not been modified since the hash was generated.

### What it does NOT do

- **No server endpoint.** There is no `/evidence/verify` endpoint.
- **No database access.** The verifier works purely on a local JSON file.
- **No network calls.**
- **No blockchain anchoring or external notarization.**
- **Does not prove database integrity.** It only proves the exported JSON artifact is unchanged.
- **Does not prove grant signature validity.** That is handled separately by Ed25519 grant signatures (Sprint 2B).

### CLI usage

```bash
python3 scripts/verify_evidence_bundle.py path/to/evidence.json
```

### Exit codes

| Exit code | Meaning |
|-----------|---------|
| 0 | OK — evidence bundle verified |
| 2 | FAIL — evidence hash mismatch (content was modified) |
| 3 | FAIL — invalid evidence bundle artifact (missing/invalid fields) |
| 4 | FAIL — unsupported evidence bundle format (unexpected version or algorithm) |
| 5 | FAIL — file read or parse error |

### Backend helper

The verifier can also be used programmatically:

```python
from backend.src.evidence_bundle import verify_evidence_export_artifact

result = verify_evidence_export_artifact(bundle_dict)
# result["ok"] is True or False
# result["error"] gives a stable error code on failure
```

### Verification rules

1. `canonicalVersion` must exist and equal `"gl-evidence-v1"`
2. `hashAlgorithm` must exist and equal `"sha256"`
3. `evidenceHash` must exist and be exactly 64-character lowercase hex
4. The hash is recomputed using the same GL-026 canonicalization rules:
   - Strip `generatedAt`, `evidenceHash`, `canonicalVersion`, `hashAlgorithm`
   - Recursively sort all object keys alphabetically
   - Serialize to compact JSON (`separators=(",", ":")`)
   - Compute SHA-256
5. The recomputed hash is compared to the embedded `evidenceHash`
6. Changing `generatedAt` alone does **not** fail verification (it is excluded from the hash input)
7. Changing any meaningful bundle content **does** fail verification

### Security notes

- No secrets, tokens, or raw signatures are printed by the CLI.
- No raw bundle content is printed by default.
- Safe error messages only — no stack traces on malformed JSON.

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

