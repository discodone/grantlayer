# GrantLayer Minimal API Usage Walkthrough

> GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This walkthrough shows the **minimal API-first Product Core sequence** an external integrator should follow to understand the GrantLayer institutional grant flow.

It maps each stage to:
- a concrete Product Core area
- an example JSON file from the GL-057 quickstart examples
- stable identifiers that tie every stage together
- an OpenAPI path where one exists and is verified in `docs/openapi.yaml`

This document is intended for technical integrators who want to understand the API surface by tracing a single coherent workflow from grant request through compliance readiness.

## 2. Before you start

Familiarity with the following documents will make this walkthrough easier to follow:

- [`docs/integration_guide.md`](integration_guide.md) — explains what GrantLayer is, what it solves, the Product Core capabilities, and the minimal integration flow.
- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples with stable identifiers and deterministic data shapes.
- [`docs/demo_scenario.md`](demo_scenario.md) — a concrete deterministic walkthrough with actor definitions and a realistic scenario (municipality microgrant).
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — the consolidated Integration-Ready v0 review after GL-052 through GL-057.

## 3. Stable identifiers used throughout

The walkthrough reuses the same stable identifiers from the GL-057 quickstart examples so that every stage connects to the same coherent workflow:

| Identifier | Value | Appears in |
|------------|-------|------------|
| `workflowId` | `gl057-workflow-001` | Grant request, compliance gap report, decision provenance, auditor export, compliance readiness, minimal flow bundle |
| `subjectId` | `gl057-subject-001` | Grant request, grant, compliance gap report, decision provenance, compliance readiness |
| `grantRequestId` | `gl057-request-001` | Grant request, approval result, grant, grant execution, evidence item |
| `grantId` | `gl057-grant-001` | Grant, grant execution, evidence item, evidence completeness, auditor export, compliance readiness |
| `executionId` | `gl057-execution-001` | Grant execution, evidence item, evidence completeness, compliance gap report, decision provenance, auditor export, compliance readiness |
| `evidenceId` | `gl057-evidence-001` | Evidence item, minimal flow bundle |
| `policyId` / `policyPackId` | `gl057-policy-001` | Policy requirements result, minimal flow bundle |
| `auditorExportId` | `gl057-auditor-export-001` | Auditor export, minimal flow bundle |

`minimal_flow_bundle.json` collects all of these IDs in a single place so that an integrator can verify link integrity without opening every file.

## 4. Minimal walkthrough sequence

The steps below follow the natural Product Core flow from intake to audit. Each step includes its purpose, the GL-057 example file, the relevant Product Core area, and an OpenAPI path when one is present in `docs/openapi.yaml`.

> **Note:** Where an OpenAPI path is listed, it is verified against `docs/openapi.yaml`. Steps without a listed OpenAPI path are illustrative internal concepts rather than exact API contracts.

### Step 1 — Grant Request

- **Purpose:** Create a structured grant request capturing the subject, role, action, resource, validity window, and reason.
- **Input example:** [`docs/examples/gl057/grant_request.json`](examples/gl057/grant_request.json)
- **Output / next ID:** `gl057-request-001`
- **Product Core area:** Grant Requests / Approvals
- **OpenAPI path:** `POST /grant-requests`
- **Contract note:** Documented OpenAPI POST path. Field contracts are definitive in `docs/openapi.yaml`.

### Step 2 — Approval Result

- **Purpose:** Approve the request and produce a linked Grant record with an approval decision.
- **Input example:** [`docs/examples/gl057/approval_result.json`](examples/gl057/approval_result.json)
- **Output / next ID:** `gl057-grant-001`
- **Product Core area:** Grant Requests / Approvals
- **OpenAPI path:** `POST /grant-requests/{id}/approve`
- **Contract note:** Documented OpenAPI POST path. Approval atomically creates the linked Grant.

### Step 3 — Grant

- **Purpose:** Retrieve the signed Grant record containing Ed25519 signature, SHA-256 payload hash, and signing key ID.
- **Input example:** [`docs/examples/gl057/grant.json`](examples/gl057/grant.json)
- **Output / next ID:** `gl057-grant-001`
- **Product Core area:** Grants
- **OpenAPI path:** `GET /grants/{id}`
- **Contract note:** Documented OpenAPI GET path. The Grant is created during approval and contains GL-050 integrity fields.

### Step 4 — Grant Execution

- **Purpose:** Record the protected action attempt, linking the Execution to the Grant and the original Grant Request.
- **Input example:** [`docs/examples/gl057/grant_execution.json`](examples/gl057/grant_execution.json)
- **Output / next ID:** `gl057-execution-001`
- **Product Core area:** Grant Executions
- **OpenAPI path:** `POST /grant-executions`
- **Contract note:** Documented OpenAPI POST path. Each execution represents one protected action attempt.

### Step 5 — Evidence Item

- **Purpose:** Build an Evidence Bundle aggregating the grant, execution, audit trail, and a deterministic SHA-256 integrity hash.
- **Input example:** [`docs/examples/gl057/evidence_item.json`](examples/gl057/evidence_item.json)
- **Output / next ID:** `gl057-evidence-001`
- **Product Core area:** Evidence Persistence / Verification
- **OpenAPI path:** `GET /evidence/executions/{id}`
- **Contract note:** Documented OpenAPI GET path. Returns the evidence bundle for a given execution.

### Step 6 — Evidence Completeness

- **Purpose:** Compute a structured completeness score and readiness flag from execution presence, evidence presence, verification status, and provenance events.
- **Input example:** [`docs/examples/gl057/evidence_completeness.json`](examples/gl057/evidence_completeness.json)
- **Output / next ID:** *(report output)*
- **Product Core area:** Evidence Completeness
- **OpenAPI path:** `GET /evidence/executions/{id}/completeness`
- **Contract note:** Documented OpenAPI GET path. Provides a machine-readable completeness assessment.

### Step 7 — Compliance Gap Report

- **Purpose:** Generate automated gap detection mapped to a severity catalogue with recommended actions.
- **Input example:** [`docs/examples/gl057/compliance_gap_report.json`](examples/gl057/compliance_gap_report.json)
- **Output / next ID:** *(report output)*
- **Product Core area:** Compliance Gap Reports
- **OpenAPI path:** `GET /compliance/gaps/executions/{id}`
- **Contract note:** Documented OpenAPI GET path. Returns critical/high/medium/low gaps for the execution.

### Step 8 — Policy Requirements Result

- **Purpose:** Evaluate machine-readable policy rules against subject evidence, exclusions, deadlines, amount limits, required roles, and approval policies.
- **Input example:** [`docs/examples/gl057/policy_requirements_result.json`](examples/gl057/policy_requirements_result.json)
- **Output / next ID:** *(evaluation output)*
- **Product Core area:** Policy Requirements / Rule Packs
- **OpenAPI path:** `POST /policy-requirements/evaluate`
- **Contract note:** Documented OpenAPI POST path. Returns a policy evaluation result with blockers and warnings.

### Step 9 — Decision Provenance Summary

- **Purpose:** Synthesize evidence completeness, compliance gaps, permissions, approvals, provenance events, and policy results into a single structured decision record.
- **Input example:** [`docs/examples/gl057/decision_provenance_summary.json`](examples/gl057/decision_provenance_summary.json)
- **Output / next ID:** `gl057-decision-001`
- **Product Core area:** Decision Provenance
- **OpenAPI path:** `POST /decision-provenance/v2/build`
- **Contract note:** Documented OpenAPI POST path. Builds a decision provenance summary for the execution.

### Step 10 — Auditor Export

- **Purpose:** Produce an institutional auditor export combining all upstream signals into a single structured record with section coverage, blockers, and audit-readiness status.
- **Input example:** [`docs/examples/gl057/auditor_export.json`](examples/gl057/auditor_export.json)
- **Output / next ID:** `gl057-auditor-export-001`
- **Product Core area:** Auditor Reports / Auditor Exports
- **OpenAPI path:** `POST /auditor/exports/build`
- **Contract note:** Documented OpenAPI POST path. Builds an exportable auditor record for the workflow.

### Step 11 — Compliance Readiness Summary

- **Purpose:** Build a composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.
- **Input example:** [`docs/examples/gl057/compliance_readiness_summary.json`](examples/gl057/compliance_readiness_summary.json)
- **Output / next ID:** *(summary output)*
- **Product Core area:** Compliance Readiness
- **OpenAPI path:** `POST /compliance/readiness/build`
- **Contract note:** Documented OpenAPI POST path. Returns the final readiness verdict for the workflow.

## 5. How IDs flow through the system

The same stable identifiers tie together every Product Core stage:

1. `gl057-workflow-001` is declared in the Grant Request and referenced by downstream reports and exports.
2. `gl057-subject-001` represents the actor and appears in the request, grant, compliance gap, decision provenance, and readiness summary.
3. `gl057-request-001` is created at intake, then referenced by the approval, grant, execution, and evidence.
4. `gl057-grant-001` is produced by approval and becomes the permission anchor for execution, evidence, and audit export.
5. `gl057-execution-001` records the protected action and feeds into evidence, completeness, compliance gaps, decision provenance, and auditor export.
6. `gl057-evidence-001` is the evidence bundle for the execution.
7. `gl057-policy-001` is the evaluated policy rule pack.
8. `gl057-auditor-export-001` is the final institutional export that pulls every upstream signal together.

Because every example file uses the same IDs, an integrator can trace any reference forward or backward through the workflow without ambiguity.

## 6. How this relates to existing artifacts

This walkthrough is built on top of earlier Integration-Ready artifacts and does not replace them:

- **GL-052 E2E test** (`backend/tests/test_gl052_product_core_e2e_flow.py`) proves the same Product Core flow using real module execution against a temporary database.
- **GL-053 integration guide** (`docs/integration_guide.md`) explains the system architecture and capabilities at a higher level.
- **GL-054 demo pack** (`docs/demo_scenario.md` and `backend/tests/fixtures/gl054_demo_scenario.json`) provides a narrative-driven scenario with more detailed actor definitions.
- **GL-055 contract/readiness gate** (`backend/tests/test_gl055_integration_contract_readiness.py`) guards the OpenAPI contract and validates artifact presence.
- **GL-057 quickstart examples** (`docs/examples/gl057/`) supply the concrete JSON files referenced by every step in this walkthrough.

## 7. Local verification

Run the targeted walkthrough validation test:

```bash
python3 -m unittest backend.tests.test_gl058_minimal_api_usage_walkthrough -v
```

Run the full backend test suite to confirm no regressions were introduced:

```bash
python3 -m unittest discover backend.tests -v
```

The full suite is expected to pass with 0 failures and 0 errors.

## 8. Non-goals

This walkthrough **explicitly does not** provide:

- **Production authentication** — no OAuth, JWT, SSO, or HSM-backed key management.
- **Deployment guidance** — no containers, load balancing, TLS termination, or orchestration instructions.
- **Live API client** — this walkthrough references static JSON files and OpenAPI paths, not runnable cURL or Python client examples against a running service.
- **SDKs** — no client libraries (Python, JavaScript, Go).
- **Blockchain / wallet / payment integrations** — integrity checks use standard SHA-256 and Ed25519 only.
- **Legal or compliance advice** — the outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Production hardening** — the examples use a demo Ed25519 keypair and synthetic data.
- **OpenAPI modifications** — `docs/openapi.yaml` is not changed by this task. Paths are referenced as documented.

## See also

- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples for quick integrator onboarding
- [`docs/integration_guide.md`](integration_guide.md) — minimum viable integration guide
- [`docs/demo_scenario.md`](demo_scenario.md) — deterministic demo scenario with actors
- [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — Integration-Ready v0 checklist
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — Integration-Ready v0 release candidate review
- [`docs/openapi.yaml`](openapi.yaml) — definitive API contract
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — pilot-ready handoff plan for first integration discussion
- [`docs/demo_runner_api_smoke.md`](demo_runner_api_smoke.md) — GL-061 demo runner / API smoke script
