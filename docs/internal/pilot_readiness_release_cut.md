# GrantLayer Pilot Readiness Review / Release Cut

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose and Scope

This document is the **GL-128 Pilot Readiness Review / Release Cut**. It records the
formal release-cut judgment after completing the GL-116–GL-127 production-hardening
sprint and establishes the go/no-go criteria for a controlled pilot deployment.

**This is a review-only artifact.** No production code, API behavior, schema,
migration, or OpenAPI changes are made in GL-128.

## 2. Baseline

| Field | Value |
|-------|-------|
| Main after | GL-127 (Backup / Restore Minimum Drill) |
| Latest merge commit (short) | `333a6dd` |
| Full backend suite — passed | 3312 |
| Full backend suite — skipped | 43 |
| Full backend suite — failures | 0 |
| Full backend suite — errors | 0 |
| Full backend suite — timeout | No |

## 3. Review Disposition

```
disposition: pilot_ready_with_caveats
```

The GrantLayer backend is **ready for a controlled pilot** subject to the operational
constraints listed in Section 6 (Accepted Pilot Caveats).

It is **not yet production SaaS**. It is **not yet commercial SaaS complete**. Remaining
areas — including monitoring/alerting, incident response, tenant/workspace boundaries,
external security review, legal/privacy, customer onboarding/admin UX, and production
deployment automation — are documented in Section 7 (Production SaaS Blockers) and remain
future work.

## 4. What Is Ready for Pilot

The following backend capabilities are present, tested, and validated:

- **Product Core backend** — grant lifecycle (submit, approve, execute, evidence, audit) is
  implemented end-to-end with deterministic test coverage.
- **Auth and operator boundaries** — operator tokens, admin token enforcement, expiry,
  rotation, and challenge flow are implemented and CI-gated.
- **Request validation** — payload shape, size limits, JSON structure, and string length
  validation reject unsafe inputs with safe, non-leaking error responses.
- **Structured logging and correlation** — all request handlers emit structured log events;
  X-Correlation-ID propagates through requests and appears in log output.
- **Auth failure security logging** — all auth failure paths emit structured security
  events with a stable `reason_code` field; no raw token or header material is logged.
- **Production runtime gate** — a fast, automated config validation check catches missing
  or unsafe configuration before any deployment.
- **Operational smoke tests** — a focused post-deployment validation suite covers health,
  auth boundary, payload validation, correlation ID, and logging safety.
- **Backup/restore minimum drill** — critical data categories are defined; restore
  acceptance criteria and go/no-go gates are documented.
- **PostgreSQL readiness baseline** — audit immutability triggers are CI-gated against a
  real PostgreSQL instance; connection pooling is implemented and configurable.
- **Audit and hash-chain integrity baseline** — row-level hash chain (`row_hash`,
  `prev_hash`) and PostgreSQL-level UPDATE/DELETE blocking are implemented and verified.

## 5. Completed Readiness Gates

The following gates were completed during the GL-116–GL-127 sprint:

| Issue | Title | Description |
|-------|-------|-------------|
| GL-116 | PostgreSQL Audit Immutability CI Gate | Real PostgreSQL integration test proving GL-108 audit log triggers block UPDATE and DELETE; prevents silent regression on the immutability guarantee |
| GL-117 | Structured Logging Integration | server.py request handlers emit structured log events for operational and security events without changing API behavior or auth semantics |
| GL-118 | Correlation ID Propagation Baseline | X-Correlation-ID is echoed in all responses and appears in structured log events; unsafe or oversized IDs are replaced rather than reflected |
| GL-119 | Operator Token Expiry and Rotation Baseline | Operator tokens expire and support rotation without leaking raw token material; fail-closed on expiry |
| GL-120 | Auth Failure Structured Event Logging | All auth failure paths emit structured security events with a stable `reason_code` field and `correlation_id`; no raw token or header leakage |
| GL-121 | Full Backend Suite Timeout Wrapper | `scripts/run-full-backend-suite.sh` wraps the full suite with a configurable timeout (default 900 s) and preserves exit codes |
| GL-123 | PostgreSQL Connection Pooling Baseline | psycopg2 `SimpleConnectionPool` with configurable min/max connections; SQLite path unchanged; credentials never exposed in failure messages |
| GL-124 | Request Payload Shape Validation Gate | Oversized, malformed, wrong-shape, and non-object JSON bodies are rejected with safe error responses; raw payload is never echoed |
| GL-125 | Operational Smoke Test Bundle | Fast, focused validation suite for post-deployment confidence: health, auth boundary, payload validation, correlation ID, and logging safety |
| GL-126 | Production Runtime Gate | Fast config validation before deployment covering runtime mode classification, production-like config safety, and secret-handling conventions |
| GL-127 | Backup / Restore Minimum Drill | Checklist and validation package for minimum backup/restore readiness; defines critical data categories, restore acceptance criteria, and go/no-go gates |

## 6. Accepted Pilot Caveats

A pilot deployment is permissible subject to the following constraints:

1. **Controlled environment** — deployment must be isolated (local, demo, or staging
   equivalent); this is not a public production deployment.
2. **Limited users and operators** — pilot operators must be named and accountable;
   the pilot scope is not open-ended or multi-tenant.
3. **Manual operator oversight** — no automated incident response or on-call alerting;
   a human operator must monitor the deployment during the pilot.
4. **Manual deployment and runbook steps** — there is no automated CI/CD deployment
   pipeline; operators follow documented runbook steps.
5. **Manual full-suite gate** — the full backend suite (3312+ tests) must be run and
   pass before each pilot deployment, but execution is manual.
6. **Backup/restore is minimum package, not managed backup automation** — the GL-127
   drill defines acceptance criteria and checklist items, not automated backup
   scheduling, retention policies, or cloud snapshot management.
7. **Monitoring and alerting not complete** — there is no metrics pipeline, alerting
   threshold configuration, or observability stack. This is a production SaaS blocker
   documented in Section 7.

## 7. Production SaaS Blockers / Not Yet Complete

The following areas must be addressed before GrantLayer can be described as
production-ready SaaS or commercial SaaS complete:

1. **Monitoring and alerting baseline** — no metrics pipeline, health alerting, latency
   thresholds, or error-rate dashboards. Proposed next: GL-129.
2. **Incident response runbook execution gate** — escalation procedures, on-call
   contacts, and runbook execution paths are not yet defined or tested. Proposed: GL-130.
3. **Tenant and workspace boundary** — no multi-tenant architecture, tenant isolation,
   or per-tenant configuration. A design decision and boundary definition are required
   before any multi-tenant or commercial deployment. Proposed: GL-132.
4. **Production deployment automation or explicit ops procedure** — no container images,
   orchestration manifests, or automated deployment pipelines. A documented and tested
   ops procedure is a minimum requirement for production claims. Proposed: GL-131.
5. **External security review** — no third-party or independent security review has been
   completed. Required before any commercial or regulated deployment. Proposed: GL-133.
6. **Legal, privacy, and data-retention review** — no data classification matrix,
   evidence retention policy, or legal review has been completed.
7. **Customer onboarding, admin UX, and commercial packaging** — no customer-facing
   onboarding flow, admin interface, or commercial licensing/billing structure exists.

## 8. Go / No-Go Criteria for Pilot

### Go

A pilot deployment may proceed when ALL of the following are true:

- `scripts/run-production-runtime-gate.sh` passes with no failures.
- `scripts/run-operational-smoke-tests.sh` passes with no failures.
- `scripts/run-backup-restore-drill.sh` passes with no failures.
- `scripts/run-full-backend-suite.sh` passes with 0 failures and 0 errors.
- Secrets (admin token, operator tokens, private key) are configured via environment
  variables or a secrets manager — no raw secrets in files, logs, or docs.
- Pilot operators are named and have accepted operational responsibility.
- A rollback and restore path is documented and known before deployment begins.

### No-Go

A pilot deployment must not proceed if ANY of the following are true:

- Any failure or error in the full backend suite.
- Any failure in the production runtime gate.
- Any failure in the operational smoke tests.
- Any failure in the backup/restore drill.
- Unsafe or missing secrets configuration (raw secrets in files, missing required env vars).
- Any audit log or hash-chain integrity issue detected.
- Operational responsibility for the pilot is unowned or unacknowledged.

## 9. Required Pre-Pilot Commands

Run all four commands and confirm each passes before deployment:

```bash
scripts/run-production-runtime-gate.sh
scripts/run-operational-smoke-tests.sh
scripts/run-backup-restore-drill.sh
scripts/run-full-backend-suite.sh
```

All four must exit 0 with no failures and no errors before a pilot deployment is
permitted.

## 10. Recommended Next Issues

| Issue | Title |
|-------|-------|
| GL-129 | Monitoring / Alerting Baseline |
| GL-130 | Incident Response / Operational Runbook Execution Gate |
| GL-131 | Pilot Environment Setup Checklist |
| GL-132 | Tenant / Workspace Boundary Decision |
| GL-133 | External Security Review Preparation |
| GL-134 | Pilot Partner Dry Run |

## 11. Explicit Non-Goals of GL-128

The following changes are explicitly out of scope for this issue:

- No production code changes (`backend/src/`).
- No OpenAPI specification changes.
- No database migration or schema changes.
- No dependency additions or version changes.
- No frontend, website, design, brand, or marketing file changes.

## 12. Final Release-Cut Statement

> The GrantLayer backend is **pilot-ready with caveats** as of GL-127 / commit `333a6dd`.
> It is **not production SaaS complete**. It is **not commercial SaaS complete**.
> A controlled pilot may proceed when all four pre-pilot gate commands pass and the
> go/no-go criteria in Section 8 are satisfied.
