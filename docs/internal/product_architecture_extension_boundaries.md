# GrantLayer Product Architecture and Extension Boundaries

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines GrantLayer as a **reusable, adaptable, extensible API-first product core**.

It clarifies:
- what belongs to the stable GrantLayer Product Core
- what should be treated as extension / adaptor / plugin surface
- what should remain implementation detail
- what can be customized, replaced, rebuilt, or integrated later
- what must not be coupled too early

This is a **product-foundation architecture document**. It does not implement runtime extension or plugin code.

## 2. Product architecture principle

GrantLayer turns agentic grant workflows into verifiable institutional records.

The architecture protects a stable **Product Core** while allowing adapters, policy packs, storage backends, clients, and future integrations to evolve around it. The Product Core should be opinionated about contracts and data integrity, but unopinionated about deployment-specific behavior, UI frameworks, identity providers, and optional integrations.

## 3. Architecture layers

GrantLayer is organized into the following layers, from outermost to innermost:

1. **API / Contract Layer** — the OpenAPI-documented HTTP surface that integrators and clients rely on.
2. **Product Core Domain Layer** — the canonical domain models, lifecycles, and evaluation logic.
3. **Evidence and Verification Layer** — evidence bundles, hash computation, tamper detection, and completeness scoring.
4. **Policy and Permission Layer** — policy rule packs, permission profiles, approval lifecycles, and requirement evaluation.
5. **Provenance, Audit, and Export Layer** — decision provenance, audit event records, and auditor exports.
6. **Persistence Layer** — durable storage for grants, requests, evidence, audit events, and configuration.
7. **Runtime Configuration Layer** — environment-specific settings, feature flags, and deployment parameters.
8. **Extension / Adapter Layer** — pluggable surfaces that map external formats, identity providers, and storage backends into the Product Core without redefining it.
9. **Optional Integration Layer** — blockchain anchoring, wallet signing, payment integrations, dashboard clients, and observability sinks that may be attached but are not required for Product Core operation.

## 4. Stable Product Core

The following modules constitute the stable Product Core. They should not be redefined by adapters or extensions:

- **Grant Requests** — subject-initiated requests for scoped actions, time-bounded and auditable.
- **Approvals** — operator or policy-driven approval decisions linked to grant requests.
- **Grants** — active permission records with Ed25519 signatures and SHA-256 payload hashes.
- **Grant Executions** — one record per protected action attempt, linked to a Grant and a Grant Request.
- **Evidence Bundles** — flat, deterministic JSON bundles aggregating the full lifecycle for a single execution.
- **Evidence Persistence** — durable, immutable storage for evidence bundles with hash-based lookup.
- **Evidence Verification** — offline recomputation and comparison of evidence hashes to detect tampering or corruption.
- **Evidence Completeness** — structured score (0–100) and readiness flag derived from execution, evidence, verification, provenance, and policy coverage.
- **Compliance Gap Reports** — automated gap detection mapped to severity catalogues with recommended actions.
- **Policy Requirements / Rule Packs** — machine-readable policy evaluation with required evidence, exclusions, deadlines, amount limits, required roles, and approval policies.
- **Agent Permissions** — scope-based permission evaluation, permission profiles, and assignment resolution for agents.
- **Approval Lifecycle** — evaluate whether an action needs approval, build approval lifecycles, and transition them through states.
- **Decision Provenance** — structured decision records linking evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results.
- **Auditor Exports** — institutional auditor export combining all signals into a single structured record with section coverage, blockers, and audit-readiness status.
- **Compliance Readiness** — composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.
- **API / OpenAPI Contract** — versioned HTTP contract with stable paths, schemas, and compatibility expectations.
- **Audit / Event Records** — append-only event log capturing significant state changes with timestamps and actor references.
- **Persistence Layer** — the abstraction boundary for durable storage, currently implemented with SQLite and optional PostgreSQL.
- **Operator / Admin Access Boundary** — the role-based access model that ensures only authorized actors can mutate Product Core state.

## 5. Stable public contracts

The following are stable public contracts. They should evolve intentionally, not accidentally:

- API paths and request / response schemas
- Evidence bundle records
- Verification result records
- Provenance summaries
- Auditor export records
- Compliance readiness summaries
- Policy requirement results
- Permission evaluation results
- Approval lifecycle records
- Persistent IDs across workflow, grant, execution, evidence, and subject boundaries

Changes to these contracts require versioning, a deprecation policy, and explicit approval from the contract freeze process.

## 6. Extension boundaries

Extensions should operate at the following boundaries. They may replace or augment behavior in these areas, but must map their results into the stable Product Core contracts listed above.

- **Policy rule packs** — custom rule definitions that feed into the standard policy evaluation contract.
- **Evidence source adapters** — external evidence feeds mapped to the canonical evidence bundle shape.
- **Evidence verification strategies** — alternative or additional verification methods that still produce a standard verification result record.
- **Auditor export formats** — new output formats that still export the canonical auditor export record structure.
- **Compliance readiness dimensions** — additional readiness dimensions that feed into the standard readiness summary.
- **Permission profiles** — optional profile definitions evaluated within the standard permission contract.
- **Approval workflow profiles** — optional workflow patterns that still produce standard approval lifecycle records.
- **Storage / persistence backends** — replaceable storage implementations that preserve Product Core IDs and integrity constraints.
- **Auth / identity providers** — replaceable identity and authentication backends that still produce standard operator references and role assignments.
- **SDK / API clients** — generated or handwritten clients that speak the stable API contract.
- **Workflow orchestrator integrations** — external orchestrators that interact via the stable API contract.
- **Observability sinks** — metrics, logging, and alerting backends that consume standard event streams.
- **Optional blockchain anchoring** — periodic anchoring of integrity hashes to a blockchain for enhanced tamper evidence.
- **Optional wallet / payment integration** — wallet signatures, disbursement records, or payment receipts linked to grant executions via stable IDs.
- **Dashboard / UI layer** — client applications that consume the stable API contract without embedding Product Core logic.

## 7. Adapter rules

Adapters and extensions must follow these rules:

- **Adapters must not redefine Product Core records.** They must map into the stable Product Core contracts.
- **Adapters must map into stable Product Core contracts.** Every adapter output must be a valid Product Core record.
- **Adapters should be replaceable.** Two adapters for the same boundary should be interchangeable without changes to Product Core logic.
- **Adapters should not leak secrets into records or examples.** No plaintext tokens, private keys, or credentials should appear in adapter output.
- **Adapters should keep sensitive data off-chain.** Unless explicitly scoped, adapters should avoid writing sensitive fields to public ledgers.
- **Adapters should fail closed where appropriate.** Deny by default when mapping is ambiguous or validation fails.
- **Adapters should be tested independently from Product Core logic.** Adapter tests should not require full Product Core test fixtures.

## 8. Internal implementation details

The following should remain internal and should not become public contracts too early:

- Internal file layout and module organization
- Low-level helper function names and signatures
- SQLite test implementation details
- Exact storage implementation (schema, indices, migration ordering)
- Temporary demo defaults and synthetic data
- Local-only assumptions (e.g., single-machine deployment)
- Current test fixture layout
- Non-production auth shortcuts (e.g., admin-token bypass paths)

These may change during refactoring without violating the stable public contracts.

## 9. Explicit non-core areas

The following areas are **not Product Core right now**. They may be built later as extensions or separate products:

- Payment processing
- Wallet custody
- Blockchain dependency
- Public grant discovery / matchmaking
- Full SaaS tenant management
- Production dashboard product
- Legal / compliance certification
- HSM-backed signing implementation
- Hosted production deployment automation

These remain valid future directions, but Product Core must not depend on them.

## 10. Customization model

The following can be customized later without destabilizing the Product Core:

- Rule packs (policy requirements, exclusions, thresholds)
- Approval profiles (multi-step, quorum, delegated)
- Permission profiles (scope templates, role hierarchies)
- Evidence requirements (what counts as sufficient evidence per domain)
- Export formats (layout and serialization of auditor exports)
- Storage backend (SQLite, PostgreSQL, or future backend via the persistence boundary)
- Deployment / runtime configuration (environment variables, feature flags, container layout)
- Auth provider (local tokens, OAuth, SSO, mTLS)
- Client / SDK layer (Python, JavaScript, Go, etc.)
- UI / dashboard (React, Vue, mobile, etc.)
- Optional integrity anchoring (frequency, chain, anchoring service)

## 11. Recommended architecture evolution order

1. Freeze and validate API / OpenAPI contract boundaries.
2. Define the runtime configuration model.
3. Define the auth / operator access model.
4. Define the secret management baseline.
5. Define the persistence backend boundary.
6. Define extension / adaptor interface expectations.
7. Add SDK / client examples after contract stabilization.
8. Add UI / dashboard only after API and extension boundaries stabilize.
9. Keep blockchain / payment optional and outside Product Core.

## 12. Decision boundary

GrantLayer should be treated as a **modular product foundation**, not a one-off demo or pilot artifact.

Product Core contracts should be stable; integrations and deployment-specific behavior should remain replaceable. No extension should become a hidden dependency of the Product Core.

---

## See also

- [`docs/api_openapi_contract_hardening_review.md`](api_openapi_contract_hardening_review.md) — GL-064 API/OpenAPI contract hardening review
- [`docs/runtime_configuration_environment_model.md`](runtime_configuration_environment_model.md) — GL-066 runtime configuration and environment model
- [`docs/production_auth_operator_access_design.md`](production_auth_operator_access_design.md) — GL-067 production auth and operator access design
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/deployment_package_runtime_modes_design.md`](deployment_package_runtime_modes_design.md) — GL-069 deployment package and runtime modes design
- [`docs/product_core_readiness.md`](product_core_readiness.md) — Product Core readiness and endpoint inventory
- [`docs/examples/gl065/product_architecture_map.json`](examples/gl065/product_architecture_map.json) — machine-readable product architecture map
- [`docs/examples/gl065/extension_boundary_catalog.json`](examples/gl065/extension_boundary_catalog.json) — machine-readable extension boundary catalog
- [`backend/tests/test_gl065_product_architecture_extension_boundaries.py`](../backend/tests/test_gl065_product_architecture_extension_boundaries.py) — validation test for this architecture document and artifacts
