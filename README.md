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

Expected output: **35 tests, 0 failures.**

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
| POST | /grants | Create a grant |
| POST | /grants/:id/revoke | Revoke a grant |
| POST | /challenges | Create a challenge (5-min TTL) |
| GET | /challenges | List all challenges |
| POST | /demo-action | Run protected demo action (optional challengeId) |
| GET | /audit-events | List audit events |
| GET | / | Dashboard |
| POST | /demo/tamper-grant/:id | **Demo only** — corrupt a grant field without re-signing |

## Docs

- [docs/architecture.md](docs/architecture.md) — Component overview, request flow, stack decision
- [docs/mvp_scope.md](docs/mvp_scope.md) — Sprint 1 scope, acceptance criteria, next sprints
- [docs/security_boundaries.md](docs/security_boundaries.md) — What this MVP is NOT

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

- Sprint 2C: Demo admin token (static Bearer token via env var)
- Sprint 2D: Docker packaging
