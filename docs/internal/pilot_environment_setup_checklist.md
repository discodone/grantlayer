# GrantLayer Pilot Environment Setup Checklist

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Scope

This document is the **GL-131 Pilot Environment Setup Checklist**. It defines the
minimum review, artifact, and test-only contract for setting up a GrantLayer pilot
environment before any deployment. It is a checklist for operators and responders,
not an automation package.

**This is a review-only artifact.** No production code, API behavior, schema,
migration, or OpenAPI changes are made in GL-131.

**This is NOT deployment automation.**
**This is NOT infrastructure provisioning.**
**This is NOT monitoring backend integration.**
**This is NOT incident automation.**
**This is NOT production code.**

## 2. Baseline Status

| Field | Value |
|-------|-------|
| pilot environment setup checklist defined | **Yes** |
| deployment automation implemented in GL-131 | **No** |
| infrastructure provisioning implemented in GL-131 | **No** |
| backend remains pilot-ready with caveats | **Yes** |

The backend is pilot-ready with caveats, not production SaaS complete.
No deployment automation is implemented in GL-131.
No infrastructure provisioning is implemented in GL-131.

## 3. Environment Identity Checklist

Before any pilot environment is accepted, the following identity fields must be
documented and known to the operator owner:

1. **Pilot environment name** — a unique, human-readable name for the environment.
2. **Environment owner/operator** — named individual or team responsible for the
   environment lifecycle.
3. **Technical responder** — named person who can access logs, run gates, and
   execute runbooks.
4. **Business/operator owner** — named person who can make go/no-go and
   continue/degrade/pause decisions.
5. **Main/release commit** — the exact commit hash deployed to the pilot environment.
6. **Runtime mode** — one of `local`, `test`, `demo`, `staging`, `production`.
7. **Database mode** — SQLite (local/demo/test only) or PostgreSQL (production-like).
8. **Pilot start/end window** — agreed calendar window for the pilot.

## 4. Runtime/Config Checklist

The following runtime and configuration checks must pass before the environment
is accepted:

1. **Production-like runtime mode intentionally selected** — `staging` or `production`
   is explicitly chosen for real pilot environments.
2. **Local/test/demo modes not used for real pilot unless explicitly approved** —
   these modes are for development and CI only.
3. **Startup fail-closed gates pass** — `startup_ok()` returns true and
   `startup_errors()` is empty.
4. **Unsafe config rejected** — missing admin token, missing challenge enforcement,
   or enabled demo endpoints in a production-like mode are rejected.
5. **Runtime gate command required** — `scripts/run-production-runtime-gate.sh`
   must exit 0 before any deployment.

## 5. Secrets Checklist

Secrets must be configured safely and never exposed in documentation, logs,
screenshots, or evidence artifacts:

1. **Admin token configured securely** — `GRANTLAYER_ADMIN_TOKEN` is present and
   stored outside the repository.
2. **Operator token handling defined** — operator tokens are hashed at rest;
   raw tokens are never stored in the database or logged.
3. **DB URL/credentials handled securely** — `GRANTLAYER_DATABASE_URL` or
   `GRANTLAYER_DB` is injected via environment variables or a secrets manager.
4. **Signing/private keys handled securely** — `GRANTLAYER_SIGNING_PRIVATE_KEY`
   and `GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE` are stored outside the repo.
5. **No secrets in docs/logs/screenshots** — credentials, tokens, keys, and
   passphrases are never included in documentation, log snippets, screenshots,
   or chat messages.
6. **No raw Authorization headers/tokens/request bodies in evidence** — evidence
   capture must redact or omit the `Authorization` header, bearer tokens, and
   original request payloads.

## 6. Database Checklist

Database configuration must match the runtime mode and pilot requirements:

1. **SQLite limited to local/demo/test** — SQLite is acceptable only for local
   development, demo scenarios, and automated tests.
2. **PostgreSQL expected/preferred for production-like pilot** — staging and
   production-like pilots should use PostgreSQL.
3. **Migrations applied** — all database migrations have been applied cleanly
   and the schema version matches the deployed code.
4. **Audit immutability expectations understood** — operators understand that
   `audit_events` must not be updated or deleted, and immutability triggers
   block such attempts.
5. **PostgreSQL connection pooling config reviewed** — min/max pool sizes are
   configured appropriately for the expected load.
6. **DB backup method identified** — the operator knows how backups are taken
   (`pg_dump`, managed snapshot, or file-level copy for SQLite).

## 7. Operator Checklist

A named operator must be accountable and prepared:

1. **Named operator owner** — a single named person owns operator tokens,
   role assignments, and environment access.
2. **Token expiry/rotation understood** — the operator understands token
   lifetimes, rotation procedures, and how to revoke tokens.
3. **Revoked/expired behavior verified** — expired or revoked tokens are
   rejected; the operator has verified this behavior.
4. **Emergency escalation contact known** — the operator knows who to contact
   for security or data-integrity escalation.

## 8. Required Validation Commands

The following commands must be run and pass before any pilot deployment:

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
is permitted.

## 9. Monitoring/Alerting Checklist

Monitoring and alerting ownership must be established before the pilot begins:

1. **Alert owner assigned** — a named person or team owns monitoring review
   and alert response.
2. **Alert receiver/channel known** — the alert owner knows where alerts will
   be received (email, chat, or manual log review).
3. **Alert review cadence defined** — frequency of log review and alert triage
   is documented (e.g., daily during pilot).
4. **GL-129 baseline acknowledged** — the operator has reviewed and acknowledges
   the monitoring/alerting baseline defined in GL-129.

## 10. Incident Response Checklist

Incident response ownership and runbook awareness must be established:

1. **Incident owner assigned** — a single named person owns incident lifecycle
   from detection to resolution or handoff.
2. **GL-130 runbook acknowledged** — the operator has reviewed and acknowledges
   the incident response runbook execution gate defined in GL-130.
3. **Escalation path documented** — the operator knows how to escalate SEV1 and
   SEV2 incidents to the technical responder and business owner.
4. **Evidence capture rules understood** — the operator knows what evidence to
   capture (timestamps, correlation IDs, safe logs, status codes) and what
   must never be captured (raw tokens, headers, request bodies, passwords).

## 11. Backup/Restore Checklist

Backup and restore readiness must be confirmed:

1. **Backup method identified** — the operator knows the backup tool or process
   (`pg_dump`, managed snapshot, or SQLite file copy).
2. **Restore drill known** — the operator knows how to run the restore drill
   and where to find the documentation (`docs/backup_restore_minimum_drill.md`).
3. **Isolated restore expectation acknowledged** — restores must be tested in an
   isolated environment, never directly on the active pilot or production
   environment.
4. **No direct restore over pilot/production without review** — a human operator
   must review any restore operation before it is applied to an active pilot
   or production environment.

## 12. Pilot Go/No-Go

### GO — Pilot may proceed

GO is only permitted when **ALL** of the following are true:

- **Environment identity complete** — environment name, owner, technical responder,
  business owner, commit, runtime mode, database mode, and pilot window are documented.
- **Runtime/config safe** — production-like mode is selected, startup gates pass,
  unsafe config is rejected, and the runtime gate exits 0.
- **Secrets safe** — admin token, operator tokens, DB credentials, and signing keys
  are configured securely; no secrets appear in docs, logs, or screenshots.
- **Database ready** — migrations applied, audit immutability understood,
  connection pooling reviewed, and backup method identified.
- **Operator prepared** — named operator owner, token expiry/rotation understood,
  revoked/expired behavior verified, and emergency contact known.
- **Required gates pass** — runtime gate, smoke tests, backup/restore drill,
  and full backend suite all exit 0.
- **Monitoring owned** — alert owner assigned, receiver/channel known, and
  review cadence defined; GL-129 acknowledged.
- **Incident response owned** — incident owner assigned, GL-130 runbook acknowledged,
  escalation path documented, and evidence capture rules understood.
- **Backup/restore ready** — backup method identified, restore drill known,
  isolated restore acknowledged, and no direct restore over pilot/production
  without review.
- **Pilot commit traceable** — the exact main/release commit deployed is recorded.

### NO-GO — Pilot must not proceed

NO-GO if **ANY** of the following are true:

- **Any required gate fails** — runtime gate, smoke tests, backup/restore drill,
  or full backend suite returns non-zero.
- **Secrets unsafe** — raw secrets in files, logs, docs, screenshots, or chat.
- **DB/audit setup uncertain** — migrations not applied, audit immutability not
  understood, or backup method unidentified.
- **Monitoring unowned** — no named alert owner, no review cadence, or GL-129
  not acknowledged.
- **Incident response unowned** — no named incident owner or GL-130 runbook not
  acknowledged.
- **Backup/restore unclear** — backup method unknown, restore drill not known,
  or isolated restore not acknowledged.
- **Pilot commit not traceable** — the exact deployed commit hash is unknown.

## 13. Relationship to Existing Gates

GL-131 builds on and references the following completed gates:

| Issue | Title | Relevance to Pilot Environment Setup |
|-------|-------|----------------------------------------|
| GL-125 | Operational Smoke Test Bundle | Provides fast post-deployment validation; must pass before pilot begins. |
| GL-126 | Production Runtime Gate | Provides pre-deployment config validation; must pass before pilot begins. |
| GL-127 | Backup / Restore Minimum Drill | Provides backup/restore validation; must pass and be understood before pilot begins. |
| GL-128 | Pilot Readiness Release Cut | Defines the pilot-ready baseline and accepted caveats under which GL-131 is evaluated. |
| GL-129 | Monitoring / Alerting Baseline | Defines monitoring ownership and alert review requirements for the pilot. |
| GL-130 | Incident Response / Operational Runbook Execution Gate | Defines incident ownership, escalation, and evidence capture requirements for the pilot. |

## 14. Explicit Non-Goals

The following changes are explicitly out of scope for GL-131:

- **No deployment automation** — no CI/CD pipeline, container build automation,
  or automated release orchestration is implemented.
- **No infrastructure provisioning** — no Terraform, CloudFormation, Ansible,
  or equivalent infrastructure-as-code is implemented.
- **No monitoring backend integration** — no Prometheus, Grafana, CloudWatch,
  Datadog, Sentry, or OpenTelemetry wiring is implemented.
- **No incident automation** — no automated remediation, auto-scaling, or
  self-healing is implemented.
- **No tenant/workspace boundary decision** — tenant isolation and multi-tenancy
  remain future work (GL-132).
- **No production code changes** (`backend/src/`).
- **No OpenAPI changes**.
- **No database migration or schema changes**.
- **No dependency additions or version changes**.
- **No frontend, website, design, brand, or marketing file changes**.
- **No production SaaS complete claim** — this checklist does not make the
  backend production SaaS complete by itself.

## 15. Final Statement

> GL-131 defines the **minimum pilot environment setup contract** for the
> GrantLayer backend. It documents what must be verified before a controlled
> pilot deployment: environment identity, runtime safety, secret handling,
> database readiness, operator preparedness, required validation commands,
> monitoring ownership, incident response ownership, and backup/restore
> readiness. It does **not** complete production SaaS readiness by itself.
> Deployment automation, infrastructure provisioning, monitoring backend
> integration, incident automation, and tenant/workspace boundaries remain
> future work.

(End of file)
