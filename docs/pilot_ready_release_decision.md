# GrantLayer Pilot-Ready Release Decision

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Executive decision

| Decision | Status |
|----------|--------|
| Ready for first technical pilot discussion | **Yes** |
| Ready for pilot planning | **Yes, with non-production constraints** |
| Ready for production deployment | **No** |

GrantLayer has completed the Integration-Ready v0 artifact chain (GL-052 through GL-058) and the Pilot-Ready Handoff Plan (GL-059). This release decision (GL-060) formally records the current state and confirms the project is ready for a first technical pilot discussion.

## 2. Basis for the decision

The following prior blocks constitute the basis for this decision:

- **GL-052 Product Core E2E Flow Test** — proves the full institutional grant workflow using real module execution.
- **GL-053 Minimum Viable Integration Guide** — explains what GrantLayer is, what it solves, and the Product Core capabilities.
- **GL-054 Integration Demo Pack** — provides a deterministic demo scenario and coherent JSON fixture.
- **GL-055 Integration Contract & Readiness Gate** — guards the OpenAPI contract and validates artifact presence.
- **GL-056 Integration-Ready Release Candidate Review** — consolidates the Integration-Ready v0 state.
- **GL-057 Integrator Quickstart Examples** — provides minimal static JSON examples for quick integrator onboarding.
- **GL-058 Minimal API Usage Walkthrough** — step-by-step API-first walkthrough mapping Product Core stages to OpenAPI paths.
- **GL-059 Pilot-Ready Handoff Plan** — packages Integration-Ready v0 into a clear technical handoff for pilot discussions.

## 3. Supporting artifacts

The following documents are present and validated:

- `docs/integration_guide.md`
- `docs/demo_scenario.md`
- `docs/integration_ready_checklist.md`
- `docs/integration_ready_release_candidate.md`
- `docs/integrator_quickstart.md`
- `docs/minimal_api_usage_walkthrough.md`
- `docs/pilot_ready_handoff_plan.md`
- `docs/pilot_ready_checklist.md`

The following example directories and files are present and validated:

- `backend/tests/fixtures/gl054_demo_scenario.json` — GL-054 demo fixture
- `docs/examples/gl057/` — GL-057 quickstart example JSON files (12 files)
- `docs/examples/gl058/minimal_api_usage_walkthrough.json` — GL-058 walkthrough JSON
- `docs/examples/gl059/pilot_handoff_package.json` — GL-059 machine-readable handoff summary

## 4. Supporting validation tests

The following tests are present, expected to pass, and guard coherence:

- `backend/tests/test_gl052_product_core_e2e_flow.py`
- `backend/tests/test_gl054_demo_scenario_fixture.py`
- `backend/tests/test_gl055_integration_contract_readiness.py`
- `backend/tests/test_gl057_integrator_quickstart_examples.py`
- `backend/tests/test_gl058_minimal_api_usage_walkthrough.py`
- `backend/tests/test_gl059_pilot_ready_handoff.py`
- `backend/tests/test_gl060_pilot_ready_release_decision.py`

## 5. What a pilot can evaluate

A pilot partner can evaluate the following Product Core areas:

- **Product Core flow** — grant request, approval, grant creation, execution, evidence, and audit export.
- **Grant request / approval / grant records** — lifecycle states, linked identifiers, and deterministic signatures.
- **Execution and evidence relationships** — how a protected action attempt produces an evidence bundle.
- **Evidence completeness** — structured scoring (0–100) and readiness flag derived from execution presence, evidence presence, verification status, and provenance events.
- **Compliance gap reports** — automated gap detection mapped to a severity catalogue (critical / high / medium / low) with recommended actions.
- **Policy requirements** — machine-readable policy evaluation with required evidence, exclusions, deadlines, amount limits, required roles, and approval policies.
- **Decision provenance** — structured decision record linking evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results.
- **Auditor export** — institutional auditor export combining all signals into a single structured record with section coverage, blockers, and audit-readiness status.
- **Compliance readiness** — composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.
- **Integration artifacts and example flows** — static JSON examples, demo fixtures, walkthroughs, validation tests, and the `docs/openapi.yaml` contract.

## 6. Constraints and non-goals

The following constraints apply to any pilot evaluation or planning:

- **Local / test environment only** — unless the partner separately deploys, all verification runs against a local SQLite database.
- **No production auth** — authentication is admin-token or operator-token only; no OAuth, JWT, SSO, or HSM-backed key management.
- **No production secrets** — the repository uses a demo Ed25519 keypair and synthetic data.
- **No production observability** — no metrics, logging pipelines, alerting, or tracing.
- **No production backup / restore** — no automated backup, point-in-time recovery, or disaster runbooks.
- **No SDK** — no client libraries (Python, JavaScript, Go).
- **No legal / compliance certification** — outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **No payment / blockchain integration** — integrity checks use standard SHA-256 and Ed25519 only; no wallet, payment, or blockchain anchoring is implemented.
- **No dashboard dependency** — the HTML dashboard is present but not a productized UI.
- **No multi-tenant SaaS architecture** — no tenant isolation, subscription billing, or SaaS onboarding.

## 7. Release decision

GrantLayer should be treated as **Pilot-Ready for technical review and pilot planning**, not **Production-Ready**.

The current state is sufficient for:
- First technical pilot discussion with an external partner.
- Pilot planning scoped to non-production constraints.
- Evaluating Product Core flow, evidence completeness, compliance readiness, and integration artifacts.

The current state is **not sufficient** for:
- Production deployment.
- Production data processing.
- External user-facing SaaS operation.

## 8. Recommended next workstream options

After this release decision, the following next workstream options are available:

1. **Demo Runner / API Smoke Script** — a lightweight executable script (e.g., Python or cURL) that hits the running API to verify core flows and produce a confidence report.
2. **First Pilot Partner Preparation** — select a target institution, define pilot success criteria for that partner, and prepare a hosted demo instance or deployment package.
3. **Production-Hardening Roadmap** — prioritize production readiness epics (OAuth/JWT, secret management, observability, backup/restore, multi-tenancy, SaaS architecture).

**Default recommended next block: Demo Runner / API Smoke Script.**

Rationale:
- It converts existing docs/examples into an executable local confidence check.
- It avoids committing to production hardening before pilot feedback is collected.
- It gives a pilot partner a more practical onboarding path than static JSON alone.

## 9. Stop conditions before pilot

Do not proceed to a pilot discussion if any of the following blockers are present:

- The full backend suite is failing.
- OpenAPI / readiness validation is failing.
- Any pilot handoff artifact is missing or unreadable.
- Non-goals are unclear or have been silently promoted to in-scope features.
- Production readiness is being claimed accidentally or implicitly.
- Secrets, credentials, or real personal data appear in examples, fixtures, or documentation.

## 10. Machine-readable record

A deterministic JSON decision record is available at:

- `docs/examples/gl060/pilot_ready_decision_record.json`

This record is validated by `backend/tests/test_gl060_pilot_ready_release_decision.py`.

---

## See also

- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — GL-059 pilot-ready handoff plan
- [`docs/pilot_ready_checklist.md`](pilot_ready_checklist.md) — GL-059 pilot-ready checklist
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — GL-056 Integration-Ready v0 consolidated review
