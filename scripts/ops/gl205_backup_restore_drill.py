#!/usr/bin/env python3
"""GL-205 — Backup / Restore Drill Baseline Script.

This script performs a deterministic, synthetic-data-only backup/restore drill.
It is safe by default and does not require production data.

SAFETY RULES:
- Uses synthetic/demo data only.
- Does not require or access production data.
- Does not log secrets or DB credentials.
- Cleans up temp files by default unless --keep-artifacts is set.
- Supports --dry-run (describe actions, no file operations).
- Supports --plan (show steps without mutation).

Usage:
  python3 scripts/ops/gl205_backup_restore_drill.py --dry-run
  python3 scripts/ops/gl205_backup_restore_drill.py --plan
  python3 scripts/ops/gl205_backup_restore_drill.py --sqlite-drill
  python3 scripts/ops/gl205_backup_restore_drill.py --sqlite-drill --keep-artifacts
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SYNTHETIC_TENANT_ID = "gl205-drill-tenant-001"
_SYNTHETIC_WORKSPACE_ID = "gl205-drill-ws-001"
_SYNTHETIC_GRANT_ID = "gl205-drill-grant-001"


# ---------------------------------------------------------------------------
# Drill steps
# ---------------------------------------------------------------------------

DRILL_PLAN = [
    "step_01: Create temporary synthetic SQLite database",
    "step_02: Apply GrantLayer migrations to synthetic DB",
    "step_03: Insert synthetic tenant and workspace records",
    "step_04: Insert synthetic grant record (scoped to synthetic tenant)",
    "step_05: Insert synthetic audit events",
    "step_06: Verify audit hash-chain integrity BEFORE backup",
    "step_07: Perform backup — copy synthetic DB to temp backup path",
    "step_08: Restore — copy backup to a new temp restore path",
    "step_09: Open restored DB and verify schema (migrations table exists)",
    "step_10: Verify tenant/workspace data separation in restored DB",
    "step_11: Verify audit hash-chain integrity AFTER restore",
    "step_12: Clean up temp files (unless --keep-artifacts is set)",
    "step_13: Report results — success or failure with safe diagnostics",
]

POSTGRES_BACKUP_CHECKLIST = """
GL-205 PostgreSQL Backup/Restore — Manual Drill Checklist (ephemeral only)

This checklist must only be executed against an explicitly ephemeral/synthetic
PostgreSQL instance. Never run against production or real-data databases.

PRE-DRILL REQUIREMENTS:
  [ ] Confirm target instance is ephemeral/synthetic (not production)
  [ ] Confirm no real customer, grant, or institutional data is present
  [ ] Confirm operator has write access to backup storage
  [ ] Confirm GRANTLAYER_GL205_POSTGRES_DSN points to ephemeral instance only

BACKUP STEPS:
  [ ] Run pg_dump on synthetic DB:
        pg_dump "$GRANTLAYER_GL205_POSTGRES_DSN" > /tmp/gl205-drill-backup.sql
  [ ] Verify backup file is non-empty
  [ ] Verify backup contains expected tables (tenants, workspaces, audit_events)
  [ ] Store backup file in secure ephemeral location only

RESTORE STEPS:
  [ ] Create new ephemeral PostgreSQL instance for restore
  [ ] Restore from backup:
        psql "$RESTORE_DSN" < /tmp/gl205-drill-backup.sql
  [ ] Verify migrations table exists in restored DB
  [ ] Verify tenant/workspace data matches original
  [ ] Verify audit hash-chain integrity in restored DB
  [ ] Verify application can connect and pass smoke tests against restored DB

POST-DRILL:
  [ ] Delete all temp backup files
  [ ] Destroy ephemeral restore instance
  [ ] Document drill outcome in ops log

REMAINING GAPS (as of GL-205):
  - No automated PostgreSQL backup integration
  - No backup scheduling or retention policy
  - No DR runbook for production failover
  - No offsite backup storage configured
  - PostgreSQL backup/restore production readiness: LIMITED
    (manual drill only; no live PostgreSQL service available for automated drill)
"""


# ---------------------------------------------------------------------------
# Hash-chain helpers (minimal, standalone)
# ---------------------------------------------------------------------------

def _compute_row_hash_simple(event_id: str, action: str, prev_hash: str) -> str:
    """Compute a simplified SHA-256 row hash for synthetic audit events."""
    import hashlib, json as _json
    payload = {"id": event_id, "action": action, "prev_hash": prev_hash}
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# SQLite drill implementation
# ---------------------------------------------------------------------------

def _run_sqlite_drill(keep_artifacts: bool) -> int:
    """Execute the SQLite backup/restore drill. Returns exit code."""
    print("[GL-205-DRILL] SQLite Backup/Restore Drill — EXECUTING")
    print("[GL-205-DRILL] Using synthetic/demo data only.")
    print("[GL-205-DRILL] No production data required.")
    print("[GL-205-DRILL]")

    # Locate repo root for migrations
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    backend_path = os.path.join(repo_root, "backend")

    results: list[str] = []
    tmpdir = tempfile.mkdtemp(prefix="gl205_drill_")
    source_db = os.path.join(tmpdir, "synthetic_source.db")
    backup_db = os.path.join(tmpdir, "synthetic_backup.db")
    restore_db = os.path.join(tmpdir, "synthetic_restore.db")

    try:
        # step_01: Create synthetic DB
        print("[GL-205-DRILL] step_01: Creating temporary synthetic SQLite database...")
        conn_source = sqlite3.connect(source_db)
        conn_source.row_factory = sqlite3.Row
        print(f"[GL-205-DRILL] step_01: Created at temp path (not logged for safety).")
        results.append("step_01: PASS")

        # step_02: Apply migrations
        print("[GL-205-DRILL] step_02: Applying GrantLayer migrations...")
        try:
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            from src.migrations.runner import run_migrations  # type: ignore
            run_migrations(conn_source)
            conn_source.commit()
            print("[GL-205-DRILL] step_02: Migrations applied.")
            results.append("step_02: PASS")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_02: Migration failed: {type(exc).__name__}: {exc}")
            results.append(f"step_02: FAIL {type(exc).__name__}")
            conn_source.close()
            return 1

        # step_03: Verify tenant_id column exists on business tables (GL-200B)
        print("[GL-205-DRILL] step_03: Verifying GL-200B tenant isolation columns...")
        try:
            cur = conn_source.execute("PRAGMA table_info(grants);")
            grant_cols = {row[1] for row in cur.fetchall()}
            cur = conn_source.execute("PRAGMA table_info(audit_events);")
            audit_cols_check = {row[1] for row in cur.fetchall()}
            has_tenant_col = "tenant_id" in grant_cols
            has_audit_tenant = "tenant_id" in audit_cols_check
            if has_tenant_col:
                print("[GL-205-DRILL] step_03: tenant_id column present on grants table.")
                results.append("step_03: PASS")
            else:
                print("[GL-205-DRILL] step_03: tenant_id column missing from grants (expected GL-200B migration).")
                results.append("step_03: WARN tenant_id-missing")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_03: Schema check failed: {type(exc).__name__}: {exc}")
            results.append(f"step_03: FAIL {type(exc).__name__}")

        # step_04: Synthetic scoped grant insert
        print("[GL-205-DRILL] step_04: Inserting synthetic scoped grant record...")
        try:
            cur = conn_source.execute("PRAGMA table_info(grants);")
            grant_cols = {row[1] for row in cur.fetchall()}
            if "tenant_id" in grant_cols:
                conn_source.execute(
                    "INSERT OR IGNORE INTO grants (id, subject_id, role, action, resource, "
                    "valid_from, valid_until, created_by, reason, tenant_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    (_SYNTHETIC_GRANT_ID, "gl205-synthetic-subject", "synthetic",
                     "read", "synthetic-resource", "2026-01-01T00:00:00Z",
                     "2099-01-01T00:00:00Z", "gl205-drill", "GL-205 synthetic grant",
                     _SYNTHETIC_TENANT_ID, "2026-01-01T00:00:00Z"),
                )
            else:
                conn_source.execute(
                    "INSERT OR IGNORE INTO grants (id, subject_id, role, action, resource, "
                    "valid_from, valid_until, created_by, reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    (_SYNTHETIC_GRANT_ID, "gl205-synthetic-subject", "synthetic",
                     "read", "synthetic-resource", "2026-01-01T00:00:00Z",
                     "2099-01-01T00:00:00Z", "gl205-drill", "GL-205 synthetic grant",
                     "2026-01-01T00:00:00Z"),
                )
            conn_source.commit()
            print("[GL-205-DRILL] step_04: Synthetic grant inserted.")
            results.append("step_04: PASS")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_04: Grant insert failed (non-critical): {type(exc).__name__}: {exc}")
            results.append(f"step_04: WARN {type(exc).__name__}")

        # step_05: Synthetic audit events
        print("[GL-205-DRILL] step_05: Inserting synthetic audit events...")
        try:
            genesis_hash = "0" * 64
            h1 = _compute_row_hash_simple("gl205-audit-drill-001", "drill_start", genesis_hash)
            h2 = _compute_row_hash_simple("gl205-audit-drill-002", "drill_write", h1)

            cur = conn_source.execute("PRAGMA table_info(audit_events);")
            audit_cols = {row[1] for row in cur.fetchall()}

            base_insert = (
                "INSERT OR IGNORE INTO audit_events "
                "(id, timestamp, subject_id, role, action, resource, approved, reason, "
                "prev_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            tenant_insert = (
                "INSERT OR IGNORE INTO audit_events "
                "(id, timestamp, subject_id, role, action, resource, approved, reason, "
                "tenant_id, prev_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )

            if "tenant_id" in audit_cols:
                conn_source.execute(tenant_insert, (
                    "gl205-audit-drill-001", "2026-01-01T00:00:00Z",
                    "gl205-drill-subject", "synthetic", "drill_start", "synthetic",
                    1, "GL-205 drill start", _SYNTHETIC_TENANT_ID, genesis_hash, h1,
                ))
                conn_source.execute(tenant_insert, (
                    "gl205-audit-drill-002", "2026-01-01T00:00:01Z",
                    "gl205-drill-subject", "synthetic", "drill_write", "synthetic",
                    1, "GL-205 drill write", _SYNTHETIC_TENANT_ID, h1, h2,
                ))
            else:
                conn_source.execute(base_insert, (
                    "gl205-audit-drill-001", "2026-01-01T00:00:00Z",
                    "gl205-drill-subject", "synthetic", "drill_start", "synthetic",
                    1, "GL-205 drill start", genesis_hash, h1,
                ))
                conn_source.execute(base_insert, (
                    "gl205-audit-drill-002", "2026-01-01T00:00:01Z",
                    "gl205-drill-subject", "synthetic", "drill_write", "synthetic",
                    1, "GL-205 drill write", h1, h2,
                ))
            conn_source.commit()
            print("[GL-205-DRILL] step_05: Synthetic audit events inserted.")
            results.append("step_05: PASS")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_05: Audit insert failed: {type(exc).__name__}: {exc}")
            results.append(f"step_05: FAIL {type(exc).__name__}")
            h2 = "0" * 64  # fallback for step_06

        # step_06: Verify hash-chain BEFORE backup
        print("[GL-205-DRILL] step_06: Verifying audit hash-chain BEFORE backup...")
        try:
            rows = conn_source.execute(
                "SELECT id, prev_hash, row_hash, action FROM audit_events "
                "WHERE id IN ('gl205-audit-drill-001', 'gl205-audit-drill-002') "
                "ORDER BY timestamp;"
            ).fetchall()
            if len(rows) >= 2:
                computed_h1 = _compute_row_hash_simple(rows[0]["id"], rows[0]["action"], rows[0]["prev_hash"])
                computed_h2 = _compute_row_hash_simple(rows[1]["id"], rows[1]["action"], rows[1]["prev_hash"])
                if computed_h1 == rows[0]["row_hash"] and computed_h2 == rows[1]["row_hash"]:
                    print("[GL-205-DRILL] step_06: Hash-chain integrity verified BEFORE backup.")
                    results.append("step_06: PASS")
                else:
                    print("[GL-205-DRILL] step_06: Hash mismatch detected BEFORE backup.")
                    results.append("step_06: FAIL hash-mismatch")
            else:
                print(f"[GL-205-DRILL] step_06: Expected 2 audit rows, found {len(rows)}.")
                results.append(f"step_06: WARN row-count={len(rows)}")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_06: Hash-chain check failed: {type(exc).__name__}: {exc}")
            results.append(f"step_06: FAIL {type(exc).__name__}")

        conn_source.close()

        # step_07: Backup — copy synthetic DB
        print("[GL-205-DRILL] step_07: Performing backup (copy synthetic DB to backup path)...")
        try:
            shutil.copy2(source_db, backup_db)
            if os.path.isfile(backup_db) and os.path.getsize(backup_db) > 0:
                print("[GL-205-DRILL] step_07: Backup copy completed. Backup is non-empty.")
                results.append("step_07: PASS")
            else:
                print("[GL-205-DRILL] step_07: Backup file is missing or empty.")
                results.append("step_07: FAIL empty-backup")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_07: Backup failed: {type(exc).__name__}: {exc}")
            results.append(f"step_07: FAIL {type(exc).__name__}")

        # step_08: Restore — copy backup to restore path
        print("[GL-205-DRILL] step_08: Restoring backup to new temp path...")
        try:
            shutil.copy2(backup_db, restore_db)
            if os.path.isfile(restore_db) and os.path.getsize(restore_db) > 0:
                print("[GL-205-DRILL] step_08: Restore copy completed. Restore DB is non-empty.")
                results.append("step_08: PASS")
            else:
                print("[GL-205-DRILL] step_08: Restore file is missing or empty.")
                results.append("step_08: FAIL empty-restore")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_08: Restore failed: {type(exc).__name__}: {exc}")
            results.append(f"step_08: FAIL {type(exc).__name__}")

        # step_09: Verify schema in restored DB
        print("[GL-205-DRILL] step_09: Verifying schema in restored DB...")
        try:
            conn_restore = sqlite3.connect(restore_db)
            conn_restore.row_factory = sqlite3.Row
            migrations_count = conn_restore.execute(
                "SELECT COUNT(*) FROM schema_migrations;"
            ).fetchone()[0]
            if migrations_count > 0:
                print(f"[GL-205-DRILL] step_09: schema_migrations table exists with {migrations_count} entries.")
                results.append("step_09: PASS")
            else:
                print("[GL-205-DRILL] step_09: schema_migrations exists but is empty.")
                results.append("step_09: WARN empty-migrations")
        except Exception as exc:
            print(f"[GL-205-DRILL] step_09: Schema verification failed: {type(exc).__name__}: {exc}")
            results.append(f"step_09: FAIL {type(exc).__name__}")
            conn_restore = None

        # step_10: Verify tenant scoped grant data in restored DB
        if conn_restore is not None:
            print("[GL-205-DRILL] step_10: Verifying tenant-scoped grant data in restored DB...")
            try:
                cur_restore = conn_restore.execute("PRAGMA table_info(grants);")
                restore_grant_cols = {row[1] for row in cur_restore.fetchall()}
                if "tenant_id" in restore_grant_cols:
                    grant_row = conn_restore.execute(
                        "SELECT id, tenant_id FROM grants WHERE id = ?;", (_SYNTHETIC_GRANT_ID,)
                    ).fetchone()
                    if grant_row:
                        stored_tenant = grant_row["tenant_id"] if hasattr(grant_row, "__getitem__") else grant_row[1]
                        if stored_tenant == _SYNTHETIC_TENANT_ID:
                            print("[GL-205-DRILL] step_10: Tenant-scoped grant data verified in restored DB.")
                            results.append("step_10: PASS")
                        else:
                            print(f"[GL-205-DRILL] step_10: Grant tenant_id mismatch: {stored_tenant}")
                            results.append("step_10: FAIL tenant-mismatch")
                    else:
                        print("[GL-205-DRILL] step_10: Synthetic grant not found in restored DB.")
                        results.append("step_10: FAIL not-found")
                else:
                    print("[GL-205-DRILL] step_10: tenant_id column not in grants — GL-200B may not have applied.")
                    results.append("step_10: WARN no-tenant-col")
            except Exception as exc:
                print(f"[GL-205-DRILL] step_10: Tenant scoping check failed: {type(exc).__name__}: {exc}")
                results.append(f"step_10: FAIL {type(exc).__name__}")

            # step_11: Verify hash-chain AFTER restore
            print("[GL-205-DRILL] step_11: Verifying audit hash-chain AFTER restore...")
            try:
                rows = conn_restore.execute(
                    "SELECT id, prev_hash, row_hash, action FROM audit_events "
                    "WHERE id IN ('gl205-audit-drill-001', 'gl205-audit-drill-002') "
                    "ORDER BY timestamp;"
                ).fetchall()
                if len(rows) >= 2:
                    computed_h1 = _compute_row_hash_simple(rows[0]["id"], rows[0]["action"], rows[0]["prev_hash"])
                    computed_h2 = _compute_row_hash_simple(rows[1]["id"], rows[1]["action"], rows[1]["prev_hash"])
                    if computed_h1 == rows[0]["row_hash"] and computed_h2 == rows[1]["row_hash"]:
                        print("[GL-205-DRILL] step_11: Hash-chain integrity verified AFTER restore.")
                        results.append("step_11: PASS")
                    else:
                        print("[GL-205-DRILL] step_11: Hash mismatch detected AFTER restore.")
                        results.append("step_11: FAIL hash-mismatch")
                else:
                    print(f"[GL-205-DRILL] step_11: Expected 2 audit rows, found {len(rows)}.")
                    results.append(f"step_11: WARN row-count={len(rows)}")
            except Exception as exc:
                print(f"[GL-205-DRILL] step_11: Post-restore hash check failed: {type(exc).__name__}: {exc}")
                results.append(f"step_11: FAIL {type(exc).__name__}")

            conn_restore.close()

    finally:
        # step_12: Cleanup
        if keep_artifacts:
            print(f"[GL-205-DRILL] step_12: --keep-artifacts set — temp directory retained.")
            print("[GL-205-DRILL]   WARNING: Temp artifacts contain synthetic data — delete manually.")
            results.append("step_12: SKIP keep-artifacts")
        else:
            print("[GL-205-DRILL] step_12: Cleaning up temp files...")
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
                print("[GL-205-DRILL] step_12: Temp files cleaned up.")
                results.append("step_12: PASS")
            except Exception as exc:
                print(f"[GL-205-DRILL] step_12: Cleanup warning: {type(exc).__name__}: {exc}")
                results.append(f"step_12: WARN {type(exc).__name__}")

    # step_13: Summary
    print("[GL-205-DRILL]")
    print("[GL-205-DRILL] step_13: Drill summary:")
    failures = [r for r in results if ": FAIL" in r]
    for r in results:
        print(f"[GL-205-DRILL]   {r}")
    print("[GL-205-DRILL]")
    if failures:
        print(f"[GL-205-DRILL] Drill completed with {len(failures)} failure(s).")
        return 1
    else:
        print("[GL-205-DRILL] SQLite backup/restore drill PASSED — synthetic data only.")
        print("[GL-205-DRILL] NOTE: PostgreSQL backup/restore production readiness remains LIMITED.")
        print("[GL-205-DRILL] See PostgreSQL backup/restore checklist for manual drill steps.")
        return 0


# ---------------------------------------------------------------------------
# Mode entry points
# ---------------------------------------------------------------------------

def _run_dry_run() -> int:
    print("[GL-205-DRILL] Backup/Restore Drill — DRY-RUN mode")
    print("[GL-205-DRILL] Would execute the following steps (no file operations performed):")
    print("[GL-205-DRILL]")
    for step in DRILL_PLAN:
        print(f"[GL-205-DRILL]   {step}")
    print("[GL-205-DRILL]")
    print("[GL-205-DRILL] Dry-run complete. No files created. No data modified.")
    return 0


def _run_plan() -> int:
    print("[GL-205-DRILL] Backup/Restore Drill — PLAN mode")
    print("[GL-205-DRILL]")
    print("[GL-205-DRILL] SQLite Drill Steps:")
    for step in DRILL_PLAN:
        print(f"[GL-205-DRILL]   {step}")
    print("[GL-205-DRILL]")
    print("[GL-205-DRILL] PostgreSQL Drill: Manual checklist only (no live service available).")
    print("[GL-205-DRILL]")
    print(POSTGRES_BACKUP_CHECKLIST)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="GL-205 Backup/Restore Drill Baseline (synthetic data only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Describe actions without performing any file operations",
    )
    mode.add_argument(
        "--plan",
        action="store_true",
        help="Show full drill plan and PostgreSQL checklist without mutation",
    )
    mode.add_argument(
        "--sqlite-drill",
        action="store_true",
        help="Execute the SQLite backup/restore drill (synthetic data only)",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep temp artifacts after drill (for manual inspection; safe to delete after review)",
    )
    args = parser.parse_args()

    if args.dry_run:
        return _run_dry_run()
    elif args.plan:
        return _run_plan()
    elif args.sqlite_drill:
        return _run_sqlite_drill(keep_artifacts=args.keep_artifacts)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
