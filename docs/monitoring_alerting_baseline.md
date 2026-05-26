# GrantLayer Monitoring / Alerting Baseline

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose and Scope

This document is the **GL-129 Monitoring / Alerting Baseline**. It defines the
minimum monitoring and alerting contract for the GrantLayer backend without
implementing a real monitoring backend integration.

**This is a review-only artifact.** No production code, API behavior, schema,
migration, or OpenAPI changes are made in GL-129.

## 2. Baseline Status

| Field | Value |
|-------|-------|
| monitoring/alerting baseline defined | **Yes** |
| real monitoring backend integration implemented | **No** |
| pilot may proceed | **Only with accepted caveats and assigned alert ownership** |

Real monitoring backend integration is not implemented in GL-129.
metrics pipeline, alerting threshold configuration, or observability stack is
wired. A pilot deployment may proceed only if:

- an alert owner is assigned,
- an alert review cadence is defined,
- all pre-pilot gates pass, and
- the accepted caveats from GL-128 are acknowledged.

## 3. Signal Categories

The following signal categories must be observable in logs and health endpoints
before any production observability integration is attempted:

1. **Availability** — `GET /health` liveness and `GET /readiness` readiness
   responses (200 / 503) with deterministic shape.
2. **Readiness** — readiness probe failures indicating dependency or
   configuration issues.
3. **Request volume** — count of requests per path/method, derivable from
   structured logs.
4. **Request latency** — duration of request handling, derivable from structured
   logs or timing wrappers.
5. **Error rate** — proportion of 4xx/5xx responses versus 2xx responses,
   derivable from structured logs.
6. **Auth failures** — `auth_failed` events with `reason_code`, method, path,
   and `correlation_id`.
7. **Forbidden/role failures** — `auth_failed` events where `reason_code` is
   `operator_role_forbidden`, indicating insufficient role for the requested
   action.
8. **Rate-limit events** — `rate_limited` events with `status_code` 429,
   method, path, and `correlation_id`.
9. **Invalid payload/request rejection events** — `request_rejected` events
   with `status_code` 400/413, indicating malformed JSON, top-level non-object
   JSON, or oversized payloads.
10. **Audit write failures** — any failure to append to `audit_events` or
    related audit tables.
11. **Audit/hash-chain integrity issues** — mismatches in `row_hash` or
    `prev_hash`, or unexpected UPDATE/DELETE attempts on `audit_events`.
12. **Database connectivity and pool pressure** — connection acquisition
    failures, pool exhaustion, or slow query indicators.
13. **PostgreSQL audit immutability failures** — UPDATE or DELETE on
    `audit_events` succeeding when they should be blocked by immutability
    triggers.
14. **Runtime gate failures** — `scripts/run-production-runtime-gate.sh`
    returning non-zero or reporting config errors.
15. **Operational smoke failures** — `scripts/run-operational-smoke-tests.sh`
    returning non-zero.
16. **Backup/restore drill failures** — `scripts/run-backup-restore-drill.sh`
    returning non-zero.
17. **Unexpected exceptions** — unhandled exceptions not covered by the above
    categories, captured in structured logs with `correlation_id`.

## 4. Required Safe Log Fields

Every structured log event that supports operational or security monitoring
must include the following fields where applicable:

- `timestamp` — ISO-8601 UTC timestamp.
- `level` — log level (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- `component` — subsystem or module name (e.g., `grantlayer.server`).
- `event` / `action` — event type (e.g., `request_completed`, `auth_failed`,
  `rate_limited`, `request_rejected`).
- `correlation_id` — propagated from `X-Correlation-ID` (GL-118).
- `method` / `path` / `status_code` — HTTP context where applicable.
- `reason_code` — stable machine-readable reason for rejections or failures
  (GL-120).
- `safe principal/operator identifiers` — operator ID or role where already
  supported, never raw tokens.

## 5. Secret Safety

Logs, metrics labels, and alert context must never contain:

- **No raw Authorization header** — never log the full `Authorization` header.
- **No raw tokens** — never log bearer tokens, admin tokens, operator tokens,
  or bootstrap tokens.
- **No raw request bodies** — never echo the original request payload in logs
  or error responses.
- **No DB passwords** — never log database URLs containing passwords or
  connection strings.
- **No private keys/passphrases** — never log signing keys or their
  passphrases.
- **No backup credentials** — never log backup tool credentials or cloud
  storage access keys.

## 6. Minimum Alert Categories

The following alert categories must be defined and owned before any pilot
proceeds:

1. **Service health failure** — `/health` or `/readiness` returning non-200
   for an extended period.
2. **Readiness failure** — `/readiness` returning 503, indicating a dependency
   or configuration problem.
3. **Elevated 5xx/error rate** — increased rate of 5xx responses or unhandled
   exceptions.
4. **Repeated auth failures** — sustained volume of `auth_failed` events,
   indicating possible brute-force or misconfiguration.
5. **Repeated forbidden/operator role failures** — sustained volume of
   `operator_role_forbidden` events, indicating privilege escalation attempts
   or role misconfiguration.
6. **Repeated rate-limit events** — sustained volume of `rate_limited` events,
   indicating abuse or overly restrictive thresholds.
7. **Repeated invalid payload/request rejection events** — sustained volume of
   `request_rejected` events, indicating client bugs or probing.
8. **Audit write failure** — any failure to write to the audit log.
9. **Audit/hash-chain anomaly** — any integrity mismatch in `row_hash` or
   `prev_hash`, or immutability trigger bypass.
10. **DB connectivity/pool failure** — inability to acquire connections or
    pool exhaustion.
11. **PostgreSQL immutability guard failure** — UPDATE or DELETE on
    `audit_events` succeeding when blocked by design.
12. **Runtime gate failure** — pre-deployment config validation failing.
13. **Smoke test failure** — post-deployment smoke tests failing.
14. **Backup/restore drill failure** — backup/restore validation failing.
15. **Unexpected exception spike** — unhandled exceptions exceeding a baseline.

## 7. Pilot Go / No-Go

### Go

A pilot deployment may proceed when ALL of the following are true:

- **Alert owner is assigned** — a named operator or team owns monitoring
  review and response.
- **Alert review cadence is defined** — frequency of log review and alert
  triage is documented (e.g., daily during pilot).
- **Runtime gate passes** — `scripts/run-production-runtime-gate.sh` exits 0.
- **Smoke tests pass** — `scripts/run-operational-smoke-tests.sh` exits 0.
- **Backup/restore drill passes** — `scripts/run-backup-restore-drill.sh`
  exits 0.
- **Full backend suite passes** — `scripts/run-full-backend-suite.sh` exits 0
  with 0 failures and 0 errors.
- **Structured logs/correlation IDs are available** — GL-117 and GL-118
  capabilities are confirmed present.

### No-Go

A pilot deployment must not proceed if ANY of the following are true:

- **No alert receiver/owner** — there is no named person or team responsible
  for reviewing alerts.
- **Health/readiness failures are unobserved** — no process exists to notice
  when `/health` or `/readiness` fails.
- **Auth/security failures are unobserved** — no process exists to notice
  repeated `auth_failed` or `rate_limited` events.
- **DB/audit failures are unobserved** — no process exists to notice audit
  write failures, hash-chain anomalies, or DB connectivity issues.
- **Logs leak secrets** — any structured log event contains raw tokens,
  headers, request bodies, passwords, keys, or backup credentials.
- **Runtime/smoke/backup/full-suite gate fails** — any pre-pilot validation
  command returns non-zero.

## 8. Relationship to Existing Gates

GL-129 builds on and references the following completed gates:

| Issue | Title | Relevance to Monitoring / Alerting |
|-------|-------|------------------------------------|
| GL-117 | Structured Logging Integration | Provides the `event`, `level`, `component`, `correlation_id`, and `status_code` fields required for log-based alerting. |
| GL-118 | Correlation ID Propagation Baseline | Provides `correlation_id` for tracing failures across requests and alerts. |
| GL-120 | Auth Failure Structured Event Logging | Provides `auth_failed` and `rate_limited` events with stable `reason_code` for security alerting. |
| GL-125 | Operational Smoke Test Bundle | Provides fast post-deployment validation; smoke failures are an alert category. |
| GL-126 | Production Runtime Gate | Provides pre-deployment config validation; runtime gate failures are an alert category. |
| GL-127 | Backup / Restore Minimum Drill | Provides backup/restore validation; drill failures are an alert category. |
| GL-128 | Pilot Readiness Release Cut | Defines the pilot-ready baseline and accepted caveats under which GL-129 is evaluated. |

## 9. Recommended Implementation Path After Baseline

After GL-129 is accepted, the following steps are recommended to achieve
production observability:

1. **Choose monitoring backend** — select Prometheus, Grafana, CloudWatch,
   Datadog, Sentry, OpenTelemetry, or equivalent.
2. **Wire log aggregation** — ship structured logs from GL-117 to the chosen
   backend with secret redaction verified.
3. **Define alert receivers** — configure notification channels (email, SMS,
   pager, chat) for each alert category in Section 6.
4. **Test alert delivery** — trigger synthetic failures and confirm alerts
   reach the assigned owner within the defined SLA.
5. **Create incident-response handoff in GL-130** — document escalation
   procedures, on-call contacts, and runbook execution paths.

## 10. Explicit Non-Goals

The following changes are explicitly out of scope for GL-129:

- **No monitoring backend integration** — no Prometheus, Grafana, CloudWatch,
  Datadog, Sentry, or OpenTelemetry wiring.
- **No new metrics endpoint** — unless required by a future issue.
- **No production code changes** (`backend/src/`).
- **No OpenAPI changes**.
- **No database migration or schema changes**.
- **No dependency additions or version changes**.
- **No frontend, website, design, brand, or marketing file changes**.
- **No incident response automation** — that is GL-130.
- **No tenant model, billing, or onboarding** — future work.

## 11. Final Statement

> GL-129 defines the **minimum monitoring/alerting contract** for the
> GrantLayer backend. It documents what must be observed, what must be alerted
> on, and what safety rules apply to logs and metrics. It does **not** complete
> full production observability integration. A real monitoring backend,
> log aggregation pipeline, and tested alert delivery remain future work.
