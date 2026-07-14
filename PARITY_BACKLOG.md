# PostgreSQL Full-Suite Parity Backlog (GL-351)

**Status:** open · **Opened:** 2026-06-23 · **Tracking:** no external tracker (repo-internal)

## Landed 2026-07-14 — migration-system drift closed

Three fixes reconciled the two migration systems and made the deployment
contract fail-loud instead of silently divergent:

- **Audit-write atomicity** (`af831d7`) — mutation and its `append_event` now
  share the request session, so a failed audit write rolls back the mutation
  instead of leaving a Cardano-anchored gap.
- **Runner fail-loud guard** (`fd93265`) — the runner's legacy-baseline shortcut
  now raises `RuntimeError` instead of marking every migration applied without
  executing it when it finds an Alembic-provisioned database. See
  DEPLOYMENT.md §11 for the operator remedy.
- **Migration parity + runner freeze** (`32f0e5e`) — one Alembic catch-up
  revision (`d4e5f6a7b8c9`) brings Alembic to full parity with the frozen
  runner (tables, indexes, 19 server defaults, `audit_events.seq`, immutability
  triggers); the file-based runner is frozen dev/test-only; `init_db()` defers
  to Alembic when it owns the schema; PostgreSQL CI now provisions with
  `alembic upgrade head`; and `backend/tests/test_migration_parity.py` fails CI
  if a runner migration ever adds an object Alembic lacks.

The two PostgreSQL runtime parity bugs enumerated below (sync-engine URL
`ArgumentError`; `workspace_id` `NOT NULL` enforced only on PostgreSQL) are
separate and remain open.

## Verified closed 2026-07-14 — audit_events seq + immutability triggers on Alembic PG

**Item:** a pure Alembic-provisioned PostgreSQL database was reported to be
missing `audit_events.seq` and the `no_update`/`no_delete` immutability triggers,
leaving the production audit log without DB-level append-only protection and
breaking `verify_audit_hash_chain` / cursor pagination.

**Status: RESOLVED by revision `d4e5f6a7b8c9` (commit `32f0e5e`).** Confirmed
empirically on throwaway PostgreSQL 16 containers: at the pre-catch-up revision
`c3d4e5f6a7b8` the drift is real (`seq` absent, zero triggers); at head
(`d4e5f6a7b8c9`, `alembic upgrade head`) `audit_events` has `seq` (+ backing
sequence + index) and both immutability triggers, and functionally UPDATE and
DELETE are rejected by the DB, `verify_audit_hash_chain` validates, and cursor
pagination over `seq` pages correctly. A permanent PG-only regression test
(`backend/tests/test_migration_parity.py::TestMigrationParityPostgresFunctional`,
gated on `GRANTLAYER_PARITY_PG_DSN`) pins these five guarantees and fails loudly
if a future revision regresses any of them. No new migration was required; a
production DB provisioned before this revision only needs `alembic upgrade head`.

Known/intentional: on a fresh DB the first inserted row gets `seq = 2` (the
catch-up runs `setval(sequence, MAX(seq) + 1)` on an empty table). This is not
fixed — the seq contract is strict monotonicity + uniqueness, which holds; the
absolute starting value is irrelevant to ordering, verification, and pagination.

## Summary

The PostgreSQL 16 Full Suite CI job had never run to completion before. Clearing
the prerequisite blockers (missing runtime deps `arq`/`audit`/`asyncpg`,
optional-dependency test conditionals, and finally per-test PostgreSQL isolation
via the autouse TRUNCATE fixture) let the suite run far enough to surface a
backlog of genuine PG/SQLite parity bugs that SQLite alone never exposed.

The SQLite Unit Tests job (4,697 tests, green) remains the merge gate. The PG
Full Suite was made non-blocking (`continue-on-error: true`) in commit `6aa52ad`
so the honest v2.1.0 release can ship decoupled from this backlog, while the job
keeps running and reporting.

## Parity bugs identified so far

1. **URL `ArgumentError` on the sync engine** in the evidence-export path — PG-only failure.
2. **Raw `INSERT INTO grants` omitting `workspace_id` -> `NotNullViolation`** on PG.
   Migration 0012 applies `NOT NULL` only on PostgreSQL; SQLite silently skips
   `ALTER COLUMN ... SET NOT NULL`, so the same insert succeeds on SQLite and the
   divergence is invisible there.
3. **Likely more** — the suite runs with `-x` today, so it stops at the first
   failure. The full extent is unknown until it runs to completion without `-x`.

## Plan (Option A — triage)

1. Run the full suite against the local PG container to completion, WITHOUT `-x`.
2. Enumerate every PG-only failure.
3. Categorize each as either:
   - (a) a real schema/parity/code bug that affects production, or
   - (b) a test-only SQLite-ism (test relies on SQLite-specific behavior).
4. Fix the real bugs in a batch; adjust the test-only cases.
5. Once the divergences are triaged and fixed, restore the PG Full Suite to a
   blocking merge gate.

## Related

- Non-blocking CI change: commit `6aa52ad` (`.github/workflows/postgres-ci.yml`)
- Isolation prerequisite: commit `a8826b2` (TRUNCATE seed-row restore) + `9230687` (autouse TRUNCATE fixture)
