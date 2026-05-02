# GrantLayer MVP — Scope

## Sprint 1 — Local Demonstrator (this build)

### In scope

| Feature | Status |
|---------|--------|
| Create temporary grant (subject, role, action, resource, time window) | ✅ |
| Policy evaluation: subject / role / action / resource / time / revocation | ✅ |
| Fail-closed: any ambiguity → deny | ✅ |
| Grant revocation | ✅ |
| Audit log (every attempt, approved or denied) | ✅ |
| Protected demo action endpoint | ✅ |
| Dashboard: grants + audit events | ✅ |
| Dashboard: create grant form | ✅ |
| Dashboard: test demo action form | ✅ |
| Dashboard: revoke grant button | ✅ |
| SQLite persistence | ✅ |
| Unit tests: policy engine + audit events | ✅ |

### Explicitly out of scope (Sprint 1)

| Feature | Sprint |
|---------|--------|
| Cryptographic grant signatures (Ed25519) | Sprint 2 |
| Blockchain-anchored audit log | Sprint 3+ |
| Real authentication / session management | Sprint 2 |
| Windows service integration | Sprint 3+ |
| Multi-approver (4-eyes principle) | Sprint 2 |
| Real admin action execution | Sprint 3+ |
| PostgreSQL / production database | Sprint 3+ |
| API rate limiting | Sprint 2 |
| HTTPS / TLS | Sprint 2 |
| Deployment / Docker | Sprint 2 |

## Acceptance criteria (Sprint 1)

- [x] POST /grants creates a grant with all required fields
- [x] POST /demo-action with valid grant → approved: true + audit event
- [x] POST /demo-action with expired grant → approved: false + audit event
- [x] POST /demo-action with revoked grant → approved: false + audit event
- [x] POST /demo-action with wrong role → approved: false + audit event
- [x] POST /demo-action with wrong action → approved: false + audit event
- [x] POST /grants/:id/revoke marks grant as revoked
- [x] GET /grants returns all grants with status
- [x] GET /audit-events returns all audit events
- [x] Dashboard loads and is usable in browser
- [x] All tests pass
