# GrantLayer Production-Hardening Roadmap

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This roadmap separates **Pilot-Ready** status from **Production-Ready** requirements.

It does not implement production hardening. It documents what GrantLayer already has, what is sufficient for first technical pilot discussions, what is still missing for production deployment, and which production-hardening workstreams should be prioritized next.

The roadmap is intended for internal planning, partner expectation-setting, and Merge Agent review before any production-hardening sprint begins.

## 2. Current readiness state

| Milestone | Status |
|-----------|--------|
| Integration-Ready v0 | **Yes** |
| Pilot-Ready for technical review | **Yes, with non-production constraints** |
| Production-Ready | **No** |

GrantLayer has completed Integration-Ready and Pilot-Ready artifacts through GL-052 through GL-062. The Product Core flow is implemented, tested end-to-end, and supported by guides, demo scenarios, quickstart examples, an OpenAPI contract, validation tests, a demo runner, and a pilot partner preparation pack.

## 3. What is already ready

The following prior blocks constitute the existing readiness foundation:

- **GL-052 Product Core E2E Flow Test** — proves the full institutional grant workflow using real module execution.
- **GL-053 Minimum Viable Integration Guide** — explains what GrantLayer is, what it solves, and the Product Core capabilities.
- **GL-054 Integration Demo Pack** — provides a deterministic demo scenario and coherent JSON fixture.
- **GL-055 Integration Contract & Readiness Gate** — guards the OpenAPI contract and validates artifact presence.
- **GL-056 Integration-Ready Release Candidate Review** — consolidates the Integration-Ready v0 state.
- **GL-057 Integrator Quickstart Examples** — provides minimal static JSON examples for quick integrator onboarding.
- **GL-058 Minimal API Usage Walkthrough** — step-by-step API-first walkthrough mapping Product Core stages to OpenAPI paths.
- **GL-059 Pilot-Ready Handoff Plan** — packages Integration-Ready v0 into a clear technical handoff for pilot discussions.
- **GL-060 Pilot-Ready Release Decision** — formally records the current Pilot-Ready state and confirms readiness for a first technical pilot discussion.
- **GL-061 Demo Runner / API Smoke Script** — lightweight executable local confidence check that validates the smoke manifest and referenced examples without network access.
- **GL-062 Pilot Partner Preparation Pack** — turns the Pilot-Ready artifacts into a practical package for a first technical pilot partner discussion.

## 4. Why production-ready is still no

The following gaps prevent GrantLayer from being described as Production-Ready:

- **Production auth is not implemented** — authentication is admin-token or operator-token only; no OAuth, JWT, SSO, or HSM-backed key management.
- **Production secrets are not managed** — the repository uses a demo Ed25519 keypair and synthetic data; no vault integration, secret rotation, or HSM.
- **Deployment hardening is not specified** — no containers, load balancing, TLS termination, orchestration, or environment-specific configuration guidance exists.
- **Observability is not implemented** — no metrics, logging pipelines, alerting, or tracing.
- **Backup/restore is not defined** — no automated backup, point-in-time recovery, or disaster runbooks.
- **PostgreSQL CI is not established** — SQLite is the default; PostgreSQL support exists but is not CI-gated.
- **OpenAPI may need contract hardening** — the current contract is verified for expected and legacy paths, but a freeze process and external security review may reveal gaps.
- **SDK/client story is not complete** — no client libraries (Python, JavaScript, Go) or structured client examples exist.
- **Dashboard/UI is not production-ready** — the HTML dashboard is present but not a productized UI and is not a pilot dependency.
- **Multi-tenant SaaS architecture is not designed** — no tenant isolation, subscription billing, or SaaS onboarding.
- **Compliance/legal review is not certification** — outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Blockchain/wallet/payment are optional future integrations** — integrity checks use standard SHA-256 and Ed25519 only; no wallet, payment, or blockchain anchoring is implemented. These are not required for Product Core.

## 5. P0 production-hardening workstreams

P0 workstreams are blockers for any production deployment claim. They must be addressed before GrantLayer can be described as Production-Ready.

1. **Production auth model**
   - Define the authentication and authorization architecture (OAuth 2.0, JWT, SSO, mutual TLS, or API tokens with rotation).
   - Specify identity provider integration, role mapping, and token lifecycle.
   - Acceptance gate: a documented auth decision record and a local proof-of-concept implementation plan.

2. **Secret management**
   - Replace the demo Ed25519 keypair with a managed secret strategy.
   - Define key rotation, encryption-at-rest, and access-control boundaries.
   - Acceptance gate: a secret-management plan with no synthetic keys in the repository.

3. **Deployment environment definition**
   - Document target runtime(s), container strategy, network topology, and environment separation (dev, staging, prod).
   - Acceptance gate: environment definition document and a reproducible local deployment target.

4. **Database production readiness**
   - Establish PostgreSQL as the CI-gated production database.
   - Define connection pooling, migration strategy, schema validation, and performance baseline.
   - Acceptance gate: PostgreSQL passes in CI alongside SQLite; migration rollback tested.

5. **Backup/restore plan**
   - Define automated backup schedule, retention policy, point-in-time recovery, and disaster runbooks.
   - Acceptance gate: documented backup/restore procedure with a tested recovery scenario.

6. **Observability baseline**
   - Define minimum metrics (health, latency, error rate), structured logging, and alerting thresholds.
   - Acceptance gate: a local observability stack that captures the baseline signals.

7. **CI gate definition**
   - Define the minimum CI pipeline (lint, type check, unit tests, contract tests, secret scan).
   - Acceptance gate: all P0 CI stages pass before any merge to main.

8. **API/OpenAPI contract freeze process**
   - Define versioning strategy, breaking-change policy, and contract review cadence.
   - Acceptance gate: a documented contract freeze process and a versioned OpenAPI artifact.

9. **Data privacy and evidence-handling boundaries**
   - Define what data may enter GrantLayer, what must stay in the partner perimeter, and how evidence retention maps to regulatory requirements.
   - Acceptance gate: a data-classification matrix and evidence retention policy draft.

## 6. P1 pilot-expansion workstreams

P1 workstreams improve pilot confidence and integration readiness but are not strict production blockers.

1. **Local API smoke v2 or planned-call validation**
   - Extend the GL-061 demo runner to exercise more edge cases or integrate a lightweight local API client.
   - Acceptance gate: the smoke script validates additional paths and produces a machine-readable confidence report.

2. **SDK/client examples**
   - Produce minimal Python and/or JavaScript client examples for common flows.
   - Acceptance gate: client examples exist, are tested, and map to the OpenAPI contract.

3. **External integration checklist**
   - Document how a partner system connects to GrantLayer (intake, approval, evidence bundle, auditor export).
   - Acceptance gate: a partner-facing integration checklist with touchpoint definitions.

4. **Pilot-specific environment documentation**
   - Document how a partner can run GrantLayer locally or in a hosted demo instance.
   - Acceptance gate: partner environment setup guide with verified commands.

5. **Operator/admin runbook**
   - Document common operations (restart, migrate, rotate key, inspect evidence, export audit record).
   - Acceptance gate: a runbook covering the most frequent operator tasks.

6. **Audit/export review workflow**
   - Document how an auditor or compliance officer reviews an exported record.
   - Acceptance gate: auditor review workflow with example output and interpretation guide.

7. **Evidence retention policy draft**
   - Draft a policy covering evidence lifespan, immutable storage guarantees, and deletion constraints.
   - Acceptance gate: a policy document reviewed by at least one stakeholder.

## 7. P2 productization workstreams

P2 workstreams expand GrantLayer into a productized platform but should only be pursued after pilot validation.

1. **Dashboard/UI**
   - Productize the HTML dashboard into a robust, accessible, and responsive UI.
   - Acceptance gate: UI supports all Product Core stages and passes basic accessibility checks.

2. **Multi-tenant SaaS architecture**
   - Design tenant isolation, subscription billing, onboarding, and per-tenant configuration.
   - Acceptance gate: architecture decision record and a local multi-tenant proof of concept.

3. **HSM/key-management upgrade path**
   - Plan migration from software Ed25519 signing to HSM-backed key management.
   - Acceptance gate: HSM integration plan with vendor-agnostic interface definition.

4. **Blockchain anchoring**
   - Design optional blockchain anchoring for enhanced integrity proofs.
   - Acceptance gate: anchoring design document with cost, latency, and reversibility analysis.

5. **Wallet/payment integrations**
   - Design optional wallet or payment integration for grant disbursement.
   - Acceptance gate: integration design document with security and compliance review.

6. **Advanced observability**
   - Add distributed tracing, custom business metrics, and SLO dashboards.
   - Acceptance gate: tracing covers end-to-end grant flow; SLOs are defined and measured.

7. **Formal compliance review support**
   - Prepare artifacts and documentation to support external compliance or security review.
   - Acceptance gate: compliance package with architecture diagrams, data-flow maps, and control matrices.

## 8. Recommended implementation order

The recommended order prioritizes contract clarity and executable validation before infrastructure investment:

1. **API/OpenAPI contract hardening review** — freeze the contract, version it, and resolve any ambiguities surfaced by pilot partners.
2. **Production auth and secret-management plan** — decide the auth model and secret strategy before any production deployment is designed.
3. **Local API smoke v2 / planned-call validation** — extend executable confidence checks to cover more paths and edge cases.
4. **Deployment/environment definition** — define where GrantLayer will run before building containers or orchestration.
5. **Observability and backup/restore plan** — define how the system is watched and recovered before accepting live data.
6. **PostgreSQL CI** — make PostgreSQL a first-class CI target so production database changes are gated.
7. **SDK/client examples** — give partners code they can copy and adapt.
8. **Dashboard/UI or multi-tenant architecture** — only after pilot validation confirms product-market fit and integration patterns.

## 9. What not to build yet

The project should not immediately build the following unless a pilot requirement explicitly demands it:

- **Full SaaS dashboard** — the HTML dashboard is sufficient for local evaluation.
- **Blockchain/payment layer** — integrity is currently handled by SHA-256 and Ed25519.
- **HSM integration** — software signing is acceptable for pilots.
- **Multi-tenant platform** — single-tenant or self-hosted is the current assumption.
- **Production deployment automation** — manual deployment documentation is sufficient for the first pilot.

Building these prematurely risks wasted effort before pilot feedback validates the core integration patterns.

## 10. Decision boundary

GrantLayer may be described as **Pilot-Ready for technical review**, but must **not** be described as **Production-Ready** until P0 gates are implemented and verified.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production timelines, reference this roadmap and the P0 workstream list.

---

## See also

- [`docs/production_readiness_cut.md`](production_readiness_cut.md) — GL-063 production readiness cut
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — GL-060 pilot-ready release decision
- [`docs/pilot_partner_preparation_pack.md`](pilot_partner_preparation_pack.md) — GL-062 pilot partner preparation pack
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — GL-059 pilot-ready handoff plan
- [`docs/examples/gl063/production_hardening_backlog.json`](examples/gl063/production_hardening_backlog.json) — machine-readable production hardening backlog
- [`docs/examples/gl063/production_readiness_cut.json`](examples/gl063/production_readiness_cut.json) — machine-readable production readiness cut
- [`backend/tests/test_gl063_production_hardening_roadmap.py`](../backend/tests/test_gl063_production_hardening_roadmap.py) — validation test for this roadmap and readiness cut
