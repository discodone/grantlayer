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

## Future sprint additions (not in this MVP)

- Blockchain-anchored audit log (optional proof layer)
- Real authentication (OAuth2, mTLS, hardware token)
- Windows service integration
- Multi-approver workflow (4-eyes principle)
- Production database (PostgreSQL)
- Role-based access control for the API itself
- HSM/KMS key management for signing keys
