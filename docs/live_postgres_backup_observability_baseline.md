# GL-205 — Live PostgreSQL Validation / Backup-Restore Drill / Observability Baseline

**Issue ID:** GL-205
**Branch:** `gl-205-live-postgres-backup-observability-baseline`
**Status:** Internal / Developer Preview

---

## Context

GL-200A, GL-200B, GL-200C, GL-201, GL-202, GL-203, GL-203B, GL-203C, and
GL-204 are merged internally. The GL-200 tenant/workspace isolation block,
GL-201 production auth/secrets/config hardening, GL-202 persistence/PostgreSQL/
migration readiness, GL-203 API contract/SDK packaging decision, GL-203B
OpenAPI contract cleanup, GL-203C SDK prototype/packaging boundary, and
GL-204 Production Ops / Go-No-Go v3 are all represented by clean doc, JSON, and
test artifacts.

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation baseline implemented but not production-complete
- No official SDK/package is claimed or published

GL-205 is an **operational readiness baseline**, not a production SaaS
readiness declaration. It addresses three of the P0 blockers identified in
GL-204:
1. Live PostgreSQL validation
2. Backup/restore drill baseline
3. Observability baseline

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
grant/institutional data is used.

---

## Scope

GL-205 covers:
- A gated live PostgreSQL validation path (`scripts/ops/gl205_live_postgres_validation.py`)
- A deterministic SQLite backup/restore drill baseline (`scripts/ops/gl205_backup_restore_drill.py`)
- A PostgreSQL backup/restore manual checklist (documented, not automated)
- An observability baseline covering log events, correlation IDs, signal categories, and secret-safety rules
- Documentation of remaining operational blockers
- Preservation assessment for GL-200 through GL-204 constraints

## Non-Goals

GL-205 is not:
- A production SaaS readiness declaration
- Real customer/private grant/institutional data readiness
- An automated backup system or production monitoring stack
- A live PostgreSQL production deployment
- An official SDK/package implementation or publication
- Frontend, website, or design changes
- GitHub workflow changes
- Public publish, GitHub push, or visibility change

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|----------|
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
| docs/sdk_prototype_packaging_boundary.md | Yes |
| docs/examples/gl203c/sdk_prototype_packaging_boundary.json | Yes |
| docs/openapi_api_contract_cleanup.md | Yes |
| docs/examples/gl203b/openapi_api_contract_cleanup.json | Yes |
| docs/api_contract_sdk_packaging_decision.md | Yes |
| docs/examples/gl203/api_contract_sdk_packaging_decision.json | Yes |
| docs/persistence_postgres_migration_readiness.md | Yes |
| docs/examples/gl202/persistence_postgres_migration_readiness.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | Yes |
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/db.py | Yes |
| backend/src/config.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/grants.py | Yes |
| backend/src/grant_requests.py | Yes |
| backend/src/challenges.py | Yes |
| backend/src/models.py | Yes |
| backend/src/migrations/* | Yes |
| backend/src/structured_logging.py | Yes |
| backend/src/logging_utils.py | Yes |
| docs/backup_restore_minimum_drill.md | Yes |
| scripts/run-backup-restore-drill.sh | Yes |

---

## Current State Summary

### Achieved (from prior GLs)

- Tenant/workspace isolation baseline: columns, filtering, auth context injection (GL-200A/B/C)
- Production auth/secrets/config hardening: fail-closed startup, placeholder rejection, CORS warning (GL-201)
- Migration runner hardening: failure context, dry-run API, audit backfill immutability fix (GL-202)
- OpenAPI contract cleanup: 36 paths documented, consistent error shapes (GL-203B)
- Internal SDK prototype: examples/sdk_prototype/python/, no official SDK (GL-203C)
- In-process structured logging baseline: logging_utils.py, structured_logging.py, correlation ID (prior GLs)
- Audit hash-chain with dual-mode for legacy and new events
- Basic backup/restore procedures documented for SQLite (GL-127)

### Remaining P0 Blockers (as of GL-205)

- No live PostgreSQL validation **executed** (script added; live run not possible without ephemeral service)
- No automated backup system; no DR runbooks for production
- No production observability stack (no external metrics, alerting, tracing)
- Admin-plane tenant isolation (GL-200D) deferred
- No production deployment hardening (TLS, container, orchestration)
- No production IAM (OAuth/JWT/SSO)

---

## Live PostgreSQL Validation

### Gating Model

The live PostgreSQL validation path is gated by **two explicit environment variables**:

| Variable | Required Value | Purpose |
|----------|----------------|---------|
| `GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES` | `1` | Explicit consent gate |
| `GRANTLAYER_GL205_POSTGRES_DSN` | `postgres://...` | Ephemeral/synthetic DSN |

The script **fails closed** if either variable is absent or the DSN fails safety
checks. It rejects:
- SQLite DSNs
- Empty or whitespace-only DSNs
- DSNs containing placeholder fragments (`localhost`, `127.0.0.1`, `example.com`,
  `placeholder`, `changeme`, etc.)
- DSNs with production-like hostnames (`.prod.`, `-prod.`, `production-`, etc.)

The script **never prints raw DSN or password values** — all diagnostic output
uses a masked form: `scheme://user:***@host:port/db`.

### Validation Plan

The script (`scripts/ops/gl205_live_postgres_validation.py`) validates:

1. Explicit environment gate
2. Explicit DSN present and passes safety checks
3. Connection to ephemeral/synthetic PostgreSQL instance
4. PostgreSQL version is reachable
5. Migrations can apply
6. Migration idempotency (re-run confirms no error)
7. GL-200B tenant_id columns exist on grants and audit_events tables
8. audit_events table and hash-chain columns exist
9. No unsafe legacy audit backfill triggers
10. Synthetic tenant + workspace insert and tenant-scoped CRUD
11. Synthetic audit event with hash-chain integrity
12. Cleanup of synthetic objects
13. Results summary

### Execution Status

**Live PostgreSQL validation: NOT EXECUTED.**

No safe ephemeral PostgreSQL instance was available at the time of GL-205
implementation. The validation script is complete and verified for:
- `--dry-run` mode (configuration validation, no connection)
- `--plan` mode (shows all steps, no mutation)
- Gating logic (refuses without explicit env vars)
- DSN safety checks

**Live PostgreSQL production claim remains NO-GO.**

This is a remaining blocker for production SaaS readiness.

### Modes

```bash
# Validate config only — no connection
python3 scripts/ops/gl205_live_postgres_validation.py --dry-run

# Show validation plan — no mutation
python3 scripts/ops/gl205_live_postgres_validation.py --plan

# Live validation — requires explicit ephemeral instance
GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES=1 \
  GRANTLAYER_GL205_POSTGRES_DSN=postgres://<ephemeral-dsn> \
  python3 scripts/ops/gl205_live_postgres_validation.py --live
```

---

## Backup / Restore Drill

### Baseline Approach

The backup/restore drill (`scripts/ops/gl205_backup_restore_drill.py`) provides:

1. **SQLite drill** — deterministic, fully automated, synthetic data only:
   - Creates ephemeral synthetic SQLite database
   - Applies GrantLayer migrations
   - Inserts synthetic tenant, workspace, grant, and audit event records
   - Verifies audit hash-chain integrity BEFORE backup
   - Copies database to temp backup path
   - Copies backup to temp restore path
   - Verifies schema in restored DB (migrations table)
   - Verifies tenant/workspace data separation in restored DB
   - Verifies audit hash-chain integrity AFTER restore
   - Cleans up temp files (unless `--keep-artifacts` is set)

2. **PostgreSQL drill** — manual checklist only:
   - No automated PostgreSQL backup/restore without an explicit ephemeral service
   - Manual drill checklist provided in `--plan` mode
   - Checklist covers: pre-drill requirements, pg_dump steps, restore steps,
     post-drill cleanup

### Safety Rules

- Uses synthetic/demo data only — no production data required
- Does not log secrets or DB credentials
- Cleans up all temp files by default
- `--keep-artifacts` warns operator about retained synthetic data
- Dry-run and plan modes perform no file operations

### Execution Status

**SQLite backup/restore drill: EXECUTABLE** (use `--sqlite-drill` flag).

**PostgreSQL backup/restore drill: DOCUMENTED ONLY** (manual checklist in `--plan` mode).

```bash
# Dry-run — describe actions only
python3 scripts/ops/gl205_backup_restore_drill.py --dry-run

# Plan — show full steps and PostgreSQL checklist
python3 scripts/ops/gl205_backup_restore_drill.py --plan

# Execute SQLite drill (synthetic data only)
python3 scripts/ops/gl205_backup_restore_drill.py --sqlite-drill
```

### PostgreSQL Backup Remaining Gaps

- No automated PostgreSQL backup integration
- No backup scheduling or retention policy
- No DR runbook for production failover
- No offsite backup storage configured
- PostgreSQL backup/restore production readiness: **LIMITED**
  (manual checklist only; automated drill requires explicit ephemeral service)

---

## Observability Baseline

### Purpose

This section documents the minimum observability expectations for GrantLayer
in Developer Preview / Controlled Preview mode. It does not claim that a
production observability backend exists — none does.

### Required Structured Log Events

The following event types are defined in `backend/src/structured_logging.py`:

| Event Type | When Emitted |
|------------|-------------|
| `api_request` | Every HTTP request (with correlation ID) |
| `api_error` | Any 4xx/5xx response |
| `auth_event` | Authentication success/failure |
| `permission_decision` | Grant allow/deny decision |
| `evidence_verification` | Evidence verification outcome |
| `approval_transition` | Workflow state transition |
| `policy_evaluation` | Policy rule evaluation |
| `persistence_operation` | DB read/write/migration operations |
| `configuration_event` | Startup, config load, fail-closed trigger |
| `operator_action` | Operator management operations |
| `health_check` | Health/liveness probe response |
| `readiness_check` | Readiness probe response |

### Correlation / Request ID Expectations

- Every HTTP request must carry a correlation ID.
- Correlation IDs must propagate through all log events for that request.
- Correlation IDs must use safe characters only: `[A-Za-z0-9_.:-]`.
- Correlation IDs must not exceed 128 characters.
- Correlation IDs must never contain secret values.

### Startup / Config Failure Signals

The following startup/config failure conditions must emit structured log events:

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Placeholder/empty operator token detected | `configuration_event` | `critical` |
| Database connection failure on startup | `configuration_event` | `critical` |
| Migration failure on startup | `configuration_event` | `critical` |
| Insecure CORS origin on startup | `configuration_event` | `warning` |
| Runtime mode is `demo` or `test` (not `production`) | `configuration_event` | `info` |

### Migration Success / Failure Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Migration run start | `persistence_operation` | `info` |
| Migration applied (per version) | `persistence_operation` | `info` |
| Migration idempotency confirmed | `persistence_operation` | `info` |
| Migration failure | `persistence_operation` | `error` |
| Dry-run migration (no mutation) | `persistence_operation` | `info` |

### Live PostgreSQL Validation Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Gate not set (validation skipped) | `configuration_event` | `info` |
| Gate set, DSN validation passed | `configuration_event` | `info` |
| DSN safety validation failed | `configuration_event` | `error` |
| Connection established | `persistence_operation` | `info` |
| Connection failed | `persistence_operation` | `error` |
| Schema verification passed | `persistence_operation` | `info` |
| Schema verification failed | `persistence_operation` | `error` |
| Synthetic data cleanup complete | `persistence_operation` | `info` |

### Backup / Restore Drill Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Drill start | `persistence_operation` | `info` |
| Backup copy created | `persistence_operation` | `info` |
| Backup failed | `persistence_operation` | `error` |
| Restore copy created | `persistence_operation` | `info` |
| Restore failed | `persistence_operation` | `error` |
| Hash-chain verified (before backup) | `persistence_operation` | `info` |
| Hash-chain verified (after restore) | `persistence_operation` | `info` |
| Hash-chain mismatch detected | `persistence_operation` | `error` |
| Temp artifact cleanup complete | `persistence_operation` | `info` |

### Auth Failure Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Missing or invalid token | `auth_event` | `warning` |
| Placeholder/empty token | `auth_event` | `error` |
| Token hash mismatch | `auth_event` | `warning` |
| Operator not found | `auth_event` | `warning` |
| Rate limit exceeded | `auth_event` | `warning` |

### Tenant / Workspace Access Denial Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Cross-tenant access attempt | `permission_decision` | `error` |
| Cross-workspace access attempt | `permission_decision` | `error` |
| Missing tenant context | `permission_decision` | `warning` |
| Workspace not found for tenant | `permission_decision` | `warning` |

### Audit Verification Signals

| Condition | Event Type | Severity |
|-----------|------------|---------|
| Hash-chain verified | `evidence_verification` | `info` |
| Hash-chain gap detected | `evidence_verification` | `error` |
| Audit event tamper detected | `evidence_verification` | `error` |
| Backfill attempt rejected | `evidence_verification` | `error` |

### Secret-Safety Logging Rules

The following values **must never appear in log output**:

- Raw operator tokens
- Raw API keys or API secrets
- Database connection strings (DSNs) with passwords
- Private keys or signing keys
- Evidence payload bodies
- Request bodies containing customer/private data
- Correlation IDs derived from or containing secrets
- Raw customer identifiers or private grant data
- Institutional data fields

Redaction rules enforced by `backend/src/structured_logging.py`:

| Key Substring | Behavior |
|--------------|---------|
| `password` | Always redacted (`[REDACTED]`) |
| `secret` | Always redacted |
| `token` | Always redacted |
| `api_key` | Always redacted |
| `private_key` | Always redacted |
| `authorization` | Always redacted |
| `cookie` | Always redacted |
| `database_url` | Always redacted |
| `db_url` | Always redacted |
| `operator_token` | Always redacted |

### Alert Categories (Minimum)

| Category | Trigger |
|---------|---------|
| Auth failure spike | >N auth failures in sliding window |
| Cross-tenant access attempt | Any single event |
| Hash-chain mismatch | Any single event |
| Migration failure | Any single event |
| Startup config failure | Any single event |
| Database connection failure | Any single event |
| Backup/restore failure | Any single event |

### Minimum Dashboard / Checklist Ideas

- Auth event rate (success vs. failure) over time
- API error rate by status code
- Migration status per deploy
- Audit hash-chain verification status
- Tenant isolation access denial count
- Backup/restore drill last-run status
- Startup config failure count

### Remaining Implementation Gaps

- No external metrics backend (Prometheus, DataDog, etc.)
- No distributed tracing (OpenTelemetry, Jaeger, etc.)
- No alerting integration (PagerDuty, OpsGenie, etc.)
- No log aggregation (ELK, Loki, CloudWatch, etc.)
- No production dashboard exists
- Structured log events are emitted in-process but not shipped externally
- Observability stack production readiness: **NOT READY**

---

## Tenant / Workspace Preservation Assessment

GL-205 does not weaken any GL-200 tenant/workspace isolation guarantees:

- GL-200A: Tenant/workspace data model design — preserved, not modified
- GL-200B: Tenant/workspace isolation implementation baseline — preserved
- GL-200C: Tenant/workspace API/audit regression tests — preserved, all pass
- All GL-200 test suites pass with no new regressions

The synthetic data inserted by GL-205 scripts uses explicit `_SYNTHETIC_TENANT_ID`
and `_SYNTHETIC_WORKSPACE_ID` values. These are cleaned up after each drill.

**Tenant/workspace isolation not overclaimed.**
Admin-plane tenant isolation (GL-200D) remains deferred.

---

## Audit Immutability Preservation Assessment

GL-205 does not modify audit log behavior:

- `backend/src/audit_log.py` is unchanged
- Hash-chain logic is unchanged
- The dual-mode hash payload (tenant_id included only when explicitly set) is preserved
- The genesis hash (64 zeros) convention is preserved
- No backfill triggers or unsafe legacy audit behavior is introduced
- The GL-205 drill scripts use the same hash function as the main codebase for consistency

**Audit immutability preservation: CONFIRMED.**

---

## GL-201 Auth / Secrets / Config Preservation Assessment

GL-205 does not weaken GL-201 auth/secrets/config hardening:

- `backend/src/auth.py` is unchanged
- `backend/src/config.py` is unchanged
- Fail-closed startup behavior is preserved
- Placeholder token rejection is preserved
- CORS security behavior is preserved
- No new secrets, credentials, or tokens are introduced

**GL-201 auth/secrets/config hardening preserved: CONFIRMED.**

---

## GL-203C SDK / Package Boundary Preservation Assessment

GL-205 does not modify SDK or package boundaries:

- No package publishing metadata is added
- No setup.py, pyproject.toml (SDK), or package.json changes
- The internal SDK prototype remains `examples/sdk_prototype/` only
- No official SDK is claimed or published
- GL-203D (Experimental Public SDK) remains deferred

**GL-203C SDK/package boundary preserved: CONFIRMED.**

---

## Production Readiness Impact

GL-205 advances operational readiness in the following ways:

| Area | Before GL-205 | After GL-205 |
|------|--------------|-------------|
| Live PostgreSQL validation | No script | Gated script added; live run not executed |
| Backup/restore drill | Shell runner + unit tests only | Python drill script + SQLite drill executable |
| PostgreSQL backup/restore | Not documented | Manual checklist documented |
| Observability baseline | In-process logging only | Signal catalog and secret-safety rules documented |

### What GL-205 Does NOT Change

- Production SaaS readiness: **NO-GO** (unchanged)
- Real customer/private grant/institutional data: **NO-GO** (unchanged)
- Official SDK/package: **NO-GO** (unchanged)
- Live PostgreSQL production claim: **NO-GO** (unchanged — live run not executed)
- Backup/restore/DR production readiness: **LIMITED** (manual drill only)
- Observability production readiness: **NOT READY** (no external backend)

---

## Remaining Blockers

| ID | Blocker | Severity |
|----|---------|---------|
| RB-001 | No live PostgreSQL validation executed | P0 |
| RB-002 | No automated backup system or DR runbooks | P0 |
| RB-003 | No production observability stack | P0 |
| RB-004 | Admin-plane tenant isolation (GL-200D) deferred | P0 |
| RB-005 | No production deployment hardening (TLS, container) | P0 |
| RB-006 | No production IAM (OAuth/JWT/SSO) | P0 |
| RB-007 | No external metrics or alerting backend | P1 |
| RB-008 | No log aggregation or distributed tracing | P1 |
| RB-009 | PostgreSQL backup/restore automated drill not executed | P1 |

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|-----------|
| R-01 | Live PostgreSQL behavior diverges from SQLite in production | Medium | High | Execute live validation against ephemeral instance before production |
| R-02 | Backup restore fails silently on PostgreSQL | Medium | Critical | Implement automated PostgreSQL drill with explicit verification |
| R-03 | Audit hash-chain becomes invalid after PostgreSQL restore | Low | Critical | Hash-chain verification built into restore drill; test mandatory |
| R-04 | Observability gap masks auth or isolation failures in production | Medium | High | Implement external log aggregation and alerting before production |
| R-05 | Synthetic data inadvertently resembles real customer data | Low | Medium | GL-205 scripts use explicit `gl205-synthetic-*` prefixes; review before live use |
| R-06 | PostgreSQL migration idempotency failure on real schema | Low | High | Step 7 of live validation script explicitly tests idempotency |
| R-07 | Tenant isolation bypass on PostgreSQL due to missing RLS | Medium | Critical | Admin-plane tenant isolation (GL-200D) deferred; must not claim production-complete |

---

## Decision

**GL-205: Operational Readiness Baseline — PROCEED (with documented gaps)**

This decision is **not** a production SaaS go/no-go. It documents the current
state of operational readiness tooling and advances the baseline.

GrantLayer remains **Developer Preview / Controlled Preview with strict
boundaries**. No production SaaS, real customer data, or official SDK claim.

---

## Decision Rationale

GL-205 adds:
1. A gated, safe live PostgreSQL validation script with dry-run and plan modes
2. A deterministic SQLite backup/restore drill script (executable)
3. A PostgreSQL backup/restore manual checklist
4. A comprehensive observability baseline document
5. Tests for all new artifacts and scripts

Live PostgreSQL execution was not possible (no safe ephemeral service available).
This is documented as a remaining blocker (RB-001). The script is ready to run
when a safe ephemeral instance is provided.

The backup/restore drill executes successfully for SQLite (synthetic data only).
PostgreSQL backup/restore remains a manual checklist.

No production SaaS, real customer data, or official SDK claims are made.
All GL-200 through GL-204 constraints are preserved.

---

## Safety Confirmations

- GL-205 is an operational readiness baseline, not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private grant data is used.
- Live PostgreSQL production claim remains no-go — live validation not executed.
- Backup/restore/DR production readiness remains limited — manual checklist only.
- No public publish, GitHub push, or visibility change.
- No frontend/website/design changes.
- No GitHub workflow changes.
- Unrelated untracked website files (website-design/, docs/website_design_workspace_import_*.md) are excluded from GL-205.

---

## Recommended Next Issues

| Issue | Description | Priority |
|-------|-------------|---------|
| GL-205 Merge | Merge GL-205 to internal main if tests pass | Immediate |
| GL-206 | Admin-plane tenant isolation planning (GL-200D) | High |
| GL-206B | Live PostgreSQL validation execution (ephemeral instance required) | High |
| GL-207 | Stale claim correction if any overclaimed items found | High |
| GL-208 | Production observability stack baseline (external backend) | Medium |
| GL-209 | Automated PostgreSQL backup/restore drill | Medium |
| GL-203D | Experimental Public SDK — only after GL-203D projection gate passes | Deferred |
