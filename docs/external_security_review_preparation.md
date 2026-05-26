# GrantLayer External Security Review Preparation

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Scope

This document is the **GL-133 External Security Review Preparation**. It creates a
review, artifact, and test-only package that prepares GrantLayer for an independent
external security review. It does not perform or complete one.

**This is NOT a completed external security review.**
**This is NOT a penetration test.**
**This is NOT security implementation work.**
**This is NOT production code.**
**This is NOT tenant/workspace implementation.**
**This is NOT frontend/onboarding/billing work.**
**This is NOT website/marketing/design work.**

## 2. Review Posture

| Field | Value |
|-------|-------|
| backend is pilot-ready with caveats | **Yes** |
| production SaaS is complete | **No** |
| commercial SaaS is complete | **No** |
| multi-tenant isolation is implemented | **No** |
| GL-133 prepares external review | **Yes** |
| GL-133 completes external review | **No** |

The backend is pilot-ready with caveats (as of GL-128), not production SaaS complete.
Production SaaS and commercial SaaS remain future work.
Multi-tenant isolation is not implemented; the pilot boundary is single-environment or
operator-bounded (as defined in GL-132).

## 3. Review Scope

The following areas are in scope for an external reviewer to inspect and evaluate:

1. **Backend API security** — endpoints, error contracts, secret-safety of responses.
2. **Operator authentication and authorization** — token handling, role enforcement,
   fail-closed behavior, RBAC boundaries.
3. **Operator token expiry and rotation** — expiry semantics, rotation flow, raw-token
   non-exposure, fail-closed on expired tokens.
4. **Startup fail-closed configuration** — unsafe defaults are detected and blocked at
   startup; unsafe modes are not silently permitted.
5. **Request body / payload validation** — JSON parsing limits, oversized payload
   rejection, shape validation, and safe error responses that do not echo raw input.
6. **Rate limiting baseline** — rate limits are enforced, do not mutate state when
   rejecting requests, and return safe, non-leaking error responses.
7. **Structured logging / correlation IDs / secret safety** — all security-relevant
   events emit structured logs; `correlation_id` propagates; secrets are never logged,
   including tokens, headers, passwords, private keys, or backup credentials.
8. **Audit persistence / hash-chain / PostgreSQL immutability** — audit records are
   append-only; row-level hash chain (`row_hash`, `prev_hash`) is computed; PostgreSQL
   triggers block UPDATE/DELETE on audit tables; tamper-evident verification is CI-gated.
9. **PostgreSQL connection pooling** — pool configuration, credential isolation,
   connection lifecycle management, and error handling that does not expose credentials.
10. **Backup / restore drill** — critical data categories, restore acceptance criteria,
    non-destructive restore guidance, and go/no-go gates.
11. **Runtime gate / smoke tests** — automated config validation before deployment and
    a fast post-deployment validation bundle covering health, auth, payload, correlation,
    and logging safety.
12. **Monitoring / alerting baseline** — documented ownership, review cadence, and
    operational expectations for monitoring and alerting.
13. **Incident response runbook** — escalation paths, ownership, and execution gates for
    incident response.
14. **Tenant/workspace boundary decision** — documented boundary posture, explicit
    non-claims, pilot go/no-go criteria, and follow-up issues for multi-tenant readiness.

## 4. Out of Scope / Non-Claims

The following are **not** claimed or implemented in GL-133:

- **No external security review completed by GL-133** — GL-133 prepares the package
  only; it does not perform, commission, or complete an independent review.
- **No penetration test completed by GL-133** — no penetration testing is executed
  or claimed as complete.
- **No multi-tenant isolation implemented** — the backend does not enforce tenant
  or workspace boundaries at the data, authorization, or audit layers.
- **No shared SaaS environment approved for unrelated customers** — a single shared
  deployment must not host unrelated customers until explicit tenant/workspace isolation
  is designed, implemented, and verified.
- **No customer account / billing / onboarding model implemented** — there is no
  customer account entity, subscription logic, usage metering, or self-service onboarding UI.
- **No frontend / website security review completed** — the security review preparation
  package covers the backend only; any frontend or website security review is separate work.

## 5. Security-Sensitive Components

Reviewers should pay particular attention to the following components:

1. **Auth / operator token handling** — token creation, hashing (PBKDF2-HMAC-SHA256),
   storage, comparison (`hmac.compare_digest`), and transmission boundaries.
2. **Permission checks** — role-based access control (`owner`, `grant_admin`, `auditor`,
   `demo_operator`), endpoint-level enforcement, and fail-closed behavior when the
   operator model is disabled or the token is missing/invalid.
3. **Request parsing and validation** — JSON parsing limits, max payload size, shape
   validation, string length checks, and safe error responses.
4. **Rate limiting** — enforcement logic, state-isolation on rejection, and safe
   responses that do not expose internal counters or window details.
5. **Audit / event persistence** — append-only audit table design, hash-chain integrity,
   PostgreSQL trigger-based immutability, and tamper-evident verification.
6. **Cryptographic signing / signature verification** — Ed25519 grant signing, hash
   computation, signature lifecycle, and fail-closed behavior for missing or invalid
   signatures.
7. **Secret source boundary** — environment variable loading, startup validation,
   non-exposure in logs/responses/errors, and file permission checks for private key files.
8. **Database configuration / migrations / PostgreSQL mode** — connection pooling,
   audit immutability triggers, SQLite vs PostgreSQL behavior, and migration runner
   safety (atomicity, dict row access).
9. **Backup / restore procedure** — critical data categories, restore acceptance
   criteria, non-destructive restore guidance, and go/no-go gates.
10. **Logs / structured events / correlation ID** — `correlation_id` propagation,
    structured event shape, safe field redaction, and absence of raw secrets in log output.

## 6. Threat-Model Review Areas

Reviewers should evaluate the following threat areas against the current implementation:

1. **Unauthenticated access** — any endpoint that should require authentication but
   permits unauthenticated access.
2. **Unauthorized operator access** — an operator with a lower-privilege role accessing
   endpoints or data that require a higher-privilege role.
3. **Token expiry / rotation failures** — tokens that do not expire when configured,
   rotation that leaks raw token material, or fail-open behavior on expired tokens.
4. **Malformed request bodies and oversized payloads** — parsers that crash, leak memory,
   or echo raw input in error responses when given malformed JSON or oversized payloads.
5. **State mutation after rejection / rate-limit** — endpoints that mutate database state
   or side effects before or after rejecting a request due to auth failure, rate limit,
   or validation failure.
6. **Audit tampering** — any path that permits UPDATE or DELETE on audit records, or
   that bypasses the hash-chain integrity check.
7. **Hash-chain / immutability gaps** — missing or weak hash computation, reproducible
   hash without a secret, or gaps in the chain that allow undetected deletion.
8. **Secret leakage through logs / errors / docs** — any log line, error response,
   API payload, or documentation file that contains raw tokens, private keys, passwords,
   or backup credentials.
9. **DB connectivity / config failures** — connection pool exhaustion, credential exposure
   in error messages, or silent fallback to unsafe SQLite behavior in production-like mode.
10. **Backup / restore misuse** — destructive restore operations that overwrite unrelated
    data, missing backup coverage for audit or evidence tables, or unclear restore
    ownership boundaries.
11. **Tenant / workspace boundary ambiguity** — any claim that the backend is multi-tenant
    when it is not, or any deployment that mixes unrelated customer data without explicit
    tenant isolation.

## 7. Reviewer Checklist

The external reviewer should verify the following items at a minimum:

- [ ] **Auth fail-closed behavior** — unauthenticated or invalid-token requests are
  rejected with `401`/`403` and no state mutation occurs.
- [ ] **Role / permission boundaries** — each endpoint enforces the correct minimum role;
  disabled operators or missing roles result in denial.
- [ ] **Token expiry / rotation semantics** — tokens expire at the configured time,
  rotation does not leak raw material, and expired tokens are rejected.
- [ ] **Unsafe startup is blocked** — `scripts/run-full-backend-suite.sh` and the
  production runtime gate catch unsafe configuration before deployment.
- [ ] **Request body limits and malformed JSON rejection** — oversized payloads and
  malformed JSON are rejected with safe, non-leaking error responses.
- [ ] **Rate limiting does not mutate state when rejected** — a rate-limited request
  returns a safe error without modifying database state or side effects.
- [ ] **Logs do not expose secrets** — structured logs, error responses, and evidence
  bundles contain no raw tokens, private keys, passwords, or backup credentials.
- [ ] **Audit immutability assumptions and CI gate** — PostgreSQL audit immutability
  triggers block UPDATE/DELETE; the hash-chain is reproducible and CI-gated in
  `test_gl108_postgres_audit_immutability`.
- [ ] **Backup / restore expectations and non-destructive restore guidance** — the
  GL-127 drill documents critical data categories, acceptance criteria, and warns
  against destructive restore.
- [ ] **Tenant / workspace non-claims and pilot boundary** — the GL-132 decision
  explicitly forbids multi-tenant claims and shared SaaS for unrelated customers.

## 8. Evidence Artifacts

The external reviewer should have access to the following evidence artifacts:

| Artifact | Location | Purpose |
|----------|----------|---------|
| GL-128 Pilot Readiness Release Cut | `docs/pilot_readiness_release_cut.md` | Baseline pilot-ready disposition and accepted caveats |
| GL-129 Monitoring / Alerting Baseline | `docs/monitoring_alerting_baseline.md` | Monitoring ownership and operational expectations |
| GL-130 Incident Response Runbook Execution Gate | `docs/incident_response_runbook_execution_gate.md` | Escalation paths and incident ownership |
| GL-131 Pilot Environment Setup Checklist | `docs/pilot_environment_setup_checklist.md` | Environment identity, operator ownership, and deployment checklist |
| GL-132 Tenant / Workspace Boundary Decision | `docs/tenant_workspace_boundary_decision.md` | Boundary posture, non-claims, pilot go/no-go, and follow-up issues |
| Security Boundary Regression Tests | `backend/tests/test_security_boundary_regression.py` | Automated CI-gated tests for auth fail-closed, secret safety, and tamper detection |
| Full Backend Suite Runner | `scripts/run-full-backend-suite.sh` | Automated runner that executes the full backend test suite (3632+ tests) |

## 9. Required Validation Commands

Before conducting a review, the reviewer or CI system should execute:

```bash
# Full backend suite (recommended; timeout configurable, default 900 s)
scripts/run-full-backend-suite.sh

# Targeted security and gate validation
python3 -m unittest backend.tests.test_security_boundary_regression -v
python3 -m unittest backend.tests.test_gl128_pilot_readiness_release_cut -v
python3 -m unittest backend.tests.test_gl129_monitoring_alerting_baseline -v
python3 -m unittest backend.tests.test_gl130_incident_response_runbook_execution_gate -v
python3 -m unittest backend.tests.test_gl131_pilot_environment_setup_checklist -v
python3 -m unittest backend.tests.test_gl132_tenant_workspace_boundary_decision -v
```

## 10. Expected Reviewer Outputs

After completing the review, the reviewer should produce:

1. **Reviewed scope** — a statement confirming which areas were inspected and on what
   commit / branch / artifact version.
2. **Findings by severity** — a list of findings classified as `critical`, `high`,
   `medium`, or `low`.
3. **Must-fix-before-pilot findings** — any finding that blocks a controlled pilot.
4. **Must-fix-before-production-SaaS findings** — any finding that blocks production
   SaaS readiness but does not necessarily block pilot.
5. **Acceptable pilot caveats** — risks or limitations that are documented, understood,
   and accepted for the controlled pilot phase.
6. **Recommended follow-up issues** — specific, actionable issues for the development
   team to address post-review (e.g., `GL-134 Pilot Partner Dry Run`).

## 11. Go/No-Go for Review Usage

### GO — Review package is ready for use

GO is only permitted when **ALL** of the following are true:

- **Scope is defined** — Section 3 (Review Scope) and Section 4 (Out of Scope / Non-Claims)
  are agreed upon by the reviewer and GrantLayer team.
- **Evidence artifacts are accessible** — the reviewer can access all artifacts listed
  in Section 8, including source code, documentation, and CI test results.
- **Security boundaries are clear** — the reviewer understands the current auth, audit,
  and isolation boundaries and their limitations.
- **No multi-tenant claims are made** — all stakeholders agree that the backend is not
  multi-tenant and that shared SaaS for unrelated customers is not approved.
- **No secrets are exposed** — documentation, logs, error responses, and JSON artifacts
  contain no raw tokens, private keys, passwords, or backup credentials.
- **Must-fix findings are resolved** — any critical or high-severity findings from a
  prior review are tracked, assigned, and resolved before the next review cycle.

### NO-GO — Review package must not be used

NO-GO if **ANY** of the following are true:

- **Reviewer cannot access evidence** — source code, documentation, or CI results are
  unavailable or incomplete.
- **Security boundaries are unclear** — it is not clear what auth, audit, or isolation
  guarantees are in scope.
- **Multi-tenant claims are made** — any stakeholder claims the backend is multi-tenant
  or approves shared SaaS for unrelated customers.
- **Secrets are exposed** — raw tokens, private keys, passwords, or backup credentials
  appear in logs, responses, or documentation.
- **Must-fix findings are unresolved** — critical or high-severity findings from a prior
  review remain open and unassigned.

## 12. Relationship to Existing Gates

GL-133 prepares an external review of the security posture established by the following
completed gates:

| Issue | Title | Relevance to External Security Review Preparation |
|-------|-------|---------------------------------------------------|
| GL-128 | Pilot Readiness Release Cut | Defines the pilot-ready baseline and accepted caveats under which the security review is conducted. |
| GL-129 | Monitoring / Alerting Baseline | Documents monitoring ownership; reviewer should verify that security events are observable. |
| GL-130 | Incident Response Runbook Execution Gate | Documents incident ownership; reviewer should verify that security incidents are actionable. |
| GL-131 | Pilot Environment Setup Checklist | Defines environment identity and operator ownership; reviewer should verify that the environment is scoped and controlled. |
| GL-132 | Tenant / Workspace Boundary Decision | Defines the boundary posture; reviewer must verify that no multi-tenant claims are made and that pilot boundaries are documented. |

## 13. Explicit Non-Goals

The following changes are explicitly out of scope for GL-133:

- **No security fix implementation** — GL-133 does not implement security fixes.
- **No penetration test execution** — GL-133 does not execute a penetration test.
- **No external reviewer sign-off** — GL-133 does not obtain or claim sign-off from an external reviewer.
- **No production SaaS approval** — GL-133 does not approve production SaaS readiness.
- **No tenant implementation** — no tenant entity, model, or identifier is added.
- **No workspace implementation** — no workspace entity, model, or identifier is added.
- **No API / OpenAPI change** — no endpoint behavior or OpenAPI specification is changed.
- **No frontend / security UI work** — no UI, admin panel, or security dashboard is implemented.
- **No production code changes** (`backend/src/`).
- **No DB migration or schema change**.
- **No dependency additions or version changes**.
- **No website, landing page, design, brand, or marketing file changes**.
- **No deployment automation, monitoring backend integration, or incident automation**.

## 14. Final Statement

> GL-133 creates the **external security review preparation package only**. It documents
> the review scope, posture, security-sensitive components, threat-model review areas,
> reviewer checklist, evidence artifacts, validation commands, expected outputs, and
> go/no-go criteria. It explicitly states that no external security review is completed,
> no penetration test is performed, no production SaaS is approved, and no multi-tenant
> isolation is implemented. It does **not** replace an actual external security review.

(End of file)
