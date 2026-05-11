# GrantLayer — Strategic Positioning

## Core statement

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**

> **GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.**

## The problem

When AI agents prepare grant applications, evaluate eligibility, collect evidence, or trigger approval decisions, institutions face a structural trust problem: there is no neutral layer that makes the agent's actions traceable, tamper-evident, and independently auditable.

Existing audit logs are internal to specific systems. Evidence is scattered across emails, documents, and APIs. Decisions are made by opaque agent pipelines. Compliance reviewers have no structured way to answer: *Who decided what, when, and on which grounds?*

## What GrantLayer is

GrantLayer is a **verification, audit, and compliance layer** for agentic grant and funding workflows. It sits between the agent pipeline and the institutional record — capturing evidence, verifying integrity, and producing machine-readable audit trails.

It is **not** a payment app, a blockchain app, a crypto wallet, a demo app, or a generic funding platform. It is infrastructure for the agentic economy's compliance problem.

## Core architecture concepts

| Concept | What it does |
|---------|-------------|
| **Evidence Bundles** | Aggregate evidence, criteria, sources, approval chain, and timestamps into a single verifiable unit for each grant lifecycle event |
| **Verification Core** | Server-side verification of stored evidence: checks hash integrity, completeness, version consistency, and status |
| **Audit Trails** | Immutable, append-only record of who or what decided what, when, and on which grounds |
| **Policy Layer** *(Phase 2)* | Machine-readable grant rules, exclusion criteria, deadlines, and proof requirements for automated compliance checking |
| **Crypto Integrity** *(Phase 3, optional)* | Hash anchoring of evidence bundle hashes or decision records on a public ledger for institutional-grade verifiability |

## What GrantLayer is not (and why this matters)

| Not this | Why |
|----------|-----|
| A payment system | No financial transactions, no treasury, no settlement |
| A blockchain app | Blockchain is a Phase 3 option for hash anchoring only; not a core dependency |
| A wallet app | No private keys for end users, no on-chain identity |
| A demo app | The MVP is a real, testable, deployable backend — not a slide-ware demo |
| A pitch tool | GrantLayer is built to be used by systems, not to impress investors |
| A UI product | The interface is an API; any UI is an integration concern |

## Strategic thesis

Agentic workflows are replacing manual human steps in grant processes — eligibility checks, evidence collection, document preparation, routing, and approval triggers. As this shift accelerates, the question shifts from "can the agent do this?" to "can we prove it was done correctly?"

GrantLayer answers the second question. It is the compliance layer that makes agentic grant workflows institutionally acceptable.

## Roadmap

### Phase 1 — MVP (current)

**Goal:** Establish the technical foundation. No external dependencies.

| Component | Status |
|-----------|--------|
| Grant model (subject, role, action, resource, time window) | ✅ |
| Policy evaluation — fail-closed | ✅ |
| Grant revocation + usage limits | ✅ |
| Ed25519 grant signatures | ✅ |
| Operator model + RBAC | ✅ |
| Grant Request approval workflow | ✅ |
| Grant Execution audit ledger | ✅ |
| Evidence Bundles + SHA-256 integrity hash | ✅ |
| Evidence Persistence (durable storage, migration-based) | ✅ |
| Evidence Verification Core (server-side hash verification) | ✅ |
| SQLite (default) + PostgreSQL (optional) | ✅ |
| OpenAPI-documented REST API | ✅ |

**Not in Phase 1:** blockchain, wallets, UI beyond debug dashboard, external notarization, production auth.

---

### Phase 2 — Product Core

**Goal:** Make GrantLayer usable by real institutions and agent pipelines.

- Compliance/Policy layer: machine-readable grant rules, exclusion criteria, deadlines, proof requirements
- Decision Provenance: full trace of which agent, which model, which data version contributed to a decision
- Auditor exports: structured, signed compliance reports for institutional review
- Agent permission model: scoped API access for agent-to-agent grant flows
- Multi-step approval workflows (e.g. 4-eyes, threshold-based)
- Evidence completeness scoring and structured compliance gap reports

---

### Phase 3 — Optional Crypto Integrity Layer

**Goal:** Provide cryptographic, independently verifiable proof of grant process integrity.

- Hash anchoring: publish SHA-256 hashes of Evidence Bundle records, verification results, or decision logs to a public ledger
- Wallet/operator-based signatures: operator identity backed by on-chain key
- Cardano or Ethereum anchoring: institutional-grade immutability for audit records
- **Sensitive data stays off-chain.** Only hashes are anchored. Evidence content never appears on-chain.
- Stablecoin/treasury integration: optional, only if grant payment flows are added in Phase 2

**Why Phase 3 is optional:**  
For most institutional use cases, SHA-256-hashed, server-side-verified evidence with a complete audit trail is sufficient for compliance. Blockchain anchoring adds independent verifiability at the cost of infrastructure complexity. It is a configurable add-on, not a requirement.

## Security boundaries

This document does not replace [docs/security_boundaries.md](security_boundaries.md). The security boundaries document remains authoritative for what the current MVP explicitly does and does not provide.

Key boundaries relevant to the strategic positioning:

- GrantLayer does not execute real privileged actions — it records and verifies that they happened correctly
- Evidence verification does not affect grant decisions — it is a read-only audit operation
- No secrets are stored in Evidence Bundles or exposed via the API
- The current MVP is a local demonstrator — it is not a production-hardened system
