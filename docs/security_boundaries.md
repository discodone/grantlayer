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

- ~~**No usage caps.**~~ Addressed by GL-024.
- **No write endpoints.** Clients cannot create, update, or delete execution records.
- **No dashboard or frontend changes.** The ledger is exposed via read-only JSON endpoints only.
- **No approval_status on grants.** GL-023 does not modify the `grants` table design.
- **No external services.** Execution records are stored in the local SQLite database.

## GL-024 — Grant Usage Limits & Exhaustion Policy

GL-024 adds optional usage limits to approved grants. It is purely backend enforcement; there are no UI, dashboard, or frontend changes.

### `max_uses` semantics

- `max_uses = null` (or omitted on creation) → unlimited uses.
- `max_uses = 1` → one-time grant.
- `max_uses = N` → fixed N-time grant.

### `use_count` tracks successful executions only

- `use_count` starts at `0` when the grant is created.
- It is incremented **only** when a protected action is fully approved and executed.
- It is **not** incremented for denied or failed attempts.

### Denied/failed attempts do not consume usage

- Policy mismatch, expired grant, revoked grant, invalid challenge, or signature failure → denial, no consumption.
- Internal handler error after the authorization path began → failure, no consumption.

### Exhausted grants fail closed

- When `use_count >= max_uses`, the grant is exhausted.
- Any subsequent attempt is denied with reason `grant_usage_exhausted`.
- This is a hard fail-closed: the action is blocked before execution.

### Exhausted attempts still create denied `GrantExecution` records

- Every exhausted attempt creates a `GrantExecution` with `result = "denied"` and `error_code = "grant_usage_exhausted"`.
- The record links to the matched grant, operator, challenge, and audit event.

### `grant_usage_exhausted` audit reason / error code

- Audit events for exhausted grants have `approved = false` and `reason = "grant_usage_exhausted"`.
- `GrantExecution.error_code` is also `"grant_usage_exhausted"`.

### No secrets/tokens stored or exposed

- Usage limit fields (`max_uses`, `use_count`) are plain integers stored in the grants table.
- No secrets, tokens, credentials, or sensitive values are involved in usage limit enforcement.
- No env variables are required for GL-024.

### No UI/dashboard/frontend changes

- Usage limits are enforced entirely in the backend policy engine and protected action handler.
- The dashboard does not display `useCount`, `maxUses`, or `remainingUses`.
- No new frontend pages, routes, or visual components were added.

## GL-026 — Evidence Bundle Integrity Hash & Export Readiness

GL-026 adds a deterministic integrity hash (`evidenceHash`) to the evidence bundle returned by `GET /evidence/executions/:id`. This section defines the security boundaries of that hash.

### What the hash is

- **Integrity metadata only.** The hash is computed on-the-fly when the bundle is built. It is not cryptographically signed, not blockchain-anchored, and not externally notarized.
- ** SHA-256 of canonical JSON.** The input is the evidence bundle with all object keys sorted recursively, serialized with compact separators, after removing volatile/self-referential fields.

### What the hash proves

- That the bundle content (request, approval, grant, execution, usageLimits, auditTrail) has not been altered since the hash was computed.
- An auditor can recompute the hash offline and compare it with the returned `evidenceHash`.

### What the hash does NOT prove

- **Database integrity.** The hash is computed at read time; it does not prove the underlying SQLite database was not tampered with before the bundle was built.
- **Cryptographic grant signature.** The Ed25519 grant signature verifies the grant's own integrity. The bundle hash is a separate, higher-level aggregation hash.
- **Legal validity or compliance.** The hash is a local demonstrator feature, not a legally binding audit proof.
- **Blockchain anchoring or external notarization.** No third-party service is involved.

### Exclusions from hash input

| Excluded field | Reason |
|----------------|--------|
| `generatedAt` | Wall-clock timestamp; changes on every rebuild |
| `evidenceHash` | Cannot hash itself |
| `canonicalVersion` | Serialization metadata, not evidence data |
| `hashAlgorithm` | Hash scheme metadata, not evidence data |

### No secrets in bundle or hash input

The evidence bundle and its canonical JSON representation never contain:
- Bearer tokens or operator tokens
- Token hashes or salts
- Raw Ed25519 signature bytes (only `grantSignatureResult` enum values)
- Environment variable values
- Private keys

Only safe, already-public metadata is included.

### GL-026 is NOT

- **Not blockchain.** No smart contracts, no wallet signatures, no testnet, no mainnet.
- **Not external notarization.** No third-party timestamping or attestation service.
- **Not a PDF/ZIP/download export.** The bundle remains a JSON API response.
- **Not a UI/dashboard/frontend change.** Hash fields appear only in JSON responses.
- **Not a new endpoint.** `GET /evidence/executions/:id` is unchanged except for additional response fields.
- **Not a schema migration.** The hash is computed at runtime; no database columns are added.
- **Not a persisted hash.** The hash is not stored in SQLite.
- **Not a verify endpoint.** There is no `POST /evidence/verify`; auditors recompute offline.

## GL-028 — Offline Evidence Bundle Verification

GL-028 adds a local, offline-only verification utility for exported evidence bundle JSON artifacts.

### What GL-028 is

- **Local file verification only.** The verifier reads a previously exported JSON artifact from disk. It does not query the API or the database.
- **Pure stdlib.** No external dependencies, no network calls.
- **Reuse of GL-026 canonicalization.** The verifier calls the same `canonical_evidence_bundle()` function used when the hash was originally computed, ensuring bit-for-bit consistency.

### What GL-028 proves

- That the exported JSON artifact has not been modified since the `evidenceHash` was generated.
- That the artifact conforms to the expected format version (`gl-evidence-v1`) and hash algorithm (`sha256`).

### What GL-028 does NOT prove

- **Database integrity.** The verifier reads a JSON file, not the database. It does not prove the underlying SQLite database was not tampered with.
- **Cryptographic grant signature.** The Ed25519 grant signature and the bundle hash are separate mechanisms. A valid bundle hash does not imply a valid grant signature, and vice versa.
- **Legal validity or compliance.** The offline verifier is a local demonstrator feature, not a legally binding audit proof.
- **Blockchain anchoring or external notarization.** No third-party service is involved.
- **Realtime server-side verification.** There is no `/evidence/verify` endpoint and no server-side file storage.

### Security properties

- **No secrets printed.** The CLI does not print bearer tokens, admin tokens, token hashes, salts, env values, private keys, raw signatures, or credentials.
- **No raw bundle content by default.** On success, only `OK evidence bundle verified` is printed. On failure, only a safe error message is printed.
- **No stack traces on malformed JSON.** The CLI catches `JSONDecodeError` and returns a clean failure with exit code 5.

### GL-028 does NOT include

- **Not a server endpoint.** There is no `/evidence/verify` endpoint.
- **Not a UI/dashboard/frontend change.** The CLI is a standalone script.
- **Not a schema migration.** No database columns are added.
- **Not a persisted verification result.** The verifier produces an exit code and prints to stdout; it does not write to disk or to the database.
- **Not bulk verification.** The CLI verifies one file at a time.
- **Not blockchain.** No smart contracts, no wallet signatures, no testnet, no mainnet.
- **Not external notarization.** No third-party timestamping or attestation service.

### GL-026 is NOT

- **Not blockchain.** No smart contracts, no wallet signatures, no testnet, no mainnet.
- **Not external notarization.** No third-party timestamping or attestation service.
- **Not a PDF/ZIP/download export.** The bundle remains a JSON API response.
- **Not a UI/dashboard/frontend change.** Hash fields appear only in JSON responses.
- **Not a new endpoint.** `GET /evidence/executions/:id` is unchanged except for additional response fields.
- **Not a schema migration.** The hash is computed at runtime; no database columns are added.
- **Not a persisted hash.** The hash is not stored in SQLite.
- **Not a verify endpoint.** There is no `POST /evidence/verify`; auditors recompute offline.

## GL-029 — Evidence & Audit Finalization Sprint

GL-029 adds offline, local-only evidence verification helpers and hardens the completeness and consistency checks without introducing new API endpoints, database migrations, or UI changes.

### Verification report security boundaries

- **No secrets printed.** `verify_evidence_export_artifact()` returns a dict containing only `ok`, `evidenceId`, `evidenceHash`, `canonicalVersion`, `hashAlgorithm`, `verifiedAt`, `error`, and `reason`. No bearer tokens, admin tokens, token hashes, salts, env values, private keys, raw signatures, or credentials are included.
- **No raw bundle content emitted.** The CLI does not echo the bundle contents by default. The `--json` flag prints only the structured report dict.
- **No stack traces on malformed JSON.** The CLI catches `JSONDecodeError` and returns exit code 5 with a clean failure message.

### Completeness checks security boundaries

- **Never crash on null or legacy bundles.** `check_evidence_completeness()` handles missing `execution`, missing `usageLimits`, and null `grantRequestId` gracefully. It returns warnings, not exceptions.
- **No mutation of input bundle.** Both completeness and consistency helpers return fresh result dicts; the input `bundle` dict is never modified.
- **No secrets leaked in result dicts.** `check_evidence_completeness()` and `check_denial_code_consistency()` return only boolean checks, string arrays (`warnings`, `errors`), and a `denialReason` string derived from a safe, hard-coded mapping.

### Known error-code semantics

GL-029 introduces `KNOWN_DENIAL_CODES`, a catalog of all denial/error codes produced by the policy engine, challenge handler, signature verifier, and usage limit enforcer:

`no_grant`, `grant_expired`, `grant_revoked`, `grant_usage_exhausted`, `invalid_challenge`, `challenge_required_missing`, `grant_signature_missing`, `grant_signature_invalid`, `grant_payload_hash_mismatch`, `grant_request_denied`, `policy_mismatch`, `role_mismatch`, `internal_error`.

Unknown error codes are flagged as a warning, not an error, so future codes do not break backward compatibility.

### What GL-029 proves and does NOT prove

**Proves:**
- The exported JSON artifact content has not been altered since the `evidenceHash` was generated.
- The bundle structure is complete (execution, grant linkage, request linkage, audit trail, usage limits consistent, outcomes consistent).
- The denial/error code is a known catalog value and matches the `result` field.

**Does NOT prove:**
- Database integrity (hash is read-time only).
- Cryptographic grant signature validity (separate Ed25519 mechanism).
- Legal validity or compliance.
- Blockchain anchoring or external notarization.

### GL-029 does NOT include

- **Not a server endpoint.** There is no `/evidence/verify` or `/audit-events/verify-chain` endpoint.
- **Not a UI/dashboard/frontend change.** The helpers are backend-only.
- **Not a schema migration.** No database columns are added.
- **Not an audit chain.** There is no `chain_hash`, no `audit_events.chain_hash`, and no chain verification endpoint.
- **Not PDF/ZIP/download export.** The bundle remains a JSON API response.
- **Not bulk verification.** The CLI verifies one file at a time.
- **Not blockchain.** No smart contracts, no wallet signatures, no testnet, no mainnet.
- **Not external notarization.** No third-party timestamping or attestation service.

## GL-032 — SQLite Persistence Boundaries & Production Readiness

GL-032 hardens the existing SQLite-based MVP for safer local operation. It does **not** add a new database engine, storage adapter, or migration framework.

### What GL-032 is

- **Configuration hardening:** `GRANTLAYER_LOG_LEVEL` (DEBUG|INFO|WARNING|ERROR, default INFO) and `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` (default 2000) are centrally evaluated in `config.py`.
- **Health readiness extension:** `GET /health` returns additive, safe readiness fields (`dbConnected`, `dbWritable`, `dbFilePresent`, `dbDirectoryWritable`, `dbSizeBytes`, `journalMode`, `dbPathKind`) without exposing absolute paths or secrets.
- **Safe startup warnings:** `startup_warnings()` reports presence of tokens and unsafe defaults but never leaks token values.
- **SQLite persistence documentation:** This section documents the single-writer boundary, WAL behavior, filesystem requirements, and backup/restore limits.

### SQLite remains the only persistent store

- GrantLayer MVP stores all data in a single SQLite database file.
- **Database:** PostgreSQL is now available as an optional backend. The security boundary for the database layer is the same as for SQLite: the database must be protected by the operator.
- There is no storage abstraction layer or pluggable adapter.

### Single-writer boundary

- SQLite with WAL mode (`PRAGMA journal_mode=WAL`) supports one writer and multiple readers concurrently.
- Do not open the `.db` file with another writer process while GrantLayer is running.
- The health probe uses a **temporary table** write test so it does not interfere with persistent schema.

### WAL files must be kept together

When using a file-backed database, three files must be treated as a single unit for backup and restore:

| File | Purpose |
|------|---------|
| `grantlayer.db` | Main database file |
| `grantlayer.db-wal` | Write-ahead log (uncommitted changes) |
| `grantlayer.db-shm` | Shared-memory file for WAL indexing |

**Backups must include all three files while the server is stopped**, or use `VACUUM INTO` / SQLite online backup tools. Copying only `.db` while the server is running will produce an inconsistent snapshot.

### Filesystem requirements

- The directory containing the DB file must be writable for WAL creation and journal files.
- Health checks report `dbDirectoryWritable` so operators can detect permission problems early.
- In-memory databases (`:memory:`) are supported for testing; `dbPathKind` is `"memory"` and file-related fields are false/null.

### Backup / restore limits

- **No built-in automated backup.** GrantLayer does not schedule or perform backups.
- **Recommended:** Stop the server, copy the `.db` + `.db-wal` + `.db-shm` set, then restart.
- **Alternative:** Use SQLite `VACUUM INTO 'backup.db'` via an external SQLite client while the server is running (this produces a clean, standalone file without WAL).
- **Restore:** Replace the three files with a consistent set and restart. Do not mix files from different points in time.

### Safe logging and error output

- Token values, hashes, salts, env values, and private keys are never written to logs or error responses.
- `GET /health` never returns `dbPath`, absolute paths, or secrets.
- Startup warnings report **presence** of settings, not their values.

### What GL-032 is NOT

- **Not a PostgreSQL sprint.** No Postgres driver, no connection pooling, no schema migration framework.
- **Not a storage adapter sprint.** No pluggable storage interface.
- **Not a migration sprint.** No Alembic, no SQLAlchemy migrations, no versioning table.
- **Not a feature sprint.** No new user-facing features; only hardening, documentation, and safe defaults.
- **Not a distributed system.** SQLite remains local-only; there is no replication, clustering, or multi-node support.

