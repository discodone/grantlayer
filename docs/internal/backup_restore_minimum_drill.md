# GrantLayer Backup / Restore Minimum Drill

## Purpose

The backup / restore minimum drill is a **checklist and validation package**
for minimum operational backup/restore readiness. It documents what to protect,
how to validate a restore, and the go/no-go criteria before declaring a
restored environment fit for use.

This drill is **not** a managed backup system, monitoring stack, or incident
response runbook. It is a documentation/test/script package that ensures the
project has a baseline understanding of backup scope and restore acceptance
criteria.

## What This Is

- A **checklist** of critical data categories that must be protected.
- A **validation package** (`scripts/run-backup-restore-drill.sh` +
  `backend/tests/test_gl127_backup_restore_minimum_drill.py`) that asserts the
checklist and runner exist and meet basic safety rules.
- A **restore acceptance guide** that links to the existing runtime gate, smoke
tests, and full suite for post-restore validation.

## What This Is Not

- **No cloud backup automation** — this package does not create, schedule, or
  manage cloud snapshots.
- **No production restore automation** — restores into production must be
  performed by a human operator following a documented runbook.
- **No monitoring or alerting replacement** — observability is out of scope.
- **No incident response runbook** — human escalation and manual review remain
  required.

## Critical Data Categories

The following categories must be considered when planning backup coverage:

1. **Grants** — core authorization records and rules.
2. **Grant requests** — submitted access requests and their states.
3. **Grant executions** — recorded executions and outcomes.
4. **Evidence records / bundles** — audit evidence and attached artifacts.
5. **Audit events** — immutable audit log entries (see hash-chain expectations).
6. **Provenance records / events** — lineage and provenance tracking.
7. **Approvals / lifecycle records** — workflow state transitions and approvals.
8. **Compliance readiness summaries** — compliance posture artifacts.
9. **Policy / rule-pack evaluation artifacts** — evaluated rules and results.
10. **Operators / operator metadata** — identities and roles, excluding raw
    token or secret values (these are stored as hashes or configured externally).
11. **Runtime configuration metadata** — mode, feature flags, and toggles,
    excluding secret values.

## SQLite / Local Backup Expectation

- SQLite-level backup is **only for local / demo / test use**.
- Before risky local operations (schema upgrades, bulk imports, test migrations),
  take a **file-level snapshot** of the SQLite database file.
- File-level snapshot is **not a production recommendation**.
- Never store SQLite backups in version control.

## PostgreSQL / Production-Like Backup Expectation

- Use `pg_dump` or a **managed database snapshot** for production-like environments.
- After any restore, verify:
  1. Dump/snapshot completed without errors.
  2. Dump/snapshot is stored with appropriate retention outside the application.
  3. Dump/snapshot is never stored in the application container or repo.
- **Never publish the database URL or password** in logs, docs, tickets, or chat.
- Credentials must be injected via environment variables or a secrets manager.

## Restore Checklist

Execute the following before declaring a restored environment acceptable:

1. **Restore into an isolated environment** — never test or validate a restore
   directly on production.
2. **Verify runtime mode / config with the production runtime gate** — ensure the
   environment is correctly classified and secrets are present.
3. **Verify schema / migrations compatibility** — all migrations must apply
   cleanly and schema version must match expectations.
4. **Verify critical data counts / presence** — confirm expected tables are
   populated and record counts are reasonable.
5. **Verify audit immutability expectations** — audit events must remain
   protected against UPDATE and DELETE.
6. **Verify audit hash-chain expectations** — row_hash and prev_hash semantics
   must be preserved across the restore boundary.
7. **Run operational smoke tests** — confirm basic health, auth, and payload
   validation behave correctly.
8. **Run the full backend suite for release-grade restore validation** — only
   a passing full suite confirms that the restore did not break application
   behavior.

## Audit / Hash-Chain Integrity Expectations

A valid restore must preserve the audit integrity guarantees established by
GL-103 and GL-108:

- `audit_events` rows must be present after restore.
- Immutability triggers / guards must remain effective — UPDATE and DELETE on
  `audit_events` must still be blocked.
- `row_hash` must be present for audit events where GL-103 applies.
- `prev_hash` chaining semantics must be preserved — each event points to the
  hash of the previous event in chronological order.
- Historical audit rows must **not** be rewritten as part of restore validation.
- A mismatch or missing hash is a **no-go** unless it is explicitly explained
  as pre-chain historical data that predates GL-103.

## Go / No-Go Criteria

### Go

- Restore completes into an isolated environment.
- Critical data categories are present and counts are reasonable.
- Production runtime gate passes.
- Operational smoke tests pass.
- Audit immutability checks pass.
- Audit hash-chain integrity checks pass.
- Full backend suite passes for release-grade restore validation.
- No secret values are printed or leaked during validation.

### No-Go

- Missing critical data (unexpectedly empty grants, audit events, or operators).
- Failed audit immutability or hash-chain checks.
- Unsafe runtime config (production mode missing required flags).
- Secret leakage in logs, test output, or documentation.
- Failed operational smoke tests.
- Failed production runtime gate.
- Failed full backend suite.

## Standard Commands

Run the commands in order for restore validation:

```bash
# 1. Production runtime gate (fast)
scripts/run-production-runtime-gate.sh

# 2. Operational smoke tests (fast)
scripts/run-operational-smoke-tests.sh

# 3. Full backend suite (comprehensive)
scripts/run-full-backend-suite.sh

# 4. Backup / restore minimum drill (checklist validation)
scripts/run-backup-restore-drill.sh
```

Or directly with unittest:

```bash
python3 -m unittest backend.tests.test_gl127_backup_restore_minimum_drill -v
```

## Secret Safety

- **Never print** raw admin token, operator token, database password, private
  key, passphrase, or backup credentials in logs, test output, tickets, or chat.
- **Never include** secret values in documentation examples.
- Report presence only (`configured` / `not configured`), never the value.
- If a secret must be shown for debugging, redact it before sharing.

## Failure Handling

If the backup / restore drill or any related validation fails:

1. **Stop** the release or deployment.
2. **Preserve evidence** — capture logs, record counts, and error messages.
3. **Do not restore over production blindly** — always validate in isolation first.
4. **Escalate to manual review** — a human operator must review before retry.
5. Fix the root cause and re-run the full validation sequence before proceeding.

## Full Suite Rule

The full backend suite requires a timeout of **>= 900 seconds** and must be run via:

```bash
scripts/run-full-backend-suite.sh
```

Do **not** run the full suite through a 120-second-limited shell wrapper.
Coding agents should run targeted tests and relevant regressions instead.
If the environment cannot safely run the full suite with >= 900 seconds,
report exactly:

```
full backend suite: not_run_due_tool_timeout_limit
```
