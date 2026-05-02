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
│   ├─ src/server.py         HTTP server + routing        │
│   ├─ src/policy_engine.py  evaluateAccess()             │
│   ├─ src/grants.py         Grant CRUD (SQLite)          │
│   ├─ src/audit_log.py      Audit events (SQLite)        │
│   ├─ src/challenges.py     Challenge store + validation  │
│   ├─ src/demo_action.py    Protected action handler     │
│   ├─ src/crypto_signing.py Ed25519 sign + verify        │
│   ├─ src/models.py         Dataclasses                  │
│   └─ src/db.py             SQLite init + connection     │
│                                                         │
│  Data                                                   │
│   ├─ data/grantlayer.db            SQLite (WAL mode)    │
│   ├─ data/demo_ed25519_private_key.pem  (gitignored)    │
│   └─ data/demo_ed25519_public_key.pem  (gitignored)     │
│                                                         │
│  Tests                                                  │
│   └─ tests/test_policy_engine.py  unittest (30 tests)   │
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
    → APPROVE
  → DENY "No matching grant"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Service health |
| GET | /grants | List all grants |
| POST | /grants | Create a grant |
| POST | /grants/:id/revoke | Revoke a grant |
| POST | /challenges | Create a challenge (5-min TTL) |
| GET | /challenges | List all challenges |
| POST | /demo-action | Run a protected demo action (optional challengeId) |
| GET | /audit-events | List audit events |
| GET | / | Dashboard |
| POST | /demo/tamper-grant/:id | **Demo only** — corrupt a grant without re-signing (tamper detection demo) |

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

**Grant** (Sprint 2B adds signature fields)
```
id, subject_id, role, action, resource,
valid_from, valid_until, created_by, reason,
revoked (bool), revoked_by, revoked_reason, revoked_at,
created_at,
signature (TEXT), signing_key_id (TEXT), payload_hash (TEXT)
```

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
