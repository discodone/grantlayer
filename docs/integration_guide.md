# GrantLayer Minimum Viable Integration Guide

> GrantLayer turns agentic grant workflows into verifiable institutional records.

## 1. What GrantLayer is

GrantLayer is an **API-first verification, audit, and compliance layer** for agentic grant and funding workflows.

When AI agents prepare funding applications, evaluate eligibility, collect evidence, or trigger approval decisions, institutions need a neutral verification layer — one that makes every step traceable, tamper-evident, and independently auditable. GrantLayer is that layer.

GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 2. What problem GrantLayer solves

Agentic grant workflows naturally produce large volumes of unstructured activity. Institutions face several operational risks without a verification layer:

- **Auditability gaps** — it is hard to prove what an agent decided, when, and why.
- **Evidence fragmentation** — supporting documents, timestamps, and decisions live in separate systems.
- **Compliance uncertainty** — policy rules, exclusion checks, and approval thresholds are hard to verify after the fact.
- **Trust and liability** — institutions need machine-readable records they can share with auditors, boards, or regulators.

GrantLayer solves this by turning every significant workflow event into a **structured, signed, hash-verified record** with built-in completeness scoring, compliance gap detection, and institutional auditor exports.

## 3. Product Core capabilities

The following capabilities form the current Product Core:

| Capability | Description |
|-----------|-------------|
| **Grant Requests / Approvals** | A request can be created, approved, denied, revoked, or expired. Approval creates a linked Grant. |
| **Grants** | An active permission record (subject, role, action, resource, time window) with an Ed25519 signature and SHA-256 payload hash. |
| **Grant Executions** | One record per protected action attempt,.linked to a Grant and a Grant Request. |
| **Evidence Bundles** | A safe, flat JSON bundle aggregating the full grant lifecycle for a single execution, with a deterministic SHA-256 integrity hash. |
| **Evidence Persistence** | Durable, immutable storage for evidence bundles with hash-based lookup and verification. |
| **Evidence Verification** | Offline recomputation of the evidence hash to detect tampering or corruption. |
| **Evidence Completeness** | A structured score (0–100) and readiness flag derived from execution presence, evidence presence, verification status, and provenance events. |
| **Compliance Gap Reports** | Automated gap detection mapped to a severity catalogue (critical / high / medium / low) with recommended actions. |
| **Agent Permissions** | Scope-based permission evaluation, permission profiles, and assignment resolution for agents. |
| **Approval Rules / Approval Lifecycle** | Evaluate whether an action needs approval, build approval lifecycles, and transition them through states. |
| **Policy Requirements / Rule Packs** | Machine-readable policy evaluation with required evidence, exclusions, deadlines, amount limits, required roles, and approval policies. |
| **Decision Provenance** | A structured decision record linking evidence completeness, compliance gaps, permissions, approvals, provenance events, auditor findings, and policy results. |
| **Auditor Reports / Auditor Exports** | Institutional auditor export combining all signals into a single structured record with section coverage, blockers, and audit-readiness status. |
| **Compliance Readiness** | A composite readiness summary across evidence, compliance, permission, approval, provenance, auditor, and policy dimensions. |

## 4. Local setup and verification

GrantLayer is a Python project. The following commands have been verified in the reference environment:

```bash
cd /home/adminuser/projects/grantlayer-mvp
python3 -m unittest discover backend.tests -v
```

The full backend suite is expected to pass with:
- **1141 tests**
- 0 failures
- 0 errors
- 3 skipped (PostgreSQL-specific baselines)

> Setup may differ on your local machine. The project depends on Python 3.11+ and uses SQLite by default. PostgreSQL is optional via `GRANTLAYER_DATABASE_URL`. Do not invent Docker or deployment instructions unless already verified in repository docs.

## 5. Minimal integration flow

An external integrator can run the following flow end-to-end using GrantLayer’s internal helpers or API equivalents:

1. **Create or represent a Grant Request** — capture the subject, role, action, resource, and reason.
2. **Approve it** — an authorized operator approves the request.
3. **Create a Grant** — approval atomically creates a signed Grant with `signature`, `payload_hash`, and `signing_key_id`.
4. **Create or represent a Grant Execution** — record the protected action attempt.
5. **Attach or persist evidence** — build an Evidence Bundle and archive it.
6. **Verify evidence** — recompute the bundle hash and compare it to the stored evidence hash.
7. **Check evidence completeness** — score presence, verification, and provenance coverage.
8. **Generate compliance gap report** — detect critical/high/medium/low gaps from the completeness report.
9. **Evaluate policy requirements** — run a machine-readable policy rule pack against subject evidence and upstream signals.
10. **Generate decision provenance** — combine all signals into a single decision record.
11. **Build auditor export** — produce an institutional auditor export with sections, blockers, and audit-readiness.
12. **Build compliance readiness summary** — compute overall readiness status and score across all dimensions.

## 6. Minimal illustrative JSON examples

> The shapes below are **minimal illustrative examples** intended to show the structure GrantLayer produces. Exact field contracts may vary; refer to the OpenAPI specification and production code for definitive schemas.

### Grant Request (illustrative)

```json
{
  "id": "req-001",
  "subjectId": "agent-a",
  "role": "analyst",
  "action": "report",
  "resource": "dataset-x",
  "validFrom": "2026-01-01T00:00:00Z",
  "validUntil": "2026-12-31T23:59:59Z",
  "requestedBy": "operator-1",
  "reason": "Quarterly analysis",
  "status": "requested"
}
```

### Approval result (illustrative)

```json
{
  "status": "approved",
  "approvedBy": "operator-2",
  "approvedAt": "2026-01-15T10:00:00Z",
  "grantId": "grant-001"
}
```

### Grant (illustrative)

```json
{
  "id": "grant-001",
  "subjectId": "agent-a",
  "role": "analyst",
  "action": "report",
  "resource": "dataset-x",
  "validFrom": "2026-01-01T00:00:00Z",
  "validUntil": "2026-12-31T23:59:59Z",
  "signature": "aabb...ccdd",
  "signingKeyId": "demo-ed25519-v1",
  "payloadHash": "1122...3344",
  "createdBy": "operator-2",
  "reason": "Approved from request req-001: Quarterly analysis"
}
```

### Grant Execution (illustrative)

```json
{
  "id": "exec-001",
  "grantId": "grant-001",
  "grantRequestId": "req-001",
  "operatorId": "operator-1",
  "action": "report",
  "resource": "dataset-x",
  "result": "succeeded",
  "executedAt": "2026-01-20T14:00:00Z",
  "metadataJson": "{\"workflowId\":\"wf-001\"}"
}
```

### Evidence Bundle (illustrative)

```json
{
  "evidenceId": "exec-001",
  "generatedAt": "2026-01-20T14:01:00Z",
  "executionId": "exec-001",
  "grantId": "grant-001",
  "grantRequestId": "req-001",
  "evidenceHash": "a1b2...c3d4",
  "canonicalVersion": "gl-evidence-v1",
  "hashAlgorithm": "sha256",
  "grant": {
    "id": "grant-001",
    "subjectId": "agent-a",
    "signingKeyId": "demo-ed25519-v1",
    "payloadHash": "1122...3344"
  },
  "execution": {
    "result": "succeeded",
    "executedAt": "2026-01-20T14:00:00Z"
  },
  "auditTrail": [
    {
      "timestamp": "2026-01-20T14:00:00Z",
      "action": "report",
      "approved": true
    }
  ]
}
```

### Evidence Completeness (illustrative)

```json
{
  "reportType": "evidence_completeness",
  "reportVersion": "gl-038-a1",
  "executionId": "exec-001",
  "grantId": "grant-001",
  "completenessScore": 100,
  "completenessStatus": "complete",
  "complianceGaps": [],
  "missingEvidence": [],
  "auditReadiness": "ready"
}
```

### Compliance Gap Report (illustrative)

```json
{
  "reportType": "compliance_gap_report",
  "reportVersion": "gl-compliance-gap-v1",
  "executionId": "exec-001",
  "overallStatus": "clear",
  "severity": "none",
  "complianceGaps": [],
  "blockingGaps": [],
  "recommendedActions": ["no_action_required"],
  "completeness": {
    "score": 100,
    "status": "complete"
  }
}
```

### Policy Requirement Evaluation (illustrative)

```json
{
  "recordType": "policy_requirement_evaluation",
  "recordVersion": "gl-policy-requirements-v1",
  "policyPackId": "pp-001",
  "policyPackVersion": "1.0.0",
  "subjectId": "agent-a",
  "evaluationStatus": "passed",
  "readiness": "ready",
  "requiredEvidence": ["execution_log"],
  "missingEvidence": [],
  "exclusionViolations": [],
  "deadlineStatus": "none",
  "amountStatus": "none",
  "blockers": [],
  "warnings": []
}
```

### Decision Provenance (illustrative)

```json
{
  "recordType": "decision_provenance",
  "recordVersion": "gl-decision-provenance-v2",
  "decisionId": "decision-exec-001",
  "subjectId": "agent-a",
  "actorId": "operator-1",
  "action": "report",
  "decision": "approved",
  "decisionStatus": "approved",
  "readiness": {
    "evidence": "ready",
    "compliance": "ready",
    "permission": "ready",
    "approval": "ready",
    "provenance": "ready",
    "policy": "ready"
  },
  "signals": {
    "evidence": "complete",
    "compliance": "complete",
    "permission": "allowed",
    "approval": "approved",
    "provenance": "present",
    "policy": "passed"
  },
  "blockers": [],
  "warnings": []
}
```

### Auditor Export (illustrative)

```json
{
  "recordType": "auditor_export",
  "recordVersion": "gl-auditor-export-v1",
  "exportId": "export-001",
  "exportType": "workflow",
  "subjectId": "agent-a",
  "decisionId": "decision-exec-001",
  "exportStatus": "ready",
  "auditReadiness": "audit_ready",
  "sections": [
    "decisionProvenance",
    "auditorReport",
    "evidence",
    "compliance",
    "permission",
    "approval",
    "policy"
  ],
  "blockers": [],
  "warnings": []
}
```

### Compliance Readiness Summary (illustrative)

```json
{
  "recordType": "compliance_readiness_summary",
  "recordVersion": "gl-compliance-readiness-v1",
  "subjectId": "agent-a",
  "workflowId": "wf-001",
  "readinessStatus": "ready",
  "readinessScore": 100,
  "evidenceStatus": "ready",
  "complianceStatus": "ready",
  "permissionStatus": "ready",
  "approvalStatus": "ready",
  "provenanceStatus": "ready",
  "auditorExportStatus": "ready",
  "policyStatus": "ready",
  "blockers": [],
  "warnings": [],
  "recommendedActions": []
}
```

## 7. Identifier strategy

An integrator should keep **stable identifiers** across the entire workflow chain. Recommended IDs:

| ID | Purpose |
|----|---------|
| `grantRequestId` | Tracks the original request through approval and linking. |
| `grantId` | Links the approved grant to executions and evidence. |
| `executionId` | Identifies a specific protected action attempt. |
| `evidenceId` | Usually the same as `executionId` for 1:1 evidence mapping. |
| `workflowId` | A higher-level identifier spanning multiple grants/executions. |
| `subjectId` | The actor or agent initiating the workflow. |

Keeping IDs stable ensures that Evidence Bundles, Compliance Gap Reports, Decision Provenance, and Auditor Exports all reference the same coherent chain of events.

## 8. Integration-readiness notes

- **Product Core is ready for integration exploration** — the API and internal builder functions produce structured, auditable records.
- **Production hardening is a separate concern** — the current operator model and auth layer are local demonstrators. See the non-goals list below.
- **Blockchain is not required** — all integrity checks run on standard SHA-256 hashes and Ed25519 signatures. If blockchain anchoring is added later, sensitive evidence should remain off-chain.
- **Auditor exports and compliance readiness are structured records, not legal advice** — they are intended to support institutional audit workflows, not replace legal or regulatory review.
- **SQLite is the default** — PostgreSQL is supported but not required for integration exploration.

## 9. Current non-goals / future production hardening

The following are **explicitly out of scope** for the current Product Core MVP and will only be added if explicitly scoped later:

- OAuth / JWT / SSO production authentication
- Production secret management (HSM, HashiCorp Vault, AWS KMS)
- Deployment hardening (containers, load balancing, TLS termination)
- Observability (metrics, traces, structured logging)
- Backup / restore / disaster recovery procedures
- PostgreSQL continuous integration and performance tuning
- HSM-backed signing key management
- Client SDKs (Python, JavaScript, Go)
- Blockchain / wallet / payment layer integrations
- Dashboard / UI product
- Multi-tenant SaaS architecture

## 10. Verification reference

A deterministic backend end-to-end test exists that proves this entire flow:

- File: `backend/tests/test_gl052_product_core_e2e_flow.py`
- Covers: Grant Request, Approval, Grant creation, Grant Execution, Evidence Bundle, Evidence Persistence, Evidence Verification, Evidence Completeness, Compliance Gap Report, Policy Requirements, Decision Provenance, Auditor Export, and Compliance Readiness.
- Verifies: GL-050 signature fields are present, GL-051 transactional consistency is preserved, all outputs belong to the same coherent workflow/subject identifiers.

A deterministic demo scenario and fixture are also available for integrators who want a concrete, readable example before running code:

- Document: `docs/demo_scenario.md`
- Fixture: `backend/tests/fixtures/gl054_demo_scenario.json`
- Test: `backend/tests/test_gl054_demo_scenario_fixture.py`

The full backend suite is expected to pass with 0 failures and 0 errors.

See also: [`docs/integration_ready_checklist.md`](integration_ready_checklist.md) — the minimum artifact and verification gate for Integration-Ready v0.

- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — step-by-step API-first walkthrough with stable identifiers and verified OpenAPI paths
