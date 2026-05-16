# GrantLayer Product Core Readiness

**Status:** Product Core MVP ready for integration/demo preparation after GL-045-C, assuming tests pass.

## Completed capability map (GL-037 through GL-045)

| Sprint | Capability | Status |
|--------|------------|--------|
| GL-037 | Evidence Persistence / Verification | Done |
| GL-038 | Evidence Completeness + Compliance Gap Reports | Done |
| GL-039 | Agent Permissions (Evaluator, Profiles, Assignments) | Done |
| GL-040 | Approval Rules + Lifecycle (Build, Transition, Evaluate) | Done |
| GL-041 | Decision Provenance v2 | Done |
| GL-042 | Auditor Export | Done |
| GL-043 | Policy Requirements / Rule Packs | Done |
| GL-044 | Compliance Readiness Summary + API | Done |
| GL-045-A | API Contract / Error Consistency | Done |
| GL-045-B | Security / Secrets Regression Hardening | Done |
| GL-045-C | Final Product Core Readiness Check | Done |

## Core API endpoint inventory

### Product Core builders (POST)

| Endpoint | Description |
|----------|-------------|
| `POST /agent-permissions/evaluate` | Evaluate whether an agent is permitted a scope |
| `POST /agent-permissions/assignments/resolve` | Resolve effective permission for an agent assignment |
| `POST /approvals/evaluate` | Evaluate approval requirements for an action |
| `POST /approvals/lifecycle/build` | Build an approval request lifecycle state |
| `POST /approvals/lifecycle/transition` | Transition an approval request through a state change |
| `POST /decision-provenance/v2/build` | Build decision provenance record v2 |
| `POST /auditor/exports/build` | Build institutional auditor export |
| `POST /policy-requirements/evaluate` | Evaluate policy requirement rule pack |
| `POST /compliance/readiness/build` | Build compliance readiness summary |

### Product Core lookups (GET)

| Endpoint | Description |
|----------|-------------|
| `GET /agent-permissions/profiles` | List agent permission profiles |
| `GET /agent-permissions/profiles/{profileName}` | Get a single permission profile |
| `GET /evidence/executions/{executionId}/verify` | Verify evidence bundle integrity |
| `GET /evidence/executions/{executionId}/completeness` | Evidence completeness report |
| `GET /compliance/gaps/executions/{executionId}` | Compliance gap report |
| `GET /auditor/reports/executions/{executionId}` | Auditor report for execution |
| `GET /provenance/executions/{executionId}/summary` | Decision provenance summary |

## Non-scope statement

The current GrantLayer Product Core MVP explicitly does **not** include:

- **No UI product** — the interface is an API layer; any UI is an integration concern
- **No blockchain dependency** — blockchain hash anchoring is a Phase 3 optional extension
- **No payment processing** — no financial transactions, treasury, or settlement
- **No OAuth/JWT/SSO production auth** — the current operator model is a local demonstrator
- **No multi-tenant SaaS architecture** — single-tenant deployment only
- **No grant discovery marketplace** — no general-purpose grant matchmaking

## Integration positioning

GrantLayer is a **verification, audit, policy, permission, approval, and readiness layer** for agentic grant/funding workflows.

It sits between the agent pipeline and the institutional record — capturing evidence, verifying integrity, and producing machine-readable audit trails.

## Operational readiness notes

- All tests must pass (1068+ tests, 3 skipped for PostgreSQL)
- OpenAPI must remain aligned with server.py
- Evidence / decision / auditor / policy / readiness flows are API-first
- Institutional integrations can use the readiness and auditor export APIs as entry points
- SQLite is the default persistent store; PostgreSQL is optional

## Future optional extensions

These are explicitly out of scope for the current Product Core MVP and will only be added if explicitly scoped later:

- Real production auth (OAuth2, mTLS, hardware tokens)
- Multi-tenant architecture
- UI/dashboard product
- Blockchain hash anchoring
- Wallet/operator signatures
- Payment/treasury integration

## Test coverage

- `backend/tests/test_gl045c_product_core_readiness.py` — final readiness regression
- All prior GL-037 through GL-045-B test suites remain active and passing
