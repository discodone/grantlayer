# GrantLayer API/OpenAPI Contract Hardening Review

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This review separates **Pilot-Ready API contract confidence** from **Production-Ready API contract requirements**.

It does not change the API surface, the OpenAPI specification, or any backend behavior. It evaluates the current contract from an Integration-Ready / Pilot-Ready perspective and identifies what must be hardened before any Production-Ready claim can be made.

The review is intended for internal planning, partner expectation-setting, and Merge Agent review before any production-hardening sprint begins.

## 2. Current readiness state

| Milestone | Status |
|-----------|--------|
| Integration-Ready API review | **Yes** |
| Pilot-Ready API review | **Yes, with non-production constraints** |
| Production-Ready API contract | **No** |

GrantLayer has completed Integration-Ready and Pilot-Ready artifacts through GL-052 through GL-063. The Product Core flow is implemented, tested end-to-end, and supported by guides, demo scenarios, quickstart examples, an OpenAPI contract, validation tests, a demo runner, and a pilot partner preparation pack. The current API contract is sufficient for pilot evaluation, but it is not yet hardened for production.

## 3. Current contract artifacts

The following artifacts constitute the current API/OpenAPI contract baseline:

| Artifact | Location | Purpose |
|----------|----------|---------|
| **OpenAPI specification** | `docs/openapi.yaml` | Definitive HTTP surface, schema definitions, and security model. |
| **Integration-Ready checklist** | `docs/integration_ready_checklist.md` | Minimum artifact and verification gate definition for Integration-Ready v0. |
| **Integration-Ready release candidate** | `docs/integration_ready_release_candidate.md` | Consolidated Integration-Ready v0 review after GL-052 through GL-055. |
| **Minimum API usage walkthrough** | `docs/minimal_api_usage_walkthrough.md` | Step-by-step API-first walkthrough mapping Product Core stages to OpenAPI paths. |
| **Demo runner / API smoke** | `docs/demo_runner_api_smoke.md` | Lightweight executable local confidence check for Pilot-Ready artifacts. |
| **Production-hardening roadmap** | `docs/production_hardening_roadmap.md` | Separates Pilot-Ready from Production-Ready and lists prioritized workstreams. |
| **Production readiness cut** | `docs/production_readiness_cut.md` | Readiness cut that records what is in place and what is missing for production. |
| **Integration contract readiness test** | `backend/tests/test_gl055_integration_contract_readiness.py` | Guards expected OpenAPI paths and rejects known legacy paths. |
| **Minimal API usage walkthrough test** | `backend/tests/test_gl058_minimal_api_usage_walkthrough.py` | Validates walkthrough alignment with OpenAPI paths and GL-057 examples. |
| **Demo runner smoke test** | `backend/tests/test_gl061_demo_runner_api_smoke.py` | Validates smoke manifest, referenced examples, and dry-run behavior. |

## 4. What is sufficient for Pilot-Ready review

The following conditions make the current API contract sufficient for Pilot-Ready evaluation:

- **OpenAPI exists** — `docs/openapi.yaml` is present, parseable, and documents the full HTTP surface including paths, methods, request/response schemas, and security schemes.
- **Current readiness gate exists** — `backend/tests/test_gl055_integration_contract_readiness.py` verifies that expected paths are present and known legacy paths are absent.
- **Minimal walkthrough references documented paths where declared** — `docs/minimal_api_usage_walkthrough.md` maps every Product Core stage to a concrete OpenAPI path that is verified against `docs/openapi.yaml`.
- **Demo runner validates dry-run sequence** — `scripts/demo/gl061_api_smoke.py` validates the smoke manifest and referenced examples without requiring network access or secrets.
- **Backend tests provide current confidence** — the full backend suite passes with zero failures and zero errors, and targeted tests (GL-055, GL-058, GL-061) confirm artifact coherence.
- **Docs clearly state non-production constraints** — every checklist, walkthrough, and decision document explicitly notes that authentication, deployment, observability, and multi-tenancy are not production-ready.

## 5. Why Production-Ready API contract is still no

The following gaps prevent the API contract from being described as Production-Ready:

- **Contract freeze process is not established** — there is no documented versioning strategy, breaking-change policy, or contract review cadence. The OpenAPI version is a release candidate (`0.31.0-rc`), not a frozen production baseline.
- **Auth semantics are not production-grade** — the OpenAPI documents `LegacyAdminToken` and `OperatorToken` security schemes, but several endpoints do not currently enforce authentication. The `security` blocks describe the target contract, not the fully implemented state.
- **Error responses may need stronger standardization** — while `ErrorResponse` is referenced consistently, the exact field contracts (`error`, `errorCode`, `reason`) are described in prose rather than enforced by a single reusable schema with examples for every status code.
- **Schema examples may need expansion** — many request and response schemas do not include illustrative examples, making integrator onboarding harder at scale.
- **Endpoint versioning policy is not formalized** — paths such as `/decision-provenance/v2/build` indicate versioning by URL, but the policy (when to bump, how long to support old versions) is undocumented.
- **Compatibility/deprecation policy is not formalized** — there is no documented rule for how long legacy paths or fields remain supported, how deprecation is announced, or how breaking changes are communicated to integrators.
- **CI contract validation may need hardening** — the GL-055 test checks path presence and legacy-path absence, but it does not validate schema completeness, example coverage, or OpenAPI semantic correctness.
- **External SDK/client expectations are not finalized** — without a frozen contract, generated clients would be unstable. SDK readiness is explicitly a post-contract-freeze concern.

## 6. P0 contract-hardening workstreams

P0 workstreams are blockers for any Production-Ready API contract claim. They must be addressed before GrantLayer can be described as having a production-grade API contract.

1. **Define production API contract freeze process**
   - Document who can approve contract changes, what qualifies as a breaking change, and how the freeze is announced.
   - Acceptance gate: a documented contract freeze process and a versioned OpenAPI artifact with a non-RC version.

2. **Confirm endpoint inventory and legacy path policy**
   - Produce a complete inventory of every documented path, its maturity level, and whether it is candidate for deprecation.
   - Acceptance gate: an endpoint inventory document with maturity labels (stable / experimental / deprecated).

3. **Standardize error response schema**
   - Ensure every error response references a single, strongly typed `ErrorResponse` schema with required fields, example values, and documented status-code mappings.
   - Acceptance gate: OpenAPI `ErrorResponse` schema is complete and every error status code uses it consistently.

4. **Harden auth/permission contract documentation**
   - Clarify which endpoints enforce authentication today, which are target-only, and what the migration path is from legacy admin-token to operator-token or future OAuth/JWT.
   - Acceptance gate: auth/permission contract document that aligns OpenAPI `security` blocks with implementation truth.

5. **Validate OpenAPI path/schema coverage**
   - Audit every path for missing request examples, missing response examples, undocumented query parameters, and inconsistent field naming.
   - Acceptance gate: coverage report with zero undocumented public paths and zero schemas lacking examples.

6. **Add CI gate for OpenAPI contract validation**
   - Extend existing tests or CI to lint the OpenAPI document for structural correctness, schema completeness, and semantic consistency.
   - Acceptance gate: a CI stage that fails if OpenAPI is structurally invalid or if documented paths lack schemas.

7. **Document compatibility and deprecation rules**
   - Define how long deprecated paths remain available, how breaking changes are versioned, and how integrators are notified.
   - Acceptance gate: a published compatibility and deprecation policy document.

## 7. P1 pilot-expansion workstreams

P1 workstreams improve pilot confidence and integration readiness but are not strict production blockers for the API contract itself.

1. **Add richer request/response examples**
   - Provide illustrative JSON examples for every request body and every success response.
   - Acceptance gate: every POST/PUT/PATCH request body and every 2xx response has at least one `example` or `examples` entry.

2. **Add integrator-focused endpoint grouping**
   - Use OpenAPI `tags` or external documentation to group endpoints by Product Core area (Grant Requests, Grants, Evidence, Compliance, Auditor Export, etc.).
   - Acceptance gate: integrators can navigate the OpenAPI document by Product Core concept without reading the full path list.

3. **Add planned-call smoke validation against documented paths**
   - Extend the GL-061 demo runner or create a new planned-call test that validates every documented path has a corresponding example or fixture.
   - Acceptance gate: a machine-readable report mapping every OpenAPI path to at least one example or test fixture.

4. **Document pagination/filter/query conventions**
   - Standardize how list endpoints accept pagination, filtering, and sorting, and document these conventions in the OpenAPI specification or an integration guide.
   - Acceptance gate: a conventions document referenced by the OpenAPI spec.

5. **Align demo runner with API usage walkthrough**
   - Ensure the GL-061 smoke manifest and the GL-058 walkthrough reference the exact same OpenAPI paths in the same order.
   - Acceptance gate: a coherence test proving every walkthrough step has a matching smoke manifest entry.

6. **Add contract review checklist for pilot partners**
   - Provide a short checklist that a pilot partner can use to evaluate whether the current contract meets their integration needs.
   - Acceptance gate: partner-facing contract review checklist document.

## 8. P2 productization workstreams

P2 workstreams expand the API contract into a productized platform surface but should only be pursued after pilot validation and P0 contract hardening.

1. **SDK/client generation readiness**
   - Evaluate OpenAPI generator compatibility, produce minimal generated clients, and document integration patterns.
   - Acceptance gate: generated Python and TypeScript clients compile and pass basic integration tests against a local server.

2. **Versioned API policy**
   - Formalize URL versioning (e.g., `/v1/...`, `/v2/...`) or header versioning, and document the migration path between versions.
   - Acceptance gate: a versioned API policy document and a proof-of-concept versioned path.

3. **Public changelog process**
   - Establish a machine-readable and human-readable changelog for every contract change.
   - Acceptance gate: changelog exists and is updated automatically from merged contract changes.

4. **Advanced schema linting**
   - Adopt a linter (e.g., Spectral) to enforce naming conventions, example coverage, and security scheme consistency.
   - Acceptance gate: linter passes in CI with a documented rule set.

5. **External conformance test pack**
   - Build or adopt a third-party conformance test suite that validates the running API against the OpenAPI contract.
   - Acceptance gate: conformance tests pass against a local GrantLayer instance.

6. **Dashboard/API alignment after pilot validation**
   - Ensure the HTML dashboard uses the same endpoints and field names as the documented contract, reducing drift.
   - Acceptance gate: dashboard network traffic audit shows no usage of undocumented paths or fields.

## 9. Recommended hardening order

The recommended order prioritizes contract stability and clarity before tooling or client generation:

1. **Endpoint inventory and path stability review** — know what exists, what is stable, and what is legacy.
2. **Error response consistency review** — standardize the error contract so integrators can handle failures predictably.
3. **Auth/permission contract documentation review** — align OpenAPI security blocks with implementation truth.
4. **OpenAPI schema/example coverage review** — fill gaps in examples and schema definitions.
5. **CI OpenAPI validation gate** — automate structural and semantic checks so contract regressions are caught before merge.
6. **Planned-call smoke validation** — ensure every documented path has a corresponding example or test fixture.
7. **Compatibility/deprecation policy** — give integrators confidence that breaking changes will be managed.
8. **SDK/client readiness after pilot validation** — only after the contract is frozen and the pilot has confirmed integration patterns.

## 10. What not to change yet

The project should **not** immediately:

- **Rename endpoints** — path stability is more important than naming perfection at this stage.
- **Remove legacy paths** — deprecation must follow a documented policy and a communicated timeline.
- **Generate SDKs** — SDK generation requires a frozen contract and stable version.
- **Add a versioned public API surface** — versioning policy must be defined before adding `/v1/` or `/v2/` prefixes.
- **Change auth behavior** — auth hardening is a separate production-hardening workstream (see GL-063 P0); the contract should document the target model without forcing an implementation change.
- **Rewrite OpenAPI broadly** — large-scale restructuring risks introducing errors and breaking existing integrations.

Any of these changes should only be pursued if a pilot issue or a production-hardening issue explicitly scopes that change.

## 11. Decision boundary

GrantLayer may be described as having a **Pilot-Ready API contract review baseline**, but must **not** be described as having a **Production-Ready API contract** until P0 contract gates are implemented and verified.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production API timelines, reference this review, the P0 workstream list, and the GL-063 production-hardening roadmap.

---

## See also

- [`docs/openapi.yaml`](openapi.yaml) — definitive API contract
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap with prioritized workstreams
- [`docs/production_readiness_cut.md`](production_readiness_cut.md) — GL-063 production readiness cut
- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — GL-060 pilot-ready release decision
- [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — Integration-Ready v0 checklist
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — minimal API usage walkthrough
- [`docs/demo_runner_api_smoke.md`](demo_runner_api_smoke.md) — GL-061 demo runner / API smoke script
- [`docs/examples/gl064/api_contract_hardening_backlog.json`](examples/gl064/api_contract_hardening_backlog.json) — machine-readable API contract hardening backlog
- [`docs/examples/gl064/api_contract_readiness_snapshot.json`](examples/gl064/api_contract_readiness_snapshot.json) — machine-readable API contract readiness snapshot
- [`backend/tests/test_gl064_api_openapi_contract_hardening_review.py`](../backend/tests/test_gl064_api_openapi_contract_hardening_review.py) — validation test for this review and its artifacts
