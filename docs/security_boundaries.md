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

## What the MVP demonstrates

| Concept | Demonstrated how |
|---------|-----------------|
| Temporary grant creation | POST /grants stores a grant with validFrom/validUntil |
| Policy evaluation | evaluateAccess() checks role, action, resource, time window, revocation |
| Fail-closed behavior | Any missing or non-matching grant results in denial |
| Grant revocation | POST /grants/:id/revoke sets revoked=true; subsequent checks are denied |
| Audit logging | Every access attempt (approved or denied) is written to audit_events |
| Dashboard visibility | GET /grants and GET /audit-events exposed; served via dashboard |

## Future sprint additions (not in this MVP)

- Cryptographic signatures on grants (Ed25519)
- Blockchain-anchored audit log (optional proof layer)
- Real authentication (OAuth2, mTLS, hardware token)
- Windows service integration
- Multi-approver workflow (4-eyes principle)
- Production database (PostgreSQL)
- Role-based access control for the API itself
