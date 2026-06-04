# GL-202 — Persistence / PostgreSQL / Migration Readiness

**Issue ID:** GL-202
**Branch:** `gl-202-persistence-postgres-migration-readiness`
**Status:** Internal / Developer Preview

---

## Context

GL-202 follows the merged GL-200A/B/C (tenant/workspace isolation) and GL-201
(production auth/secrets/config hardening) blocks.  It hardens persistence,
PostgreSQL readiness, migration behavior, and migration-operational safety.

**GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries.** GL-202 is a persistence/migration readiness step — not a
production SaaS readiness declaration.

Real customer/private grant/institutional data is not safe to store until later
readiness gates explicitly change that status.  Tenant/workspace isolation is not
overclaimed as production-complete.

Security-sensitive reports route to GitHub Security Advisories.  No exploit
details are included here.  No real secrets are included.

---

## Scope

- Review and verify migration runner behavior.
- Close concrete migration runner gaps (error context, dry-run API).
- Fix PostgreSQL `executescript` comment-handling bug.
- Fix audit_events backfill incompatibility with immutability trigger.
- Verify GL-200B tenant/workspace migration 0010 idempotency.
- Verify audit hash-chain integrity across migration paths.
- Document remaining gaps, indexes, and rollback posture.
- Add GL-202 regression test suite.

## Non-Goals

- Production SaaS readiness declaration.
- Public GitHub push.
- Broad ORM / persistence rewrite.
- Real backup/restore against production-like data.
- New auth provider or broad CORS redesign.
- API redesign.
- Frontend / website / design changes.
- Public marketing claims.

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| backend/src/db.py | Yes |
| backend/src/config.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/migrations/* | Yes (all 10 files) |
| backend/tests/* (selected) | Yes |
| README.md, SECURITY.md, AGENTS.md | Yes |

---

## Current Persistence Summary

GrantLayer uses a file-based migration runner on top of SQLite (default) and
PostgreSQL (configured via `GRANTLAYER_DATABASE_URL`).  The runner is minimal
and deliberate: no ORM, no external migration framework, SQL executed directly
via `_ConnectionWrapper` which translates `?` placeholders to `%s` for
PostgreSQL.

### Migration Inventory (10 migrations)

| Version | Content |
|---|---|
| 0001_gl032_baseline | Full GL-032 schema (grants, audit_events, challenges, operators, grant_requests, grant_executions, indexes) |
| 0002_gl036_evidence_persistence | evidence_archives, evidence_hashes tables |
| 0003_gl036_r2_evidence_verification | Verification tracking columns on evidence_archives |
| 0004_gl037a_provenance_events | provenance_events table |
| 0005_gl102_audit_log_immutability | SQLite triggers preventing UPDATE/DELETE on audit_events |
| 0006_gl103_audit_hash_chain | row_hash, prev_hash columns on audit_events |
| 0007_gl107_operator_token_lookup | token_lookup_hash column and index on operators |
| 0008_gl108_postgres_audit_immutability | PostgreSQL triggers preventing UPDATE/DELETE on audit_events |
| 0009_gl119_operator_token_expiry_rotation | expires_at, rotated_at on operators |
| 0010_gl200b_tenant_workspace_isolation | tenant_id, workspace_id columns and indexes on all business tables |

---

## Migration Runner Assessment

### Ordering — VERIFIED SAFE
`_discovery()` uses `sorted(os.listdir(...))` with numeric prefixed filenames.
Lexicographic sort of `000N_*` names equals numeric order.  Repeated calls
return the same list.

### Idempotency — VERIFIED SAFE
All migrations use existence guards: `IF NOT EXISTS` in DDL, `_column_exists`,
`_table_exists`, `_index_exists` helpers.  Running a migration twice on an
already-migrated DB is a no-op.

### Failure Safety — HARDENED (GL-202)
Previously, if `apply_fn(conn)` raised an exception, the error propagated
without indicating which migration failed.  GL-202 wraps the call:

```python
try:
    apply_fn(conn)
except Exception as exc:
    raise RuntimeError(
        f"Migration {version} failed during apply: {exc}"
    ) from exc
```

Failed migrations are NOT marked applied (the `_mark_applied` call comes after
`apply_fn` returns), so the runner is restartable.

### Dry-Run / Inspection — ADDED (GL-202)
`list_pending_migrations(conn)` returns `(version, filepath)` pairs for
unapplied migrations.  Safe to call without modifying the database.

### Legacy DB Detection — VERIFIED (DOCUMENTED LIMITATION)
When `schema_migrations` is absent but `grants` table exists, the runner
validates the GL-032 baseline and marks **all** migrations as applied.  This is
intentional for developer environments where the full schema predates the
migration runner.  Any DB encountering this path in post-GL-202 deployments
should be treated as a special case requiring manual review.

---

## SQLite Readiness Assessment

- WAL journal mode is enabled on every connection (`PRAGMA journal_mode=WAL`).
- Foreign keys are enabled (`PRAGMA foreign_keys=ON`).
- All migrations use SQLite-compatible DDL.
- Immutability triggers are SQLite-native (`CREATE TRIGGER IF NOT EXISTS`).
- Audit hash-chain verification is read-only and safe.
- Fresh DB initialization applies all 10 migrations in deterministic order.
- All required columns and indexes are present post-migration.

**Assessment: READY for controlled SQLite usage within Developer Preview.**

---

## PostgreSQL Readiness Assessment

### What Works

- Connection factory supports `postgres://` and `postgresql://` URLs.
- `_ConnectionWrapper` translates `?` placeholders to `%s` for PostgreSQL.
- `_table_exists`, `_column_exists`, `_index_exists` have PostgreSQL branches.
- Migration 0008 adds PostgreSQL audit immutability triggers.
- Connection pool (`SimpleConnectionPool`) with bounded retry is in place.
- Lazy psycopg2 import with clear install hint.

### Gap Found and Fixed (GL-202): `executescript` Comment Handling

**Before GL-202:** `_ConnectionWrapper.executescript` for PostgreSQL split SQL
on `;` and skipped statements where the stripped text started with `--`.
Migrations like 0001 and 0002 have `-- Comment\nCREATE TABLE ...` patterns.
These statements would be silently skipped, leaving the schema incomplete.

**Fix:** Strip leading line comments from each `;`-delimited chunk before
checking whether there is actual SQL content, then execute the SQL portion.

### Remaining PostgreSQL Gaps (Deferred)

- **No live PostgreSQL test infrastructure.** Static/dry-run checks cover
  compatibility patterns; full live execution requires a PostgreSQL instance
  not available in this environment.  Documented in tests as a known limitation.
- **Connection pool not exercised.** `SimpleConnectionPool` is code-complete
  but not tested with real connections.  Manual validation required before
  first PostgreSQL deployment.
- **pg_stat_activity privilege.** Health probe uses `pg_stat_activity`; this
  requires at least `pg_monitor` role in hardened PostgreSQL configurations.

**Assessment: PostgreSQL code paths are substantially hardened but NOT validated
end-to-end without a live instance.  Not production-ready for PostgreSQL without
live integration testing.**

---

## GL-200 Tenant/Workspace Schema Assessment

### Fresh DB

All business tables (grants, grant_requests, challenges, grant_executions,
evidence_archives) get `tenant_id TEXT NOT NULL DEFAULT 'demo'`.  Operators get
`tenant_id TEXT NOT NULL DEFAULT 'demo'`.  audit_events gets `tenant_id TEXT
DEFAULT NULL`.  All tables get `workspace_id TEXT DEFAULT NULL`.  audit_events
gets `scope TEXT DEFAULT NULL`.

Performance indexes: `idx_<table>_tenant_id` on each scoped table,
`idx_grants_tenant_subject` composite index.

### Bug Found and Fixed (GL-202): Audit Events Backfill

**Before GL-202:** Migration 0010 attempted to `UPDATE audit_events SET
tenant_id = 'demo' WHERE tenant_id IS NULL` for existing rows.  This is
incompatible with the audit immutability trigger added by migration 0005:

- Migration 0005 creates `BEFORE UPDATE` and `BEFORE DELETE` triggers that
  raise an error on any modification to `audit_events`.
- On an existing DB with audit events, migration 0010's UPDATE would trigger
  the immutability guard, causing migration 0010 to fail.
- Re-running migration 0010 after partial execution would fail again on the
  same UPDATE (idempotency guard skips the ALTER TABLE but still tries the
  UPDATE).

**Additionally:** backfilling chain-verified audit events (with `row_hash IS
NOT NULL`) to `tenant_id = 'demo'` would corrupt hash-chain verification,
because `_hash_payload` includes `tenant_id` only when non-NULL.  The stored
row_hash was computed without `tenant_id`; post-backfill recomputation would
include it, causing a mismatch.

**Fix:** Remove the backfill UPDATE from the nullable path entirely.
- Pre-migration audit events keep `tenant_id = NULL`.
- NULL tenant_id is the intended fail-closed behavior: legacy events are not
  associated with any specific tenant and do not appear in per-tenant filtered
  queries.
- New audit events written after migration have `tenant_id` set explicitly by
  `append_event`.

### Legacy Row Behavior

- Business table rows inserted before explicit tenant context use `tenant_id =
  'demo'` (NOT NULL column default).
- Audit events inserted without explicit tenant_id keep `tenant_id = NULL`.
- `list_events(tenant_id='t1')` returns only rows with `tenant_id = 't1'`.
  Legacy NULL-tenant audit events are isolated by default.

---

## Audit Immutability and Migration Assessment

- SQLite immutability triggers (migration 0005) and PostgreSQL triggers
  (migration 0008) protect audit_events from UPDATE and DELETE.
- Triggers are created before migration 0010 adds tenant_id columns.
- After GL-202 fix, migration 0010 does not attempt UPDATE on audit_events.
- Hash-chain verification (`verify_audit_hash_chain`) is read-only; it reads
  audit events in ascending timestamp+rowid order and recomputes row_hash.
- Pre-chain events (row_hash IS NULL) are skipped during verification.
- Post-migration events with tenant_id verify correctly because `_hash_payload`
  conditionally includes `tenant_id` only when non-None, matching the format
  used at write time.

**Assessment: Audit immutability is intact.  Pre-migration and post-migration
audit events verify correctly.  Hash-chain is not corrupted by GL-202.**

---

## Constraints / Indexes Assessment

### Existing Indexes (Post-Migration)

| Index | Table | Purpose |
|---|---|---|
| idx_grants_tenant_id | grants | Per-tenant grant lookup |
| idx_grants_tenant_subject | grants | Tenant + subject composite |
| idx_audit_events_tenant_id | audit_events | Per-tenant audit listing |
| idx_grant_requests_tenant_id | grant_requests | Per-tenant request lookup |
| idx_challenges_tenant_id | challenges | Per-tenant challenge lookup |
| idx_grant_executions_tenant_id | grant_executions | Per-tenant execution lookup |
| idx_evidence_archives_tenant_id | evidence_archives | Per-tenant archive lookup |
| idx_operators_token_lookup_hash | operators | O(1) token narrowing |
| idx_grant_executions_grant_id | grant_executions | Join index |
| idx_grant_executions_executed_at | grant_executions | Time-range scan |

### Recommended Future Indexes (Deferred — Not Added in GL-202)

The following indexes would improve production query patterns but are deferred
to a dedicated controlled migration issue to avoid schema risk:

- `idx_audit_events_timestamp` — audit event time-range queries.
- `idx_audit_events_subject_id` — per-subject audit history.
- `idx_grants_subject_id` — per-subject grant lookup.
- `idx_operators_active` — active operator filter.

**Assessment: Current index set is sufficient for Developer Preview scale.
Production-grade index additions are a separate, lower-risk migration issue.**

---

## Backfill / Rollback / Dry-Run Strategy

### Forward Migration

Migrations run in deterministic numeric order.  Each migration is idempotent.
A fresh DB applies all 10 migrations.  An upgraded DB applies only pending
migrations.  The `list_pending_migrations(conn)` helper provides dry-run
visibility before `run_migrations(conn)` is called.

### Backfill Assumptions

- Business tables: `tenant_id = 'demo'` is the NOT NULL column default.
  Pre-existing rows from before the column existed receive this default
  automatically via SQLite's ALTER TABLE default behavior.
- Audit events: `tenant_id = NULL` for pre-migration rows.  No backfill is
  performed (GL-202 fix removes the UPDATE that was incompatible with the
  immutability trigger).
- Operators: `tenant_id = 'demo'` via NOT NULL default.

### Rollback Limitations

- Schema migrations (ALTER TABLE ADD COLUMN) are not reversible in SQLite
  without rebuilding the table.
- There is no automated rollback mechanism.  Manual DB restoration from backup
  is the only rollback path for schema changes.
- For production deployments, a pre-migration database snapshot is required
  before running `init_db()`.

### Dry-Run / Manual Verification

```python
from src.db import get_conn
from src.migrations import list_pending_migrations

conn = get_conn()
pending = list_pending_migrations(conn)
for version, filepath in pending:
    print(f"PENDING: {version} ({filepath})")
conn.close()
```

### Production Safety Gates (Before Real Data)

1. Run `list_pending_migrations` and confirm expected versions.
2. Take a full DB snapshot.
3. Run `init_db()` in a staging environment with production-like data shape.
4. Verify `list_pending_migrations` returns empty.
5. Run audit chain verification: `al.build_audit_chain_verification_report()`.
6. Verify health endpoint returns `dbConnected=true, dbWritable=true`.
7. Run the GL-202 test suite against the upgraded DB.
8. Only then promote to production.

---

## Implemented Changes

| File | Change |
|---|---|
| `backend/src/db.py` | Fix `executescript` PostgreSQL path to strip leading line comments before executing SQL chunks |
| `backend/src/migrations/runner.py` | Wrap `apply_fn(conn)` in error context; add `list_pending_migrations(conn)` |
| `backend/src/migrations/__init__.py` | Export `list_pending_migrations` |
| `backend/src/migrations/0010_gl200b_tenant_workspace_isolation.py` | Remove backfill UPDATE from nullable (audit_events) path; add explanatory comment |
| `backend/tests/test_gl202_persistence_postgres_migration_readiness.py` | New GL-202 test suite |
| `docs/persistence_postgres_migration_readiness.md` | This document |
| `docs/examples/gl202/persistence_postgres_migration_readiness.json` | JSON artifact |

---

## Tests Added

`backend/tests/test_gl202_persistence_postgres_migration_readiness.py`

- Migration ordering is deterministic.
- All migrations expose `apply(conn)`.
- Runner raises with version context on missing apply function.
- Runner raises with version context on apply failure.
- Failed migration not marked applied.
- Fresh DB has all required tables.
- Fresh DB has GL-200B tenant_id/workspace_id columns.
- All tenant lookup indexes present.
- Repeated migration 0010 application is idempotent.
- Legacy GL-032 DB detection marks baseline, all migrations applied.
- Legacy rows backfilled to 'demo' for business tables.
- Audit events with NULL tenant_id not backfilled (fail-closed).
- Audit hash chain empty DB verifies valid.
- Pre-chain events skipped during verification.
- Post-migration tenant-aware events verify correctly.
- Mixed pre-chain and chain events verify correctly.
- Tampered event fails verification.
- Audit immutability trigger blocks UPDATE.
- Chain verification report structure is correct.
- `list_pending_migrations` returns empty after init_db.
- `list_pending_migrations` returns pending before init_db.
- PostgreSQL executescript comment stripping (mock test).
- Placeholder translation for migration SQL.
- Migration SQL uses IF NOT EXISTS / existence guards.
- DB URL password not in connection error messages.
- GL-201 production config fail-closed preserved.
- Documentation artifacts present and structurally valid.

---

## Remaining Gaps

| Gap | Risk | Resolution |
|---|---|---|
| No live PostgreSQL test infrastructure | Medium | Deferred; requires PostgreSQL instance not available locally |
| `pg_stat_activity` health probe privilege | Low | Document; use `pg_monitor` role in hardened PostgreSQL |
| Legacy DB detection marks all migrations applied without running them | Low | Documented; only applies to developer environments pre-migration-runner |
| Production-grade indexes (audit timestamp, subject_id, etc.) | Low | Deferred to dedicated migration issue |
| Connection pool live validation | Medium | Requires live PostgreSQL; deferred |
| DR / backup-restore drill | Medium | Separate GL-203 scope |

---

## Production Readiness Impact

**GL-202 hardens the migration path for Developer Preview but does NOT declare
production SaaS readiness.**

- Migration failure context is improved (specific error messages).
- PostgreSQL executescript SQL execution is now correct for commented migrations.
- Audit events are not backfilled in ways that violate hash-chain integrity or
  trigger the immutability guard.
- Dry-run inspection is available via `list_pending_migrations`.
- The GL-201 auth/secrets/config hardening is fully preserved.
- The GL-200 tenant/workspace isolation is preserved and not weakened.

---

## Decision

**Proceed with GL-202.  Persistence and migration readiness is hardened for
Developer Preview.  PostgreSQL remains not live-validated; this is documented.**

### Safety Confirmations

- No production SaaS readiness claim.
- Tenant/workspace isolation not overclaimed as production-complete.
- No real customer / private grant / institutional data readiness claimed.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details included.
- No real secrets included.
- GL-201 auth/secrets/config hardening preserved.
- GL-200 tenant/workspace behavior preserved.
- Audit immutability not weakened.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No public publish or visibility change.

---

## Recommended Next Issues

- **GL-202 Merge** — merge `gl-202-persistence-postgres-migration-readiness` to internal main.
- **GL-203** — API Contract / SDK Packaging Decision after GL-202 is merged.
