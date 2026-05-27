# GL-145 Developer Adoption Strategy Intake

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Status

This document is the **GL-145 Developer Adoption Strategy Intake**. It defines the
strategy, target audiences, value proposition, adoption track, artifact map,
messaging rules, risk register, validation gates, non-goals, proposed follow-up
issues, and go/no-go criteria for the Developer Adoption track.

| Field | Value |
|-------|-------|
| Issue | GL-145 |
| Status | strategy/intake only |
| Production code changed | **No** |
| SDK implemented | **No** |
| Quickstart implemented | **No** |
| LangGraph/LangChain example implemented | **No** |
| Public GitHub readiness claimed | **No** |
| Production SaaS readiness claimed | **No** |
| Tenant isolation claimed/implemented | **No** |

This is **NOT SDK implementation.**
This is **NOT quickstart implementation.**
This is **NOT LangGraph/LangChain integration implementation.**
This is **NOT public GitHub release.**
This is **NOT API work.**
This is **NOT auth redesign.**
This is **NOT tenant/workspace implementation.**
This is **NOT production SaaS enablement.**

---

## 2. Current Posture

GrantLayer is suitable for **controlled pilot/developer-preview exploration with
caveats**. The following posture statements apply:

- **Production SaaS readiness is not claimed** — the backend has not completed
  all production-hardening gates required for a shared multi-tenant SaaS.
- **Tenant isolation is not implemented** — the backend does not enforce
  tenant/workspace boundaries at the data, authorization, or audit layers.
- **GL-144 tenant/workspace design exists but implementation is future work** —
  the data model design is accepted, but no schema changes, migrations, or
  production code changes have been made.
- **GL-136 through GL-144 gates improve readiness but do not equal public SaaS
  readiness** — key hygiene, dependency manifest, server route decomposition,
  and tenant/workspace design are planning/design milestones, not implementation
  completions that authorize public SaaS claims.
- **Controlled pilot with accepted caveats remains the appropriate framing** —
  local evaluators, integrators, and pilot partners should understand the
  current boundaries before building on GrantLayer.

---

## 3. Target Developer Audiences

1. **Local evaluator** — a developer who clones the repo, runs the backend
   locally, and evaluates the Product Core flow using the demo script and
   quickstart examples.
2. **AI-agent/LangGraph developer** — a developer building agentic workflows
   who wants to integrate GrantLayer as a policy-bound grant/evidence layer
   within a LangGraph or LangChain orchestration.
3. **Grant/compliance workflow integrator** — a developer integrating
   GrantLayer into an existing grant management, compliance, or audit workflow
   who needs API examples, data shape documentation, and deterministic
   identifier tracing.
4. **Pilot partner technical reviewer** — a technical stakeholder from a pilot
   partner organization who reviews the codebase, tests, and documentation to
   assess integration feasibility and security posture.
5. **Security-conscious contributor** — a developer or security reviewer who
   audits the codebase for secrets, auth boundaries, audit integrity, and
   tamper-evidence guarantees before recommending adoption.

---

## 4. Developer Value Proposition

- **Policy-bound grant/evidence workflow experiments** — developers can explore
  a fail-closed policy engine, approval workflows, and evidence bundles without
  building these primitives from scratch.
- **Auditable execution/evidence flow** — every grant request, approval,
  execution, and evidence item produces a traceable record with SHA-256 integrity
  hashes and optional Ed25519 signatures.
- **Security-conscious local baseline** — the codebase includes explicit
  security boundaries, secret-handling policies, and regression tests that
  demonstrate a security-aware foundation.
- **Integration-oriented API examples** — OpenAPI contract, static JSON
  examples, and E2E tests provide concrete integration targets for client
  development.

---

## 5. Adoption Track

The Developer Adoption track consists of the following issues:

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-146 | 10-Minute Quickstart | A runnable, copy-paste quickstart that gets a developer from clone to first API call in 10 minutes. |
| GL-147 | Minimal Python SDK | A minimal Python client/SDK that wraps the OpenAPI contract with typed requests and responses. |
| GL-148 | LangGraph/LangChain Integration Example | A concrete example showing how GrantLayer grant requests, evidence bundles, and policy checks fit into a LangGraph node graph. |
| GL-149 | Public GitHub Readiness Pack | A checklist and set of artifacts (README, CONTRIBUTING, issue templates, CI badges) that prepare the repo for public visibility. |
| GL-150 | First Developer Feedback Log | A structured log or template for capturing the first real (or explicitly simulated) developer feedback on the quickstart, SDK, and integration example. |

---

## 6. Artifact Map

Each adoption issue produces the following artifacts:

| Issue | Artifact | Location (proposed) |
|-------|----------|---------------------|
| GL-146 | Quickstart guide | `docs/gl146_10_minute_quickstart.md` |
| GL-146 | Quickstart validation test | `backend/tests/test_gl146_10_minute_quickstart.py` |
| GL-147 | Minimal Python SDK | `sdk/python/grantlayer/` (or similar, TBD in GL-147) |
| GL-147 | SDK usage examples | `docs/examples/gl147/` |
| GL-148 | LangGraph/LangChain integration example | `docs/examples/gl148/` |
| GL-148 | Integration validation test | `backend/tests/test_gl148_langgraph_integration.py` |
| GL-149 | Public readiness checklist | `docs/gl149_public_github_readiness_pack.md` |
| GL-149 | Readiness JSON artifact | `docs/examples/gl149/public_github_readiness_pack.json` |
| GL-150 | Feedback log template | `docs/gl150_first_developer_feedback_log.md` |
| GL-150 | Feedback JSON artifact | `docs/examples/gl150/first_developer_feedback_log.json` |

---

## 7. Messaging Rules

All developer-facing messaging must follow these rules:

1. **Avoid production SaaS claims** — never describe GrantLayer as
   "production-ready SaaS," "enterprise-ready," or "multi-tenant SaaS."
2. **Avoid tenant isolation claims** — clearly state that tenant/workspace
   isolation is designed but not implemented.
3. **Describe pilot/developer-preview status accurately** — use phrases like
   "controlled pilot with accepted caveats," "developer preview," or
   "local evaluation only."
4. **Document security caveats clearly** — list demo keys, missing TLS,
   missing OAuth/JWT, and single-namespace data model as known limitations.
5. **Do not expose secrets** — no tokens, keys, passwords, or internal
   endpoints may appear in public docs, examples, or tests.

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Overclaiming readiness | High | Messaging rules (Section 7) and explicit non-goal statements in every adoption issue. |
| Stale examples | Medium | Validation gates require examples to be tested; quickstart must be copy-paste runnable. |
| API drift | Medium | Validation gates require no OpenAPI drift unless explicitly planned; SDK must track OpenAPI. |
| Hidden local assumptions | Medium | Quickstart must work on a clean clone with no hidden config; document all env vars. |
| Auth confusion | Medium | Clearly distinguish demo-mode from product-mode; never present demo-mode as secure. |
| Secrets in public docs | High | Automated scan for PEM markers, tokens, and passwords in all docs and examples. |
| Dependency/setup friction | Medium | Minimal Python SDK must use only stdlib + `cryptography` (same as backend); document install steps. |
| Examples that are not reproducible | High | Every example must have a corresponding validation test that runs in CI. |

---

## 9. Validation Gates for GL-146 through GL-150

Before any adoption issue is accepted, the following gates must pass:

1. **Docs are copy-paste runnable where applicable** — the quickstart must work
   when followed verbatim on a clean clone.
2. **Examples tested** — every JSON example and code snippet must have a
   corresponding automated test.
3. **JSON examples valid** — all JSON artifacts must pass `python3 -m json.tool`
   validation.
4. **No secrets** — no PEM private keys, tokens, or passwords in any doc,
   example, or test.
5. **No OpenAPI drift unless explicitly planned** — the SDK and integration
   examples must match the current `docs/openapi.yaml` contract.
6. **Full backend suite on main before push** — `python3 -m unittest discover
   backend.tests` must pass with 0 failures and 0 errors before any adoption
   branch is merged.

---

## 10. Non-Goals

The following are explicitly out of scope for GL-145 and the Developer Adoption
track intake:

- **No SDK implementation in GL-145** — SDK work is scoped to GL-147.
- **No quickstart implementation in GL-145** — quickstart work is scoped to
  GL-146.
- **No LangGraph/LangChain implementation in GL-145** — integration example
  work is scoped to GL-148.
- **No public GitHub release in GL-145** — public readiness work is scoped to
  GL-149.
- **No API change** — the adoption track must work with the existing OpenAPI
  contract; any API change requires a separate issue.
- **No auth redesign** — the adoption track uses existing auth boundaries;
  auth redesign is a separate workstream.
- **No tenant/workspace implementation** — tenant/workspace implementation is
  a separate workstream that depends on GL-144 design acceptance and follow-up
  implementation issues.
- **No production SaaS claim** — no adoption issue may claim or imply
  production SaaS readiness.

---

## 11. Proposed Issue Definitions

### GL-146 10-Minute Quickstart

- Produce a runnable quickstart guide that gets a developer from `git clone` to
  a successful API call in 10 minutes.
- Include copy-paste cURL or Python examples for the core flow.
- Include a validation test that asserts the quickstart steps are documented
  and the examples are syntactically valid.
- Explicitly state local-only scope and security caveats.

### GL-147 Minimal Python SDK

- Produce a minimal Python client library that wraps the GrantLayer OpenAPI
  contract.
- Use only stdlib + `cryptography` (same dependency footprint as backend).
- Include typed request/response models for core endpoints.
- Include usage examples and a validation test.
- Do not claim production readiness; document local-evaluation scope.

### GL-148 LangGraph/LangChain Integration Example

- Produce a concrete example showing GrantLayer nodes in a LangGraph graph.
- Demonstrate grant request, approval check, execution, and evidence capture
  as graph nodes.
- Include a validation test that asserts the example files exist and are
  syntactically valid.
- Do not require LangGraph/LangChain as a production dependency of the backend.

### GL-149 Public GitHub Readiness Pack

- Produce a checklist and set of artifacts that prepare the repo for public
  GitHub visibility.
- Include CONTRIBUTING.md, issue templates, PR template, and CI badge updates.
- Include a validation test that asserts required files exist and contain
  appropriate non-claims.
- Do not claim public release is complete until all checklist items pass.

### GL-150 First Developer Feedback Log

- Produce a structured feedback log template for capturing developer feedback.
- Include fields for environment, steps taken, blockers, suggestions, and
  disposition.
- Include a validation test that asserts the template exists and is valid.
- Feedback may be real or explicitly simulated; simulated feedback must be
  labeled as such.

---

## 12. Go/No-Go Criteria

### GO — Proceed to GL-146

- GL-145 strategy intake is accepted.
- All required sections are present in this document.
- JSON artifact passes validation.
- Scope guard confirms no production code changes.
- Messaging rules are understood and agreed by the team.

### NO-GO — Do not proceed

- Any production SaaS readiness claim appears in the strategy or proposed
  issues.
- Any tenant isolation claim appears in the strategy or proposed issues.
- Any scope creep into SDK, quickstart, or integration implementation is
  detected.
- Any secret is found in docs, examples, or tests.

### Additional constraints

- **Do not publish publicly until GL-149 passes** — the repo must not be made
  publicly visible until the Public GitHub Readiness Pack is complete and
  validated.
- **Do not claim developer adoption until GL-150 captures real or explicitly
  simulated feedback** — developer adoption metrics or claims require evidence
  from the feedback log.

---

## 13. Next Issue

**GL-146 10-Minute Quickstart**

After the developer adoption strategy intake is accepted, the next issue is
GL-146, which implements the first runnable developer onboarding artifact.

---

> GL-145 documents the **developer adoption strategy intake** for the
> GrantLayer Developer Adoption track. It does **not** implement any SDK,
> quickstart, integration example, public GitHub release, API change, auth
> redesign, tenant/workspace implementation, or production SaaS claim. It
> explicitly preserves all existing gates (GL-136 through GL-144) and mandates
> that no public release or developer adoption claim is made until GL-146
> through GL-150 are completed and validated.
