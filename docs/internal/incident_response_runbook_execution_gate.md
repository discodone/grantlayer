# GrantLayer Incident Response / Operational Runbook Execution Gate

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose and Scope

This document is the **GL-130 Incident Response / Operational Runbook Execution Gate**.
It defines the minimum incident-response execution contract for the GrantLayer
backend. It documents what to do when an incident occurs, how to classify it,
how to respond, and what evidence to capture.

**This is a review-only artifact.** No production code, API behavior, schema,
migration, or OpenAPI changes are made in GL-130.

**This is NOT incident automation.**
**This is NOT monitoring backend integration.**
**This is NOT production code.**

## 2. Baseline Status

| Field | Value |
|-------|-------|
| incident response runbook gate defined | **Yes** |
| incident automation implemented | **No** |
| production incident response fully automated | **No** |
| controlled pilot requires named operational owner | **Yes** |

Incident automation is not implemented in GL-130.
Production incident response is not fully automated.
A controlled pilot requires a named operational owner who can execute this
runbook manually.

## 3. Incident Categories

The following incident categories must be recognized and classified during
triage:

1. **Service unavailable** — `/health` or `/readiness` failing continuously,
   indicating the service is not accepting traffic.
2. **Readiness failure** — `/readiness` returning 503, indicating a dependency
   or configuration problem.
3. **Elevated 5xx/error rate** — increased rate of 5xx responses or unhandled
   exceptions beyond a baseline.
4. **Repeated auth failures** — sustained volume of `auth_failed` events,
   indicating possible brute-force or misconfiguration.
5. **Repeated forbidden/operator-role failures** — sustained volume of
   `operator_role_forbidden` events, indicating privilege escalation attempts
   or role misconfiguration.
6. **Repeated rate-limit events** — sustained volume of `rate_limited` events,
   indicating abuse or overly restrictive thresholds.
7. **Invalid payload/request rejection spike** — sustained volume of
   `request_rejected` events, indicating client bugs or probing.
8. **Audit write failure** — any failure to append to `audit_events` or
   related audit tables.
9. **Audit/hash-chain integrity anomaly** — mismatches in `row_hash` or
   `prev_hash`, or unexpected UPDATE/DELETE attempts on `audit_events`.
10. **Database connectivity/pool pressure/failure** — connection acquisition
    failures, pool exhaustion, or slow query indicators.
11. **PostgreSQL audit immutability guard failure** — UPDATE or DELETE on
    `audit_events` succeeding when they should be blocked by immutability
    triggers.
12. **Runtime gate failure** — `scripts/run-production-runtime-gate.sh`
    returning non-zero or reporting config errors.
13. **Operational smoke failure** — `scripts/run-operational-smoke-tests.sh`
    returning non-zero.
14. **Backup/restore drill failure** — `scripts/run-backup-restore-drill.sh`
    returning non-zero.
15. **Unexpected exception spike** — unhandled exceptions not covered by the
    above categories, captured in structured logs with `correlation_id`.
16. **Suspected secret exposure** — any indication that tokens, private keys,
    database passwords, or backup credentials may have been logged, returned
    in responses, or exposed to unauthorized parties.

## 4. Severity Levels

| Level | Name | Description |
|-------|------|-------------|
| **SEV1** | Critical | Active outage, data-integrity issue, secret exposure, or audit/hash-chain anomaly. Requires immediate response. |
| **SEV2** | High | Degraded core behavior, repeated security failures, or database instability. Requires prompt response. |
| **SEV3** | Medium | Isolated issue or recoverable operational degradation. Can be addressed within normal working hours. |
| **SEV4** | Low | Informational/manual follow-up. No immediate user or operator impact. |

## 5. First-Response Checklist

When an incident is detected, execute the following in order:

1. **Assign incident owner** — a single named person owns the incident from
   detection to resolution or handoff.
2. **Freeze risky deploys** — do not deploy new code, change configuration, or
   rotate secrets until the incident is understood.
3. **Capture start time and current main commit** — record the exact UTC
   timestamp and the current `main` commit hash.
4. **Collect correlation_id values** — gather `correlation_id` values from
   affected requests from structured logs (GL-118).
5. **Identify affected endpoints/components** — list which paths, methods, or
   subsystems are involved.
6. **Check health/readiness** — run `GET /health` and `GET /readiness` and
   record responses.
7. **Inspect structured logs safely** — review logs for relevant events without
   exposing secrets. Use filters on `event`, `reason_code`, and
   `correlation_id`.
8. **Run smoke tests if safe** — if the system is still accessible, run
   `scripts/run-operational-smoke-tests.sh` to confirm core boundaries.
9. **Run runtime gate if config/runtime issue suspected** — if the incident
   may be configuration-related, run `scripts/run-production-runtime-gate.sh`.
10. **Consult backup/restore drill if data integrity issue suspected** — if
    audit or data integrity is in question, review `docs/backup_restore_minimum_drill.md`.
11. **Preserve evidence** — do not delete logs, do not truncate tables, and do
    not restart services until evidence is captured.

## 6. Triage Workflow

After first response, classify the incident:

1. **Classify severity** — assign SEV1, SEV2, SEV3, or SEV4 based on Section 4.
2. **Identify category** — map the incident to one or more categories from
   Section 3.
3. **Determine user/operator impact** — how many users or operators are
   affected, and what operations are blocked.
4. **Determine whether security/data integrity is involved** — if auth,
   audit, hash-chain, or secret exposure is suspected, escalate immediately.
5. **Decide continue / degraded operation / pause pilot** —
   - **Continue** if the issue is SEV4 or a contained SEV3 with no security
     impact.
   - **Degraded operation** if core functions work but some paths are affected
     (SEV2 or contained SEV3).
   - **Pause pilot** if the issue is SEV1, an unowned SEV2, or involves
     security/data integrity.

## 7. Evidence Capture

The following evidence must be captured for every incident:

- **Timestamps** — detection time, first-response time, and any relevant log
  timestamps in UTC.
- **correlation_id values** — all `correlation_id` values associated with
  affected requests.
- **Safe log snippets** — relevant structured log lines with secrets redacted.
- **Status codes and reason codes** — HTTP status codes and `reason_code`
  values from affected responses.
- **Affected command outputs** — output from health checks, smoke tests,
  runtime gate, or backup/restore drill.
- **Current git/main commit** — the commit hash of the deployed code.
- **Runtime mode/config summary without secrets** — runtime mode and config
  flag presence, never values.

### Secret Safety During Evidence Capture

- **No raw Authorization headers** — never include the full `Authorization`
  header in evidence.
- **No raw tokens** — never include bearer tokens, admin tokens, operator
  tokens, or bootstrap tokens in evidence.
- **No raw request bodies** — never echo the original request payload in
  evidence.
- **No DB passwords** — never include database URLs containing passwords or
  connection strings.
- **No private keys/passphrases** — never include signing keys or their
  passphrases.
- **No backup credentials** — never include backup tool credentials or cloud
  storage access keys.

## 8. Escalation and Ownership

| Role | Responsibility |
|------|----------------|
| **Incident owner** | Single point of accountability for incident lifecycle. |
| **Technical responder** | Performs technical investigation, runs gates, and implements mitigations. |
| **Operator/business owner** | Decides whether to continue, degrade, or pause pilot operations. |
| **Security/data-integrity escalation** | Engaged for SEV1, suspected secret exposure, or audit/hash-chain anomalies. |
| **Decision log owner** | Records all go/no-go and continue/degrade/pause decisions. |

## 9. Required Commands

The following commands must be available and known to the incident owner:

```bash
# 1. Production runtime gate (fast config validation)
scripts/run-production-runtime-gate.sh

# 2. Operational smoke tests (fast operational validation)
scripts/run-operational-smoke-tests.sh

# 3. Backup/restore minimum drill (data integrity checklist)
scripts/run-backup-restore-drill.sh

# 4. Full backend suite (comprehensive regression)
scripts/run-full-backend-suite.sh
```

All four must exit 0 with no failures and no errors before a pilot deployment
is permitted. During an incident, they are re-run to validate the current state.

## 10. Go/No-Go for Pilot Operation

### GO — Pilot may continue or resume

GO is only permitted when **ALL** of the following are true:

- **Owner assigned** — a named incident owner is accountable.
- **Incident understood** — category and severity are classified.
- **Evidence captured** — all required evidence from Section 7 is collected.
- **No active security/data-integrity issue** — no suspected secret exposure,
  audit/hash-chain anomaly, or unauthorized access.
- **Required gates pass** — runtime gate, smoke tests, and backup/restore drill
  all exit 0.

### NO-GO — Pilot must pause

NO-GO if **ANY** of the following are true:

- **Unowned incident** — no named incident owner.
- **Secret exposure** — any suspected leak of tokens, keys, passwords, or
  backup credentials.
- **Audit/hash-chain anomaly** — any integrity mismatch or immutability guard
  failure.
- **DB failure** — database connectivity loss, pool exhaustion, or immutability
  trigger bypass.
- **Runtime gate failure** — `scripts/run-production-runtime-gate.sh` returns
  non-zero.
- **Smoke failure** — `scripts/run-operational-smoke-tests.sh` returns non-zero.
- **Backup/restore drill failure** — `scripts/run-backup-restore-drill.sh`
  returns non-zero.
- **Full suite failure** — `scripts/run-full-backend-suite.sh` reports failures
  or errors.
- **Unresolved SEV1/SEV2** — any SEV1 or unowned SEV2 remains open.

## 11. Relationship to Existing Gates

GL-130 builds on and references the following completed gates:

| Issue | Title | Relevance to Incident Response |
|-------|-------|--------------------------------|
| GL-117 | Structured Logging Integration | Provides the `event`, `level`, `component`, `correlation_id`, and `status_code` fields required for log-based incident investigation. |
| GL-118 | Correlation ID Propagation Baseline | Provides `correlation_id` for tracing failures across requests during incident triage. |
| GL-120 | Auth Failure Structured Event Logging | Provides `auth_failed` and `rate_limited` events with stable `reason_code` for security incident classification. |
| GL-125 | Operational Smoke Test Bundle | Provides fast post-deployment validation; smoke failures are an incident category and are re-run during response. |
| GL-126 | Production Runtime Gate | Provides pre-deployment config validation; runtime gate failures are an incident category and are re-run during response. |
| GL-127 | Backup / Restore Minimum Drill | Provides backup/restore validation; drill failures are an incident category and guide data-integrity response. |
| GL-128 | Pilot Readiness Release Cut | Defines the pilot-ready baseline and accepted caveats under which GL-130 is evaluated. |
| GL-129 | Monitoring / Alerting Baseline | Defines the signal categories and alert types that feed into incident detection and classification. |

## 12. Explicit Non-Goals

The following changes are explicitly out of scope for GL-130:

- **No incident automation** — no automated remediation, auto-scaling, or
  self-healing is implemented.
- **No pager/on-call platform integration** — no PagerDuty, Opsgenie, or
  equivalent wiring.
- **No monitoring backend integration** — no Prometheus, Grafana, CloudWatch,
  Datadog, Sentry, or OpenTelemetry wiring.
- **No production code changes** (`backend/src/`).
- **No OpenAPI changes**.
- **No database migration or schema changes**.
- **No dependency additions or version changes**.
- **No frontend, website, design, brand, or marketing file changes**.
- **No tenant model, billing, or onboarding** — future work.
- **No deployment automation** — that is GL-131.

## 13. Final Statement

> GL-130 defines the **minimum incident-response execution contract** for the
> GrantLayer backend. It documents what must be observed, how to classify
> incidents, how to respond, what evidence to capture, and what safety rules
> apply. It does **not** complete full automated incident response. Incident
> automation, pager integration, and monitoring backend wiring remain future
> work.
