# GrantLayer Tenant / Workspace Boundary Decision

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Scope

This document is the **GL-132 Tenant / Workspace Boundary Decision**. It defines the
review, artifact, and test-only contract for deciding how tenant and workspace
boundaries are handled before any pilot proceeds. It is an architecture decision
gate, not an implementation.

**This is a review-only artifact.** No production code, API behavior, schema,
migration, or OpenAPI changes are made in GL-132.

**This is NOT tenant implementation.**
**This is NOT workspace implementation.**
**This is NOT auth implementation.**
**This is NOT DB migration work.**
**This is NOT production code.**
**This is NOT frontend/onboarding/billing work.**
**This is NOT website/marketing/design work.**

## 2. Baseline Status

| Field | Value |
|-------|-------|
| backend is pilot-ready with caveats | **Yes** |
| GL-132 is an architecture decision gate | **Yes** |
| no tenant/workspace implementation is added | **Yes** |
| production multi-tenancy is not implemented | **Yes** |
| production SaaS/commercial SaaS is not complete | **Yes** |

The backend is pilot-ready with caveats, not production SaaS complete.
No tenant/workspace implementation is added in GL-132.
No production multi-tenancy is implemented in GL-132.
No commercial SaaS is complete in GL-132.

## 3. Terms

The following terms are used consistently in this decision:

1. **Tenant** — a logical boundary that isolates one customer's data, grants,
   evidence, audit records, and operator identities from another customer's.
2. **Workspace** — a scoped operating context within a tenant, typically mapping
   to a team, department, or organizational unit that shares grants and evidence
   but remains isolated from other workspaces.
3. **Operator** — an authenticated individual or service identity that performs
   actions within a tenant/workspace boundary.
4. **Pilot environment** — a single, controlled deployment of GrantLayer used
   for evaluation, demonstration, or early partner validation.
5. **Grant boundary** — the scope within which a grant record, its rules, and
   its execution history are visible and manageable.
6. **Evidence boundary** — the scope within which evidence files, verification
   records, and attestations are visible and manageable.
7. **Audit boundary** — the scope within which audit events, immutability chains,
   and tamper-evident records are visible and manageable.

## 4. Current Posture

The current GrantLayer backend operates without explicit tenant or workspace
isolation. The following posture statements apply:

- A **controlled pilot** can run as a **single pilot environment** or under an
  **operator-bounded workspace assumption**.
- **Unrelated customer data must not be mixed** in one shared environment.
- **Multi-tenant isolation must not be assumed** — the backend does not enforce
  tenant boundaries at the data, authorization, or audit layers.
- All grants, evidence, audit events, and operator actions in a given deployment
  share the same namespace unless externally bounded by deployment isolation
  (separate databases, separate instances, or separate infrastructure).

## 5. Options Considered

### Option A: Single-tenant pilot only

- Run each pilot on a fully isolated deployment (separate database, separate
  instance, separate infrastructure).
- No tenant/workspace concepts needed inside the application.
- Simplest to implement and operate; highest isolation guarantee.
- Does not scale to a shared SaaS model.

### Option B: Operator-bounded workspace model

- Run a single deployment where all data is implicitly bounded by the operator
  owner and their scope of control.
- Operator roles and named ownership act as a lightweight boundary.
- Acceptable only when all data belongs to a single organization or clearly
  bounded partner scope.
- Not true tenant isolation; risk of accidental cross-boundary exposure.

### Option C: Full multi-tenant SaaS model

- Implement explicit tenant/workspace identity, tenant-aware authorization,
  tenant-scoped data models, and cross-tenant access prevention.
- Required for production SaaS with unrelated customers on shared infrastructure.
- Not implemented in GL-132; significant design and implementation work required.

### Option D: Defer tenant implementation but explicitly forbid multi-tenant claims

- Document that tenant/workspace isolation is not implemented.
- Explicitly forbid any claim that the backend is multi-tenant ready.
- Proceed with pilot under single-environment or operator-bounded assumptions.
- Plan follow-up issues for tenant/workspace design and implementation.

## 6. Decision

**Recommended near-term:** A controlled pilot may proceed under
**single-environment/operator-bounded assumptions**.

**Required before production SaaS:** An **explicit tenant/workspace data and
authorization boundary** must be designed, implemented, and verified.

The decision is:

- **GO** for controlled pilot under Option A or Option B assumptions.
- **NO-GO** for shared multi-tenant SaaS under Option C until follow-up
  implementation issues are completed.
- **Documented** under Option D — no multi-tenant claims are permitted.

## 7. Production SaaS Tenant / Workspace Requirements

Before GrantLayer can claim production SaaS readiness with tenant/workspace
boundaries, the following must be implemented and verified:

1. **Tenant/workspace identity** — a stable identity model for tenants and
   workspaces that can be assigned to all data and operations.
2. **Tenant-aware authorization** — authentication and authorization layers must
   enforce tenant/workspace scope on every protected action.
3. **Tenant-aware operator/admin permissions** — operator roles and permissions
   must be scoped to a tenant/workspace; cross-tenant operator access must be
   prevented by design.
4. **Tenant-aware grants/executions/evidence/audit records** — all core data
   models must include tenant/workspace identifiers and enforce scope at the
   database and API layers.
5. **Tenant-aware export/report boundaries** — exports, reports, and evidence
   bundles must be scoped to the requesting tenant/workspace.
6. **Tenant-aware backup/restore boundaries** — backup and restore operations
   must preserve tenant/workspace isolation; cross-tenant restore must be
   impossible.
7. **Tenant-aware log/monitoring redaction rules** — logs and monitoring data
   must include tenant/workspace identifiers where appropriate and must not leak
   cross-tenant data.
8. **Cross-tenant access prevention tests** — automated tests must verify that
   no endpoint, query, or background job can access data belonging to another
   tenant/workspace.

## 8. Explicit Non-Claims

The following capabilities are **not** claimed or implemented in GL-132:

- **No multi-tenant isolation implemented** — the backend does not enforce
  tenant boundaries.
- **No tenant model implemented** — there is no tenant entity, table, or
  identifier in the data model.
- **No workspace model implemented** — there is no workspace entity, table, or
  identifier in the data model.
- **No customer account model implemented** — there is no customer account,
  subscription, or billing entity.
- **No billing model implemented** — no subscription, usage metering, or
  invoicing logic exists.
- **No frontend onboarding implemented** — no tenant signup, workspace creation,
  or self-service onboarding UI exists.
- **No shared SaaS environment approved for unrelated customers** — a single
  deployment must not be used for unrelated customers without explicit
  tenant/workspace isolation.

## 9. Pilot Go/No-Go

### GO — Pilot may proceed

GO is only permitted when **ALL** of the following are true:

- **Single pilot environment or clearly bounded operator/workspace scope** — the
  deployment serves one organization or a clearly bounded partner scope.
- **Named operator owner** — a single named person owns operator tokens, role
  assignments, and environment access.
- **No unrelated customer data mixed** — the environment does not contain data
  belonging to unrelated customers or organizations.
- **Pilot data boundary documented** — the operator understands and documents
  what data belongs in the pilot and what does not.
- **Backup/restore boundary documented** — the operator understands that backups
  contain all data in the deployment and that restore operations must respect
  the same boundary.
- **Monitoring/incident owners assigned** — named owners exist for monitoring
  review and incident response.

### NO-GO — Pilot must not proceed

NO-GO if **ANY** of the following are true:

- **Unrelated customers share an environment** — data from multiple unrelated
  customers or organizations is stored in the same deployment.
- **Unclear data ownership** — it is not clear who owns the data in the
  deployment or what organizational boundary it belongs to.
- **Unclear operator permission boundaries** — operator roles and permissions
  are not documented or understood.
- **Cross-customer data mixing risk** — there is a risk that data from one
  customer could be exposed to another.
- **Tenant isolation is assumed but not implemented** — stakeholders believe the
  backend is multi-tenant when it is not.

## 10. Follow-Up Implementation Issues

The following issues must be completed before production SaaS tenant/workspace
boundaries are claimed:

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-133 | External Security Review Preparation | Prepare for independent security review of tenant/workspace boundaries. |
| GL-134 | Pilot Partner Dry Run | Validate pilot assumptions with a real partner under documented boundaries. |
| GL-135 | Tenant / Workspace Data Model Design | Design tenant and workspace entities, identifiers, and database schema. |
| GL-136 | Tenant-Aware Authorization Design | Design tenant-scoped authentication and authorization architecture. |
| GL-137 | Cross-Tenant Isolation Test Plan | Define automated tests that verify cross-tenant access is prevented. |
| GL-138 | Tenant-Aware Audit/Evidence Boundary Plan | Design tenant-scoped audit and evidence boundaries. |

## 11. Relationship to Existing Gates

GL-132 builds on and references the following completed gates:

| Issue | Title | Relevance to Tenant / Workspace Boundary Decision |
|-------|-------|---------------------------------------------------|
| GL-128 | Pilot Readiness Release Cut | Defines the pilot-ready baseline under which GL-132 evaluates tenant/workspace posture. |
| GL-129 | Monitoring / Alerting Baseline | Defines monitoring ownership; tenant-aware monitoring redaction is future work. |
| GL-130 | Incident Response / Operational Runbook Execution Gate | Defines incident ownership; tenant-aware incident scope is future work. |
| GL-131 | Pilot Environment Setup Checklist | Defines environment identity and operator ownership; GL-132 adds tenant/workspace boundary constraints. |

## 12. Explicit Non-Goals

The following changes are explicitly out of scope for GL-132:

- **No tenant implementation** — no tenant entity, model, or identifier is added.
- **No workspace implementation** — no workspace entity, model, or identifier is added.
- **No DB migration** — no database migration or schema change is implemented.
- **No auth change** — no authentication or authorization semantics are modified.
- **No API/OpenAPI change** — no endpoint behavior or OpenAPI specification is changed.
- **No frontend/onboarding/billing** — no UI, signup flow, or billing logic is implemented.
- **No deployment/infrastructure change** — no CI/CD, container, or infrastructure change is implemented.
- **No production code changes** (`backend/src/`).
- **No dependency additions or version changes**.
- **No website, landing page, design, brand, or marketing file changes**.
- **No production SaaS complete claim** — this decision does not make the backend
  production SaaS complete by itself.

## 13. Final Statement

> GL-132 approves **controlled pilot boundaries only**. It documents the current
> tenant/workspace posture, defines the decision options, records the recommended
> near-term path, and lists the production SaaS requirements that must be met
> before tenant/workspace isolation can be claimed. It explicitly forbids
> multi-tenant claims and shared SaaS use for unrelated customers. It does **not**
> approve a shared multi-tenant SaaS environment.

(End of file)
