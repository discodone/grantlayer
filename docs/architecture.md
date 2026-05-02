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
│  Backend (Python 3, stdlib only)                        │
│   ├─ src/server.py       HTTP server + routing          │
│   ├─ src/policy_engine.py  evaluateAccess()             │
│   ├─ src/grants.py       Grant CRUD (SQLite)            │
│   ├─ src/audit_log.py    Audit events (SQLite)          │
│   ├─ src/challenges.py   Challenge store + validation   │
│   ├─ src/demo_action.py  Protected action handler       │
│   ├─ src/models.py       Dataclasses                    │
│   └─ src/db.py           SQLite init + connection       │
│                                                         │
│  Data                                                   │
│   └─ data/grantlayer.db  SQLite (WAL mode)              │
│                                                         │
│  Tests                                                  │
│   └─ tests/test_policy_engine.py  unittest              │
└─────────────────────────────────────────────────────────┘
```

## Request flow — Demo Action (Sprint 2A)

```
Browser / curl
  │
  POST /demo-action  {subjectId, role, action, resource, challengeId?}
  │
  ▼
server.py  →  demo_action.handle_demo_action()
                │
                ├─ grants.list_grants()           reads SQLite
                ├─ policy_engine.evaluate_access()
                │     checks: subject / role / action / resource /
                │             time window / revocation
                │     returns: PolicyResult {approved, reason, matchedGrantId}
                │
                ├─ (if challengeId present)
                │   challenges.validate_challenge()
                │     checks: exists / subject match / action match /
                │             resource match / not expired / not used
                │     on success: marks challenge as used (replay blocked)
                │     fail-closed: invalid challenge → deny even with valid grant
                │
                └─ audit_log.append_event()       writes SQLite
                       includes: challenge_id, challenge_present, challenge_result
                │
                ▼
          JSON response  {approved, message|reason, challengeId, challengeResult, auditEventId}
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

## Data model

**Grant**
```
id, subject_id, role, action, resource,
valid_from, valid_until, created_by, reason,
revoked (bool), revoked_by, revoked_reason, revoked_at,
created_at
```

**Challenge** (Sprint 2A)
```
id, subject_id, action, resource,
created_at, expires_at, used_at,
status: active | used | expired
```

**AuditEvent**
```
id, timestamp, subject_id, role, action, resource,
approved (bool), reason, matched_grant_id,
challenge_id, challenge_present (bool), challenge_result
```

challenge_result values: valid | missing | not_found | expired | already_used | mismatch | legacy_mode
