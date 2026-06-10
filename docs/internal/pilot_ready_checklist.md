# GrantLayer Pilot-Ready Checklist

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Repository and test gate

- [ ] `main` is clean (no uncommitted changes).
- [ ] `origin/main` is synced with the local branch.
- [ ] Full backend suite passes: `python3 -m unittest discover backend.tests -v`
- [ ] GL-059 validation test passes: `python3 -m unittest backend.tests.test_gl059_pilot_ready_handoff -v`

## 2. Required docs

- [ ] `docs/integration_guide.md` — Minimum Viable Integration Guide (GL-053).
- [ ] `docs/demo_scenario.md` — Integration Demo Scenario (GL-054).
- [ ] `docs/integration_ready_checklist.md` — Integration-Ready Checklist (GL-055).
- [ ] `docs/integration_ready_release_candidate.md` — Integration-Ready Release Candidate Review (GL-056).
- [ ] `docs/integrator_quickstart.md` — Integrator Quickstart (GL-057).
- [ ] `docs/minimal_api_usage_walkthrough.md` — Minimal API Usage Walkthrough (GL-058).
- [ ] `docs/pilot_ready_handoff_plan.md` — Pilot-Ready Handoff Plan (GL-059).
- [ ] `docs/pilot_ready_checklist.md` — Pilot-Ready Checklist (GL-059).

## 3. Required examples

- [ ] `backend/tests/fixtures/gl054_demo_scenario.json` — GL-054 demo fixture.
- [ ] `docs/examples/gl057/` — GL-057 quickstart example JSON files (12 files).
- [ ] `docs/examples/gl058/minimal_api_usage_walkthrough.json` — GL-058 walkthrough JSON.
- [ ] `docs/examples/gl059/pilot_handoff_package.json` — GL-059 pilot handoff package JSON.

## 4. Required validation tests

- [ ] `backend/tests/test_gl052_product_core_e2e_flow.py` — GL-052 Product Core E2E test.
- [ ] `backend/tests/test_gl054_demo_scenario_fixture.py` — GL-054 demo fixture validation.
- [ ] `backend/tests/test_gl055_integration_contract_readiness.py` — GL-055 contract/readiness validation.
- [ ] `backend/tests/test_gl057_integrator_quickstart_examples.py` — GL-057 quickstart example validation.
- [ ] `backend/tests/test_gl058_minimal_api_usage_walkthrough.py` — GL-058 walkthrough validation.
- [ ] `backend/tests/test_gl059_pilot_ready_handoff.py` — GL-059 pilot handoff validation.

## 5. Non-goals confirmed

The following items are **explicitly not included** in the pilot handoff and remain future production hardening work:

- [ ] Production auth (OAuth, JWT, SSO, HSM-backed key management).
- [ ] Production secrets (no HSM, no vault integration, no secret rotation).
- [ ] Deployment hardening (no containers, load balancing, TLS termination, or orchestration).
- [ ] Observability (no metrics, logging pipelines, alerting, or tracing).
- [ ] Backup / restore (no automated backup, point-in-time recovery, or disaster runbooks).
- [ ] SDKs (no Python, JavaScript, or Go client libraries).
- [ ] Blockchain / wallet / payment integrations.
- [ ] Legal / compliance certification (outputs are structured records, not legal advice).
- [ ] Dashboard / UI (the HTML dashboard is present but not a productized UI).
- [ ] Multi-tenant SaaS architecture (no tenant isolation, subscription billing, or SaaS onboarding).

## 6. Pilot handoff decision

| Decision | Status |
|----------|--------|
| Ready for technical pilot discussion | **Yes** |
| Ready for production deployment | **No** |

This checklist confirms that the Integration-Ready v0 artifacts (GL-052 through GL-058) are present, coherent, and validated, and that the GL-059 pilot handoff package turns them into a clear technical handoff for a first pilot discussion.

Production deployment requires the non-goals listed in Section 5 to be addressed in future sprints.

---

## See also

- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — full pilot handoff plan
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — Integration-Ready v0 consolidated review
- [`docs/integration_guide.md`](integration_guide.md) — minimum viable integration guide
