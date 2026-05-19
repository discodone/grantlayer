# GrantLayer Pilot-Ready Handoff Plan

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document packages **Integration-Ready v0** into a clear, self-contained technical handoff package for a first pilot or integration discussion with an external partner.

It is not a production deployment plan. It is a technical handoff artifact that tells a partner what they can evaluate, what they must have on hand, and what constraints apply.

## 2. Current status

| Milestone | Status |
|-----------|--------|
| Integration-Ready v0 | **Yes** |
| Pilot planning ready | **Yes, with non-production constraints** |
| Production-ready | **No** |

Integration-Ready v0 has been built and documented through GL-052 through GL-058. The Product Core flow is implemented, tested end-to-end, and supported by guides, demo scenarios, quickstart examples, an OpenAPI contract, and validation tests.

This handoff plan (GL-059) turns those artifacts into a single entry point for pilot discussions.

## 3. What a pilot partner can evaluate

A pilot partner can evaluate the following Product Core areas using the artifacts in this repository:

- **Product Core flow** — grant request, approval, grant creation, execution, evidence, and audit export.
- **Grant request / approval / grant records** — lifecycle states, linked identifiers, and deterministic signatures.
- **Execution and evidence relationship** — how a protected action attempt produces an evidence bundle.
- **Evidence completeness** — structured scoring (0–100) and readiness flag derived from execution presence, evidence presence, verification status, and provenance events.
- **Compliance gap reports** — automated gap detection mapped to a severity catalogue (critical / high / medium / low) with recommended actions.
- **Policy requirements** — machine-readable policy evaluation with required evidence, exclusions, deadlines, amount limits, required roles, and approval policies.
- **Decision provenance** — structured decision record linking evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results.
- **Auditor export** — institutional auditor export combining all signals into a single structured record with section coverage, blockers, and audit-readiness status.
- **Compliance readiness** — composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.
- **Integration artifacts and examples** — static JSON examples, demo fixtures, walkthroughs, validation tests, and the `docs/openapi.yaml` contract.

## 4. Required handoff artifacts

The following artifacts must be present and coherent for the handoff to be considered complete:

| Artifact | Location | Purpose |
|----------|----------|---------|
| **Minimum Viable Integration Guide** | `docs/integration_guide.md` | Explains what GrantLayer is, what it solves, and the Product Core capabilities. |
| **Integration Demo Scenario** | `docs/demo_scenario.md` | Concrete deterministic example for external integrators with actor definitions. |
| **Integration-Ready Checklist** | `docs/integration_ready_checklist.md` | Minimum artifact and verification gate for Integration-Ready v0. |
| **Integration-Ready Release Candidate Review** | `docs/integration_ready_release_candidate.md` | Consolidated Integration-Ready v0 state after GL-052 through GL-057. |
| **Integrator Quickstart** | `docs/integrator_quickstart.md` | Minimal static JSON examples for quick integrator onboarding. |
| **Minimal API Usage Walkthrough** | `docs/minimal_api_usage_walkthrough.md` | Step-by-step API-first walkthrough mapping Product Core stages to OpenAPI paths. |
| **Pilot-Ready Handoff Plan** | `docs/pilot_ready_handoff_plan.md` | This document — the technical handoff package for pilot discussions. |
| **Pilot-Ready Checklist** | `docs/pilot_ready_checklist.md` | Validation gate for pilot readiness. |
| **GL-057 Quickstart Examples** | `docs/examples/gl057/` | 12 static JSON files covering every Product Core stage. |
| **GL-058 Walkthrough JSON** | `docs/examples/gl058/minimal_api_usage_walkthrough.json` | Machine-readable walkthrough index with stable IDs and OpenAPI path references. |
| **GL-059 Handoff Package JSON** | `docs/examples/gl059/pilot_handoff_package.json` | Machine-readable pilot handoff summary. |
| **Product Core E2E test** | `backend/tests/test_gl052_product_core_e2e_flow.py` | Proves the full institutional grant workflow using real module execution. |
| **Integration Contract & Readiness Gate** | `backend/tests/test_gl055_integration_contract_readiness.py` | Guards the OpenAPI contract and validates artifact presence. |
| **Minimal API Walkthrough Test** | `backend/tests/test_gl058_minimal_api_usage_walkthrough.py` | Validates the walkthrough document, JSON, and GL-057 example coherence. |
| **Pilot Handoff Validation Test** | `backend/tests/test_gl059_pilot_ready_handoff.py` | Validates that the handoff plan, checklist, and package JSON are present and coherent. |

## 5. Recommended pilot walkthrough

For a first pilot or integration discussion, follow this order:

1. **Read the Integration Guide** (`docs/integration_guide.md`) to understand what GrantLayer is and what it solves.
2. **Review the Integration-Ready Release Candidate** (`docs/integration_ready_release_candidate.md`) to confirm the current milestone scope.
3. **Open the Demo Scenario** (`docs/demo_scenario.md`) to see a concrete, realistic workflow with actors and stable identifiers.
4. **Inspect the GL-057 Example JSONs** (`docs/examples/gl057/`) to understand the data shapes produced at each Product Core stage.
5. **Follow the GL-058 Minimal API Usage Walkthrough** (`docs/minimal_api_usage_walkthrough.md`) to map each stage to an OpenAPI path.
6. **Run the targeted validation tests** — GL-052, GL-054, GL-055, GL-057, GL-058, and GL-059 tests — to confirm coherence.
7. **Run the full backend suite** (`python3 -m unittest discover backend.tests -v`) to confirm zero failures and zero errors.
8. **Record pilot-specific questions and blockers** in a separate document or issue tracker for the next sprint.

## 6. Technical verification gate

Run the following commands to verify the handoff package before a pilot discussion:

```bash
# GL-059 pilot handoff validation
python3 -m unittest backend.tests.test_gl059_pilot_ready_handoff -v

# GL-058 minimal API usage walkthrough validation
python3 -m unittest backend.tests.test_gl058_minimal_api_usage_walkthrough -v

# GL-055 integration contract readiness validation
python3 -m unittest backend.tests.test_gl055_integration_contract_readiness -v

# Full backend suite
python3 -m unittest discover backend.tests -v
```

Expected outcome:
- **0 failures**
- **0 errors**
- Skipped count should remain at the project baseline (3 skipped for PostgreSQL-specific tests).

## 7. Pilot constraints

The following constraints apply to any pilot evaluation:

- **Local / test environment only** — unless the partner separately deploys the codebase, all verification runs against a local SQLite database.
- **No production auth** — authentication is admin-token or operator-token only; no OAuth, JWT, SSO, or HSM-backed key management.
- **No production secrets** — the repository uses a demo Ed25519 keypair and synthetic data.
- **No production observability** — no metrics, logging pipelines, alerting, or tracing.
- **No production backup / restore** — no automated backup, point-in-time recovery, or disaster runbooks.
- **No SDK** — no client libraries (Python, JavaScript, Go).
- **No legal / compliance certification** — outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **No payment / blockchain integration** — integrity checks use standard SHA-256 and Ed25519 only; no wallet, payment, or blockchain anchoring is implemented.
- **No dashboard dependency** — the HTML dashboard is present but not a productized UI.

## 8. Pilot success criteria

A pilot discussion is considered successful when:

1. The partner understands the core flow (request → approval → grant → execution → evidence → audit).
2. The partner can follow the minimal walkthrough and trace stable identifiers through every stage.
3. The partner can inspect the demo fixture and static examples and understand the data relationships.
4. The partner can identify where their system would integrate (e.g., at the grant-request intake, the approval step, the evidence bundle, or the auditor export).
5. The partner can list missing production requirements and differentiate them from the current Integration-Ready v0 scope.
6. **No P0/P1 integration blockers** are found in the handoff artifacts (docs, examples, tests, or OpenAPI contract).

## 9. Known risks and questions

The following risks and open questions should be discussed with the pilot partner:

- **OpenAPI may still need later hardening** — the current contract is verified for expected and legacy paths, but external security review may reveal gaps.
- **Production deployment not yet specified** — no containers, load balancing, TLS termination, or orchestration guidance exists.
- **Auth model not production-ready** — no OAuth, JWT, SSO, or HSM-backed key management; token-based auth is for local evaluation only.
- **External service integration not yet implemented** — no webhooks, external identity providers, or third-party evidence sources are connected.
- **Compliance outputs are structured records, not legal advice** — auditor exports, gap reports, and readiness summaries support institutional audit workflows but do not replace legal or regulatory review.
- **Blockchain anchoring is an optional future integrity enhancement** — all current integrity checks use standard SHA-256 and Ed25519 signatures; blockchain anchoring is not required for Product Core.

## 10. Recommended next decisions

After the first pilot discussion, the team should decide:

1. **Choose first pilot target / partner profile** — which institution or use case is the best fit for an early pilot.
2. **Define pilot environment expectations** — will the partner run locally, or will GrantLayer provide a hosted demo instance.
3. **Decide whether to build a small demo runner or API smoke script** — a lightweight runnable script (e.g., Python or cURL) that hits the running API may improve partner confidence.
4. **Decide production-hardening priority** — rank OAuth/JWT, secret management, observability, backup/restore, and multi-tenancy for post-pilot sprints.
5. **Decide whether SDK / client examples are needed** — evaluate whether a minimal Python or JavaScript client would accelerate partner integration.

---

## See also

- [`docs/pilot_ready_checklist.md`](pilot_ready_checklist.md) — pilot-ready validation gate
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — GL-060 pilot-ready release decision
- [`docs/demo_runner_api_smoke.md`](demo_runner_api_smoke.md) — GL-061 demo runner / API smoke script
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — Integration-Ready v0 consolidated review
- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — API-first walkthrough
- [`docs/integration_guide.md`](integration_guide.md) — minimum viable integration guide
- [`docs/demo_scenario.md`](demo_scenario.md) — deterministic demo scenario
- [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — Integration-Ready v0 checklist
- [`docs/examples/gl059/pilot_handoff_package.json`](examples/gl059/pilot_handoff_package.json) — machine-readable handoff summary
- [`docs/pilot_partner_preparation_pack.md`](pilot_partner_preparation_pack.md) — GL-062 pilot partner preparation pack
