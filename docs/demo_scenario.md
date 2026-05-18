# GrantLayer Integration Demo Scenario

> GrantLayer turns agentic grant workflows into verifiable institutional records.

## 1. Purpose

This document provides a **deterministic, concrete example** for external integrators who want to understand how the GrantLayer Product Core can be used in a realistic institutional workflow.

The scenario below is:
- **Illustrative** — it shows realistic data shapes and relationships.
- **Deterministic** — stable identifiers are used so the fixture and tests are reproducible.
- **Non-production** — it does not include real auth, real funding, or live personal data.

It complements the Minimum Viable Integration Guide (`docs/integration_guide.md`) and the Product Core E2E test (`backend/tests/test_gl052_product_core_e2e_flow.py`).

## 2. Scenario overview

A **municipality** runs a microgrant workflow for a **community energy-efficiency project**.

An applicant (a community organisation) submits a grant request for a small public subsidy to install LED lighting in a local library. A grant operator receives the request, a review agent checks eligibility against published policy rules, and an operator approves the request. The grant is issued, the project is executed, evidence is collected and verified, and the final outcome is exported in an auditor-ready format.

This scenario covers the full Product Core flow from intake to compliance readiness.

## 3. Actors

| Actor | Role | Description |
|-------|------|-------------|
| `applicant` / `beneficiary` | Community organisation | Submits the grant request and later executes the funded action. |
| `grant-operator` | Municipality officer | Receives the request, coordinates review, and approves or rejects. |
| `review-agent` | Automated eligibility checker | Evaluates the request against policy rules (required evidence, exclusions, deadlines, amount limits). |
| `auditor` | Independent reviewer | Receives the institutional auditor export to verify decision provenance and evidence completeness. |

All actor identifiers in the fixture are stable demo IDs (e.g. `gl054-applicant-001`) and contain no real personal data.

## 4. Stable identifiers

The following stable identifiers are used throughout the fixture and scenario:

| Identifier | Value | Purpose |
|------------|-------|---------|
| `scenarioId` | `gl054-demo-scenario` | Identifies this demo scenario. |
| `workflowId` | `gl054-workflow-001` | Higher-level workflow spanning the full lifecycle. |
| `subjectId` | `gl054-subject-001` | The applicant / beneficiary actor. |
| `grantRequestId` | `gl054-request-001` | The original grant request. |
| `grantId` | `gl054-grant-001` | The approved and signed grant. |
| `executionId` | `gl054-execution-001` | The protected action attempt (project execution). |
| `evidenceId` | `gl054-evidence-001` | The evidence bundle for the execution. |
| `policyId` / `rulePackId` | `gl054-policy-001` | The policy rule pack evaluated against the subject. |
| `auditorExportId` | `gl054-auditor-export-001` | The institutional auditor export. |

These IDs are reused consistently across every section of the fixture so that an integrator can trace every reference from request to audit export.

## 5. Product Core flow mapping

The demo scenario maps to the GrantLayer Product Core flow as follows:

1. **Grant Request** — The applicant submits a structured request (`gl054-request-001`) with subject, role, action, resource, validity window, and reason.
2. **Approval** — A grant operator approves the request. The approval record references `gl054-request-001` and produces `gl054-grant-001`.
3. **Grant** — A signed Grant record is created with Ed25519 signature, SHA-256 payload hash, and `demo-ed25519-v1` signing key ID.
4. **Grant Execution** — The applicant executes the funded action (`gl054-execution-001`), linked to `gl054-grant-001`.
5. **Evidence** — An Evidence Bundle (`gl054-evidence-001`) aggregates the grant, execution, audit trail, and integrity hash.
6. **Evidence Verification** — The bundle hash is recomputed offline and compared to the stored evidence hash to detect tampering.
7. **Evidence Completeness** — A completeness score and readiness flag are computed from execution presence, evidence presence, verification status, and provenance events.
8. **Compliance Gap Report** — Automated gap detection maps findings to a severity catalogue (critical / high / medium / low) with recommended actions.
9. **Policy Requirements** — The policy rule pack (`gl054-policy-001`) is evaluated against the subject evidence and upstream signals.
10. **Decision Provenance** — A structured decision record combines evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results.
11. **Auditor Export** — An institutional auditor export (`gl054-auditor-export-001`) combines all signals into a single structured record with sections, blockers, and audit-readiness status.
12. **Compliance Readiness** — A composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions is produced for the workflow.

## 6. How to use the fixture

The fixture file (`backend/tests/fixtures/gl054_demo_scenario.json`) is an **illustrative JSON document** intended for:

- **Integrators** who want to see concrete data relationships before writing their own client code.
- **Test authors** who need a deterministic, coherent dataset for validation tests.
- **Documentation readers** who want to trace a single identifier (`gl054-workflow-001`) through every Product Core stage.

Important notes:
- The fixture is **not a live API contract**. Exact field contracts may vary; refer to the OpenAPI specification and production code for definitive schemas.
- It uses **stable IDs** so that demos, tests, and documentation all refer to the same coherent chain of events.
- It **complements** `docs/integration_guide.md` (the minimal integration guide) and `backend/tests/test_gl052_product_core_e2e_flow.py` (the E2E flow test).

## 7. Non-goals

This demo scenario and its fixture **explicitly do not** provide:

- **Production authentication** — no OAuth, JWT, SSO, or HSM-backed key management.
- **Deployment setup** — no containers, load balancing, TLS termination, or orchestration.
- **Real funding / payment flow** — no wallet integration, blockchain anchoring, or bank transfer logic.
- **Blockchain / wallet integration** — all integrity checks use standard SHA-256 and Ed25519.
- **Legal or compliance advice** — the outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Personally identifiable real data** — every actor, subject, and identifier is synthetic and deterministic.

GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.
