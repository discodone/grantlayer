# GrantLayer Integrator Quickstart

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This quickstart helps external technical integrators understand the **minimal Product Core flow** using static example JSON files.

Instead of running code, you can read the examples, trace the stable identifiers through every stage, and understand the data relationships GrantLayer produces before you write your first API client call.

## 2. Before you start

Familiarity with the following documents will make the examples easier to follow:

- [`docs/integration_guide.md`](integration_guide.md) — explains what GrantLayer is, what it solves, the Product Core capabilities, and the minimal integration flow.
- [`docs/demo_scenario.md`](demo_scenario.md) — a concrete deterministic walkthrough with actor definitions and a realistic scenario (municipality microgrant).
- [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — the minimum artifact and verification gate for Integration-Ready v0.
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — the consolidated Integration-Ready v0 review after GL-052 through GL-055.

## 3. Minimal flow

The quickstart examples cover the same 12 Product Core stages as the E2E test and demo scenario:

1. **Grant Request** — a subject requests permission to perform an action on a resource within a validity window.
2. **Approval Result** — an authorized approver reviews the request and produces an approval record linked to a new Grant.
3. **Grant** — a signed permission record (Ed25519 signature, SHA-256 payload hash) issued after approval.
4. **Grant Execution** — the protected action is attempted, producing an execution record linked to the Grant and the original request.
5. **Evidence Item** — an Evidence Bundle aggregating the grant, execution, audit trail, and an integrity hash.
6. **Evidence Completeness** — a structured score and readiness flag derived from execution presence, evidence presence, verification status, and provenance events.
7. **Compliance Gap Report** — automated gap detection mapped to a severity catalogue with recommended actions.
8. **Policy Requirements Result** — machine-readable policy evaluation against evidence, exclusions, deadlines, amount limits, and required roles.
9. **Decision Provenance Summary** — a structured decision record combining evidence completeness, compliance gaps, permissions, approvals, provenance events, and policy results.
10. **Auditor Export** — an institutional auditor export combining all signals into a single structured record.
11. **Compliance Readiness Summary** — a composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions.

The examples are ordered to match the natural flow from intake to audit.

## 4. Example files

All quickstart examples are located in `docs/examples/gl057/`:

| File | Stage | Description |
|------|-------|-------------|
| `grant_request.json` | 1 | A minimal Grant Request with subject, role, action, resource, and reason. |
| `approval_result.json` | 2 | An approval record referencing the request and producing the grant. |
| `grant.json` | 3 | A signed Grant with Ed25519 signature, payload hash, and signing key ID. |
| `grant_execution.json` | 4 | An execution record linking the grant, request, and workflow. |
| `evidence_item.json` | 5 | An Evidence Bundle with grant summary, execution summary, audit trail, and SHA-256 hash. |
| `evidence_completeness.json` | 6 | A completeness report showing a full score and readiness status. |
| `compliance_gap_report.json` | 7 | A compliance gap report with no gaps and no recommended actions. |
| `policy_requirements_result.json` | 8 | A policy evaluation showing a passed status with no blockers. |
| `decision_provenance_summary.json` | 9 | A decision provenance record synthesising all upstream signals. |
| `auditor_export.json` | 10 | An auditor export pulling together every signal into a single audit-ready document. |
| `compliance_readiness_summary.json` | 11 | A readiness summary scoring all dimensions as ready. |
| `minimal_flow_bundle.json` | — | A lightweight index listing every artifact, its path, and the stable IDs that connect them. |

## 5. Stable identifier strategy

The examples reuse the same stable identifiers so that every file connects to the same coherent workflow:

| Identifier | Value | Appears in |
|------------|-------|------------|
| `workflowId` | `gl057-workflow-001` | All files except isolated policy evaluation |
| `subjectId` | `gl057-subject-001` | Grant request, grant, compliance gap, decision provenance, compliance readiness |
| `grantRequestId` | `gl057-request-001` | Grant request, approval, grant, execution, evidence |
| `grantId` | `gl057-grant-001` | Grant, execution, evidence, evidence completeness, auditor export, compliance readiness |
| `executionId` | `gl057-execution-001` | Execution, evidence, evidence completeness, compliance gap, decision provenance, auditor export, compliance readiness |
| `evidenceId` | `gl057-evidence-001` | Evidence item, minimal flow bundle |
| `policyId` / `policyPackId` | `gl057-policy-001` | Policy requirements result, minimal flow bundle |
| `auditorExportId` | `gl057-auditor-export-001` | Auditor export, minimal flow bundle |

`minimal_flow_bundle.json` collects all of these IDs in a single place so that an integrator can verify link integrity without opening every file.

## 6. How to use these examples

- **Examples are illustrative** — they show realistic data shapes but are not a canonical API schema.
- **Examples help integrators understand relationships** — trace `gl057-request-001` from request through grant, execution, evidence, and audit export.
- **Examples are not a live API contract** — exact field contracts may vary. Refer to `docs/openapi.yaml` for the definitive HTTP surface and field contracts.
- **OpenAPI remains the API contract** — the examples complement the OpenAPI document; they do not replace it.
- **GL-052 E2E test validates the Product Core flow** — `backend/tests/test_gl052_product_core_e2e_flow.py` proves the same flow using real module execution.
- **GL-054 demo fixture gives a coherent scenario** — `backend/tests/fixtures/gl054_demo_scenario.json` provides a more detailed, narrative-driven dataset.
- **GL-055 contract/readiness test guards integration artifacts** — `backend/tests/test_gl055_integration_contract_readiness.py` validates artifact presence, OpenAPI path expectations, and legacy path absence.

## 7. Local verification

Run the targeted quickstart validation test:

```bash
python3 -m unittest backend.tests.test_gl057_integrator_quickstart_examples -v
```

Run the full backend test suite to confirm no regressions were introduced:

```bash
python3 -m unittest discover backend.tests -v
```

The full suite is expected to pass with 0 failures and 0 errors.

## 8. Non-goals

This quickstart **explicitly does not** provide:

- **Production authentication** — no OAuth, JWT, SSO, or HSM-backed key management.
- **Deployment guidance** — no containers, load balancing, TLS termination, or orchestration instructions.
- **Live API client** — these are static JSON files, not runnable cURL or Python client examples.
- **SDKs** — no client libraries (Python, JavaScript, Go).
- **Blockchain / wallet / payment integrations** — integrity checks use standard SHA-256 and Ed25519 only.
- **Legal or compliance advice** — the outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Production hardening** — the examples use a demo Ed25519 keypair and synthetic data.

## See also

- [`docs/integration_guide.md`](integration_guide.md) — minimum viable integration guide
- [`docs/demo_scenario.md`](demo_scenario.md) — deterministic demo scenario with actors
- [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — Integration-Ready v0 checklist
- [`docs/integration_ready_release_candidate.md`](integration_ready_release_candidate.md) — Integration-Ready v0 release candidate review
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — minimal API usage walkthrough mapping Product Core stages to OpenAPI paths
- [`docs/openapi.yaml`](openapi.yaml) — definitive API contract
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — pilot-ready handoff plan for first integration discussion
