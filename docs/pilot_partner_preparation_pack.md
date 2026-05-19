# GrantLayer Pilot Partner Preparation Pack

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This pack turns the current Pilot-Ready GrantLayer artifacts into a practical package for a **first technical pilot partner discussion**.

It is not a production deployment plan, not an integration contract, and not a legal document. It is a structured preparation artifact that tells a partner what to review, what questions to answer, and what to expect from the meeting.

## 2. Current project status

| Milestone | Status |
|-----------|--------|
| Integration-Ready v0 | **Yes** |
| Pilot-Ready for technical review | **Yes** |
| Production-Ready | **No** |

Integration-Ready v0 and Pilot-Ready artifacts have been built and documented through GL-052 through GL-061. The Product Core flow is implemented, tested end-to-end, and supported by guides, demo scenarios, quickstart examples, an OpenAPI contract, validation tests, and a demo runner.

This preparation pack (GL-062) turns those artifacts into a single entry point for a partner-facing pilot discussion.

## 3. Ideal first pilot partner profile

An ideal first pilot partner is:

- **API-first technical evaluator** — can read OpenAPI contracts, run Python scripts, and inspect JSON artifacts without a dedicated UI.
- **Grant / funding workflow context** — understands grant requests, approval chains, evidence collection, or compliance reporting from an institutional perspective.
- **Evidence / audit / compliance need** — has a concrete reason to care about verifiable records, decision provenance, or institutional auditor exports.
- **Ability to review local / test artifacts** — can clone the repository, run the backend test suite, and inspect static examples on a local machine.
- **Willingness to identify production-hardening gaps** — can differentiate between what GrantLayer currently does and what production operation would require.
- **No expectation of production SaaS in this phase** — understands the current milestone is a technical pilot review, not a hosted service.

## 4. What the partner should review before the meeting

The following documents should be read before the pilot discussion:

- [`docs/integration_guide.md`](integration_guide.md) — explains what GrantLayer is, what it solves, and the Product Core capabilities.
- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples with stable identifiers for quick integrator onboarding.
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — API-first walkthrough mapping Product Core stages to OpenAPI paths.
- [`docs/demo_scenario.md`](demo_scenario.md) — concrete deterministic example with actor definitions and a realistic municipality microgrant scenario.
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — the technical handoff package that this preparation pack extends.
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — the formal release decision recording the current Pilot-Ready state.
- [`docs/demo_runner_api_smoke.md`](demo_runner_api_smoke.md) — GL-061 demo runner and API smoke script documentation.

## 5. Recommended pilot discussion flow

1. **Product statement and problem fit** — confirm the partner understands the core value proposition (agentic grant workflows → verifiable institutional records).
2. **Partner workflow overview** — the partner describes their current grant / funding workflow, pain points, and where verification gaps exist.
3. **GrantLayer Product Core walkthrough** — walk through the 12 Product Core stages from grant request to compliance readiness.
4. **Demo scenario review** — trace the municipality microgrant scenario and map it to the partner's domain.
5. **GL-057 example JSON review** — inspect the 12 static JSON examples and explain stable identifier relationships.
6. **GL-058 minimal API usage walkthrough** — map each Product Core stage to an OpenAPI path and explain contract boundaries.
7. **GL-061 demo runner dry-run** — run `python3 scripts/demo/gl061_api_smoke.py --dry-run` to show local artifact coherence.
8. **Integration touchpoint mapping** — identify where the partner's system would connect (intake, approval, evidence bundle, auditor export).
9. **Non-goals and production-hardening gaps** — explicitly surface what is not included and what production operation would require.
10. **Pilot success criteria** — review the checklist below and agree on what "success" means for this pilot phase.
11. **Next decision** — choose one of the recommended next paths documented in section 10.

## 6. Technical demo sequence

Run the following commands during or before the meeting to demonstrate artifact coherence:

```bash
# GL-061 demo runner dry-run
python3 scripts/demo/gl061_api_smoke.py --dry-run

# GL-062 pilot partner preparation pack validation
python3 -m unittest backend.tests.test_gl062_pilot_partner_preparation_pack -v

# GL-061 demo runner validation
python3 -m unittest backend.tests.test_gl061_demo_runner_api_smoke -v

# Full backend test suite
python3 -m unittest discover backend.tests -v
```

Expected outcome:
- **0 failures**
- **0 errors**
- Skipped count should remain at the project baseline (3 skipped for PostgreSQL-specific tests).

## 7. Partner questions to answer

The partner should be prepared to discuss the following question groups:

### Workflow fit
- What grant or funding workflows does your institution run today?
- Where do agents or automation already participate in those workflows?
- What are the biggest friction points between agentic steps and institutional approval?

### Evidence and records
- What evidence do you currently collect for a grant decision?
- How do you prove, after the fact, that a decision was correct and complete?
- Who requests the evidence (auditor, board, regulator, internal compliance)?

### Audit / compliance outputs
- What format do your auditors or compliance officers expect?
- Do you need machine-readable exports or human-readable reports?
- How often do you face audit requests that require reconstructing a decision chain?

### API integration expectations
- Would GrantLayer sit behind your existing systems, or would your systems call GrantLayer APIs?
- Do you need synchronous or asynchronous approval flows?
- What is your preferred API contract format (OpenAPI, GraphQL, gRPC)?

### Data / privacy boundaries
- What data would flow into GrantLayer (personally identifiable, financial, operational)?
- What data must stay inside your perimeter and never leave?
- Are there data-residency or cross-border transfer constraints?

### Auth / security expectations
- What authentication and authorization model do you use today (OAuth, SAML, API tokens, mutual TLS)?
- Do you require HSM-backed signing, or is software Ed25519 acceptable for a pilot?
- What identity provider do you use for operators and approvers?

### Pilot environment expectations
- Can you run the repository locally in your environment?
- Do you need a hosted demo instance, or is a self-run test acceptable?
- What database and runtime constraints do you have (Python version, container policy, network restrictions)?

### Production-hardening requirements
- What would you need to see before you could run this in production (auth, observability, backup, legal review)?
- Which of those are blockers for a pilot, and which are only blockers for production?
- What is your preferred priority order for hardening work?

### Success criteria
- What would convince you that GrantLayer solves your verification problem?
- What would convince you that it does *not* fit?
- What is a minimal viable pilot outcome you could present to your stakeholders?

### Blockers
- Are there any P0 or P1 blockers that would prevent a pilot from starting?
- Are there regulatory, procurement, or security-review gates that must be cleared first?
- Is there a hard deadline by which a pilot must show results?

## 8. Pilot success criteria

A pilot partner review is considered successful when:

1. **Partner understands the Product Core** — can describe the 12-stage flow from request to compliance readiness.
2. **Partner can map at least one workflow to GrantLayer records** — can translate a real internal process into grant request, approval, execution, and evidence stages.
3. **Partner can identify required API touchpoints** — knows which OpenAPI paths or internal events would trigger GrantLayer operations.
4. **Partner can evaluate evidence / compliance / auditor outputs** — can inspect an evidence bundle, completeness score, compliance gap report, and auditor export and explain their relevance.
5. **Partner confirms non-production constraints** — acknowledges that the current milestone is local / test only and that production hardening is a separate workstream.
6. **Partner identifies production-hardening priorities** — produces a ranked list of what production operation would require (e.g., OAuth, observability, backup, legal review).
7. **No P0 / P1 blocker prevents pilot planning** — there are no hard blockers that stop the next step from being a scoped pilot plan.

## 9. Explicit non-goals

The following are explicitly **not** in scope for the pilot partner discussion or the current milestone:

- **Production deployment** — no containers, load balancing, TLS termination, or orchestration instructions.
- **Production auth** — no OAuth, JWT, SSO, or HSM-backed key management; token-based auth is for local evaluation only.
- **Production secrets** — the repository uses a demo Ed25519 keypair and synthetic data.
- **Production observability** — no metrics, logging pipelines, alerting, or tracing.
- **Backup / restore** — no automated backup, point-in-time recovery, or disaster runbooks.
- **SDKs** — no client libraries (Python, JavaScript, Go).
- **Legal / compliance certification** — outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Blockchain / wallet / payment integration** — integrity checks use standard SHA-256 and Ed25519 only; no wallet, payment, or blockchain anchoring is implemented.
- **Dashboard / UI** — the HTML dashboard is present but not a productized UI and is not a pilot dependency.
- **Multi-tenant SaaS** — no tenant isolation, subscription billing, or SaaS onboarding.

## 10. Recommended next decision

After the partner review, the project should choose **one** of the following paths:

1. **Proceed to scoped pilot plan** — define a time-boxed pilot with the partner, specific success criteria, and a clear endpoint.
2. **Run local API smoke v2** — extend the GL-061 demo runner to exercise more edge cases or integrate a lightweight local API client.
3. **Prioritize production-hardening roadmap** — if the partner identifies critical gaps, rank them and plan a hardening sprint before the next partner discussion.
4. **Pause for API / OpenAPI contract hardening** — if the partner surfaces contract ambiguities, invest in tightening the OpenAPI specification and contract tests before proceeding.

The default recommended path is **1. proceed to scoped pilot plan**, because the Integration-Ready and Pilot-Ready artifacts are sufficient for planning, and the fastest way to learn is a real partner engagement.

---

## See also

- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — GL-059 pilot-ready handoff plan
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — GL-060 pilot-ready release decision
- [`docs/demo_runner_api_smoke.md`](demo_runner_api_smoke.md) — GL-061 demo runner / API smoke script
- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — GL-057 minimal static JSON examples
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — GL-058 API-first walkthrough
- [`docs/examples/gl062/pilot_partner_questionnaire.json`](examples/gl062/pilot_partner_questionnaire.json) — machine-readable partner questionnaire
- [`docs/examples/gl062/pilot_review_agenda.json`](examples/gl062/pilot_review_agenda.json) — machine-readable pilot review agenda
