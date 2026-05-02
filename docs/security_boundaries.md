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

## Sprint 2B — Ed25519 Grant Signatures: DEMO ONLY limitations

Sprint 2B adds Ed25519 signatures to grants. These are **demo-only** and have the following limitations:

- **Private key is stored unencrypted on disk** (`data/demo_ed25519_private_key.pem`) — no HSM, no passphrase, no secure enclave
- **Single signing key** ("demo-ed25519-v1") — no key rotation, no key revocation, no PKI
- **Public key is loaded from disk** at verification time — no certificate chain, no trust anchor, no key distribution protocol
- **No key escrow or backup** — if the `data/` directory is deleted, all previous grant signatures become unverifiable
- **Any process with filesystem access** can read the private key and forge grant signatures
- The `cryptography` library is used correctly (Ed25519 is a sound algorithm), but the key management is not suitable for production

**Do not use the demo key or this signing mechanism to gate access to real systems.**

| Concept | Sprint 2B Demo | Production requirement |
|---------|---------------|----------------------|
| Key storage | Unencrypted PEM on disk | HSM or KMS |
| Key rotation | None | Regular rotation policy |
| Multiple signers | None | Multi-party signing |
| Public key distribution | Local file | PKI / certificate |
| Key backup | None | Secure key escrow |

## What the MVP demonstrates

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
