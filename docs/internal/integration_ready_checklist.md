# GrantLayer Integration-Ready Checklist

> GrantLayer turns agentic grant workflows into verifiable institutional records.
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This checklist defines the minimum artifact and verification gate for **Integration-Ready v0**.

Integration-Ready v0 means an external integrator can:

1. Read the OpenAPI contract and understand the current HTTP surface.
2. Run the full backend test suite and observe zero failures.
3. Trace a deterministic demo scenario from grant request through compliance readiness.
4. Verify that key artifacts (E2E test, demo pack, integration guide, OpenAPI contract validation) are present and coherent.

This is a **validation/readiness gate**, not a production feature.

## 2. Required artifacts

The following artifacts must be present in the repository for Integration-Ready v0:

| Artifact | Location | Purpose |
|----------|----------|---------|
| **Product Core E2E test** | `backend/tests/test_gl052_product_core_e2e_flow.py` | Proves the full institutional grant workflow from request to compliance readiness. |
| **Minimum Viable Integration Guide** | `docs/integration_guide.md` | Explains what GrantLayer is, what it solves, and how to integrate. |
| **Integration Demo Scenario** | `docs/demo_scenario.md` | Concrete, deterministic example for external integrators. |
| **Demo JSON fixture** | `backend/tests/fixtures/gl054_demo_scenario.json` | Reproducible dataset with stable IDs for every Product Core stage. |
| **Demo fixture validation test** | `backend/tests/test_gl054_demo_scenario_fixture.py` | Lightweight checks that the fixture is loadable, coherent, and free of obvious secrets. |
| **OpenAPI contract validation test** | `backend/tests/test_gl055_integration_contract_readiness.py` | Guards expected documented paths and rejects known legacy paths. |
| **Integration-Ready checklist** | `docs/integration_ready_checklist.md` | This document — the minimum artifact and verification gate definition. |

## 3. Product Core coverage

Integration-Ready v0 covers the following Product Core capabilities:

- **Grant Requests / Approvals** — create, approve, deny, revoke, expire; approval creates a linked Grant.
- **Grants** — active permission record with Ed25519 signature and SHA-256 payload hash.
- **Grant Executions** — one record per protected action attempt, linked to a Grant and Grant Request.
- **Evidence Persistence / Verification** — durable, immutable storage with hash-based lookup and offline recomputation.
- **Evidence Completeness** — structured score (0–100) and readiness flag derived from execution presence, evidence presence, verification status, and provenance events.
- **Compliance Gap Reports** — automated gap detection mapped to a severity catalogue (critical / high / medium / low) with recommended actions.
- **Policy Requirements** — machine-readable policy evaluation with required evidence, exclusions, deadlines, amount limits, required roles, and approval policies.
- **Decision Provenance** — structured decision record linking evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results.
- **Auditor Export** — institutional auditor export combining all signals into a single structured record with section coverage, blockers, and audit-readiness status.
- **Compliance Readiness** — composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.

## 4. Contract validation

The **OpenAPI contract validation test** (`backend/tests/test_gl055_integration_contract_readiness.py`) guards the Integration-Ready contract by:

- Verifying `docs/openapi.yaml` exists and is parseable.
- Confirming the `paths` section exists and is non-empty.
- Asserting that selected expected current paths are present (covering the main Product Core areas).
- Asserting that selected known legacy/wrong paths are absent.

If `docs/openapi.yaml` is missing expected contract paths or contains unexpected legacy paths, the test fails and the blocker is reported without editing the OpenAPI document.

## 5. Demo/readiness validation

The GL-054 demo pack and GL-052 E2E test support integrator confidence by providing:

- **Deterministic identifiers** reused across every Product Core stage (`gl054-workflow-001`, `gl054-subject-001`, etc.).
- **Coherent data relationships** — every artifact references the same workflow chain from request to audit export.
- **No real secrets** — all actor IDs, signatures, and hashes are synthetic demo values.
- **Testable assertions** — the fixture test validates JSON structure, stable ID consistency, link integrity, and absence of secret-like patterns.

## 6. Non-goals / future production hardening

Integration-Ready v0 **explicitly does not** include the following production hardening items:

- **OAuth / JWT / SSO** — authentication is admin-token or operator-token only.
- **Production secret management** — no HSM, no vault integration, no secret rotation.
- **Deployment hardening** — no containers, load balancing, TLS termination, or orchestration guidance.
- **Observability** — no metrics, logging pipelines, alerting, or tracing.
- **Backup / restore** — no automated backup, point-in-time recovery, or disaster runbooks.
- **PostgreSQL CI** — SQLite is the default; PostgreSQL support exists but is not CI-gated.
- **HSM / signing** — demo Ed25519 keypair only; no hardware key management.
- **SDKs** — no client libraries (Python, JavaScript, Go).
- **Blockchain / wallet / payment integrations** — integrity checks use standard SHA-256 and Ed25519 only.
- **Dashboard / UI** — the HTML dashboard is present but not a productized UI.
- **Multi-tenant SaaS architecture** — no tenant isolation, subscription billing, or SaaS onboarding.

## 7. Release gate

Integration-Ready v0 is achieved when **all** of the following are true:

1. **Full backend suite passing** — `python3 -m unittest discover backend.tests -v` runs with 0 failures and 0 errors.
2. **Integration guide present** — `docs/integration_guide.md` exists and covers the Product Core capabilities.
3. **Demo pack present** — `docs/demo_scenario.md`, `backend/tests/fixtures/gl054_demo_scenario.json`, and `backend/tests/test_gl054_demo_scenario_fixture.py` all exist and the fixture test passes.
4. **OpenAPI contract validation passing** — `backend/tests/test_gl055_integration_contract_readiness.py` passes, confirming expected paths are present and known legacy paths are absent.
5. **No P0/P1 known blockers** — there are no critical or high-severity issues blocking an external integrator from understanding and testing the API surface.

When these conditions are met, the branch is ready for merge-agent review and the Integration-Ready v0 milestone is complete.
