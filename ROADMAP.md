# GrantLayer — Roadmap

> GrantLayer turns agentic grant workflows into verifiable institutional records.

For full strategic context see [docs/strategic_positioning.md](docs/strategic_positioning.md).

---

## Phase 1 — MVP (current)

**Scope:** Technical foundation. Evidence persistence, verification, audit trails, policy evaluation. No blockchain dependency.

| Sprint | Focus | Status |
|--------|-------|--------|
| GL-013–GL-020 | Core grant model, policy engine, RBAC, demo hardening | ✅ Done |
| GL-021 | Real operator / admin model | ✅ Done |
| GL-022 | Grant Request approval workflow | ✅ Done |
| GL-023 | Grant Execution audit ledger | ✅ Done |
| GL-024 | Grant usage limits & exhaustion policy | ✅ Done |
| GL-025–GL-029 | Evidence Bundles, integrity hash, offline verification, audit finalization | ✅ Done |
| GL-030–GL-031 | API consistency hardening, OpenAPI contract | ✅ Done |
| GL-032–GL-033 | Production readiness, SQLite persistence baseline | ✅ Done |
| GL-034–GL-035 | PostgreSQL support + deployment hardening | ✅ Done |
| GL-036 | Evidence Persistence + Evidence Verification Core | ✅ Done (pending merge) |

**MVP complete when:** GL-036 merged to main, 360 tests green, all core Evidence endpoints stable.

---

## Phase 2 — Product Core

**Scope:** Make GrantLayer usable by real agent pipelines and institutions.

- Compliance/Policy layer: machine-readable grant rules, exclusion criteria, deadlines, proof requirements
- Decision Provenance: trace which agent, which model, which data contributed to each decision
- Auditor exports: structured, signed compliance reports
- Agent permission model: scoped API access for agent-to-agent grant flows
- Evidence completeness scoring and compliance gap reports
- Multi-step approval workflows (threshold-based, 4-eyes)

**Not in Phase 2:** blockchain, wallet integration, payment flows, public UI.

---

## Phase 3 — Optional Crypto Integrity Layer

**Scope:** Cryptographic, independently verifiable proof of grant process integrity.

- Hash anchoring of Evidence Bundle hashes or decision records on a public ledger
- Wallet/operator-based signatures for institutional-grade identity
- Cardano or Ethereum anchoring (optional, configurable)
- **Sensitive data stays off-chain.** Only SHA-256 hashes are anchored.
- Optional stablecoin/treasury integration if Phase 2 introduces payment flows

**Why optional:** For most institutions, SHA-256-hashed, server-side-verified evidence with a full audit trail is sufficient. Blockchain anchoring is a configurable add-on, not a core requirement.

---

## Explicit non-scope (all phases)

- No payment processing or settlement
- No real user authentication (OAuth, JWT, SSO) until explicitly scoped
- No multi-tenant SaaS architecture until explicitly scoped
- No public UI product — GrantLayer is an API layer
- No general-purpose grant discovery or matchmaking
