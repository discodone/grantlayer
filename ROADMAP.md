# GrantLayer — Roadmap

> GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.

For full strategic context see [docs/strategic_positioning.md](docs/strategic_positioning.md).

---

## Phase 1 — MVP (current)

**Scope:** Technical foundation plus Product Core. Evidence persistence, verification, audit trails, policy evaluation, compliance readiness, and agent permissions. No blockchain dependency.

| Sprint | Focus | Status |
|--------|-------|--------|
| GL-013–GL-020 | Core grant model, policy engine, RBAC, demo hardening | Done |
| GL-021 | Real operator / admin model | Done |
| GL-022 | Grant Request approval workflow | Done |
| GL-023 | Grant Execution audit ledger | Done |
| GL-024 | Grant usage limits & exhaustion policy | Done |
| GL-025–GL-029 | Evidence Bundles, integrity hash, offline verification, audit finalization | Done |
| GL-030–GL-031 | API consistency hardening, OpenAPI contract | Done |
| GL-032–GL-033 | Production readiness, SQLite persistence baseline | Done |
| GL-034–GL-035 | PostgreSQL support + deployment hardening | Done |
| GL-036 | Evidence Persistence + Evidence Verification Core | Done |
| GL-037 | Provenance events, auditor report, summary | Done |
| GL-038 | Evidence completeness scoring, compliance gap reports | Done |
| GL-039 | Agent permission model (scopes, profiles, assignments) | Done |
| GL-040 | Approval rules + lifecycle (build, transition, evaluate) | Done |
| GL-041 | Decision Provenance v2 | Done |
| GL-042 | Auditor Export | Done |
| GL-043 | Policy Requirements / Rule Packs | Done |
| GL-044 | Compliance Readiness Summary + API | Done |
| GL-045-A | API Contract / Error Consistency | Done |
| GL-045-B | Security / Secrets Regression Hardening | Done |
| GL-045-C | Final Product Core Readiness Check | Done |
| GL-046 | Auth Fix — Grant Request read endpoints require authentication | Done |
| GL-047 | Import Fix — agent permission assignments use relative imports | Done |

**MVP + Product Core status:** Complete. 1130 tests, 3 skipped, 0 failures.

---

## Next Work

The immediate next phase is **demo/integration readiness and cleanup**:

- Documentation alignment (README, ROADMAP, architecture docs)
- Integration smoke tests with real agent pipelines
- Performance baseline for the audit/evidence read paths
- Operator onboarding documentation

---

## Phase 3 — Optional Crypto Integrity Layer

**Scope:** Cryptographic, independently verifiable proof of grant process integrity.

- Hash anchoring of Evidence Bundle hashes or decision records on a public ledger
- Wallet/operator-based signatures for institutional-grade identity
- Cardano or Ethereum anchoring (optional, configurable)
- **Sensitive data stays off-chain.** Only SHA-256 hashes are anchored.
- Optional stablecoin/treasury integration if payment flows are introduced

**Why optional:** For most institutions, SHA-256-hashed, server-side-verified evidence with a full audit trail is sufficient. Blockchain anchoring is a configurable add-on, not a core requirement.

---

## Explicit non-scope (all phases)

- No payment processing or settlement
- No real user authentication (OAuth, JWT, SSO) until explicitly scoped
- No multi-tenant SaaS architecture until explicitly scoped
- No public UI product — GrantLayer is an API layer
- No general-purpose grant discovery or matchmaking
