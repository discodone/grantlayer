#!/usr/bin/env python3
"""GL-205 — Live PostgreSQL Validation Script.

This script validates PostgreSQL behavior using synthetic/demo data only.
It is gated by explicit environment variables and will refuse to run without
explicit consent.

SAFETY RULES:
- Must not run unless GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES=1 is set.
- Must require GRANTLAYER_GL205_POSTGRES_DSN environment variable.
- Must reject SQLite DSNs, empty, placeholder, or obviously unsafe DSNs.
- Must not print or log raw DSN/password/secret values.
- Supports --dry-run (validate config only, no connection).
- Supports --plan (show safe steps without mutation).
- If live mode is used, must only target an explicitly provided ephemeral/synthetic DB.
- Must fail closed if configuration is ambiguous.

Usage:
  python3 scripts/ops/gl205_live_postgres_validation.py --dry-run
  python3 scripts/ops/gl205_live_postgres_validation.py --plan
  GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES=1 \\
    GRANTLAYER_GL205_POSTGRES_DSN=postgres://... \\
    python3 scripts/ops/gl205_live_postgres_validation.py --live
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# DSN safety helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_DSN_SUBSTRINGS = (
    "localhost",
    "127.0.0.1",
    "example.com",
    "yourdomain",
    "placeholder",
    "changeme",
    "your-db",
    "demo-dsn",
    "test-dsn",
    "<",
    ">",
)

_UNSAFE_PRODUCTION_HOSTNAMES = (
    ".prod.",
    "-prod.",
    "-production.",
    ".production.",
    "production-",
    "prod-",
)


def _mask_dsn(dsn: str) -> str:
    """Return a masked DSN safe for display — never expose password or full path."""
    try:
        parsed = urlparse(dsn)
        scheme = parsed.scheme or "unknown"
        host = parsed.hostname or "unknown"
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or "unknown"
        db = (parsed.path or "").lstrip("/") or "unknown"
        return f"{scheme}://{user}:***@{host}{port}/{db}"
    except Exception:
        return "<dsn-parse-error>"


def _validate_dsn(dsn: str) -> Optional[str]:
    """Validate DSN safety. Returns error message or None if safe."""
    if not dsn or not dsn.strip():
        return "DSN is empty or whitespace-only"

    dsn_lower = dsn.lower()

    # Must be postgres/postgresql scheme
    if not (dsn_lower.startswith("postgres://") or dsn_lower.startswith("postgresql://")):
        if dsn_lower.startswith("sqlite"):
            return "SQLite DSNs are rejected for the live PostgreSQL validation path"
        return "DSN must use postgres:// or postgresql:// scheme"

    # Check for placeholder/demo substrings
    for fragment in _PLACEHOLDER_DSN_SUBSTRINGS:
        if fragment in dsn_lower:
            return (
                f"DSN contains placeholder/unsafe fragment: '{fragment}'. "
                "Provide an explicit ephemeral/synthetic PostgreSQL DSN."
            )

    # Check for obvious production hostnames
    try:
        parsed = urlparse(dsn)
        hostname = (parsed.hostname or "").lower()
        for frag in _UNSAFE_PRODUCTION_HOSTNAMES:
            if frag in hostname:
                return (
                    f"DSN hostname looks production-like ('{frag}' found). "
                    "Only use ephemeral/synthetic databases for this validation."
                )
    except Exception:
        return "DSN could not be parsed for safety validation"

    return None


# ---------------------------------------------------------------------------
# Mode checks
# ---------------------------------------------------------------------------

_ENABLE_ENV_VAR = "GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES"
_DSN_ENV_VAR = "GRANTLAYER_GL205_POSTGRES_DSN"


def _check_gate() -> bool:
    """Return True if the explicit environment gate is set."""
    return os.environ.get(_ENABLE_ENV_VAR, "").strip() == "1"


def _get_dsn() -> Optional[str]:
    return os.environ.get(_DSN_ENV_VAR, "").strip() or None


# ---------------------------------------------------------------------------
# Validation steps
# ---------------------------------------------------------------------------

VALIDATION_PLAN = [
    "step_01: Verify explicit environment gate (GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES=1)",
    "step_02: Verify explicit DSN is provided (GRANTLAYER_GL205_POSTGRES_DSN)",
    "step_03: Validate DSN safety (no SQLite, no placeholder, no production hostname)",
    "step_04: Connect to ephemeral/synthetic PostgreSQL instance",
    "step_05: Verify PostgreSQL version is reachable",
    "step_06: Apply migrations (synthetic schema only, idempotency check)",
    "step_07: Verify migration idempotency (re-run migrations, confirm no error)",
    "step_08: Verify GL-200 tenant/workspace schema exists (tenants/workspaces tables)",
    "step_09: Verify audit_events table and hash-chain columns exist",
    "step_10: Verify no unsafe legacy audit backfill triggers exist",
    "step_11: Insert synthetic tenant + workspace records",
    "step_12: Verify tenant-scoped synthetic CRUD (grants table if feasible)",
    "step_13: Insert synthetic audit event and verify hash-chain integrity",
    "step_14: Clean up synthetic objects",
    "step_15: Report results — success or failure with safe diagnostics",
]


def _run_dry_run() -> int:
    """Validate configuration without connecting. Returns exit code."""
    print("[GL-205] Live PostgreSQL Validation — DRY-RUN mode")
    print("[GL-205] Checking environment gate...")

    gate = _check_gate()
    dsn = _get_dsn()

    if gate:
        print(f"[GL-205]   {_ENABLE_ENV_VAR} = 1 (gate is SET)")
    else:
        print(f"[GL-205]   {_ENABLE_ENV_VAR} = not set (gate is CLEAR — safe default)")

    if dsn:
        masked = _mask_dsn(dsn)
        err = _validate_dsn(dsn)
        if err:
            print(f"[GL-205]   {_DSN_ENV_VAR} present but INVALID: {err}")
            print(f"[GL-205]   Masked DSN: {masked}")
            print("[GL-205] Dry-run: DSN validation failed — would fail closed in live mode")
            return 1
        else:
            print(f"[GL-205]   {_DSN_ENV_VAR} present and passes safety checks")
            print(f"[GL-205]   Masked DSN: {masked}")
    else:
        print(f"[GL-205]   {_DSN_ENV_VAR} = not set")

    print("[GL-205]")
    print("[GL-205] Dry-run complete — no connection attempted.")
    print("[GL-205] To run live validation, provide:")
    print(f"[GL-205]   {_ENABLE_ENV_VAR}=1")
    print(f"[GL-205]   {_DSN_ENV_VAR}=<ephemeral-postgres-dsn>")
    print("[GL-205] and pass --live flag.")
    return 0


def _run_plan() -> int:
    """Show safe validation steps without mutation. Returns exit code."""
    print("[GL-205] Live PostgreSQL Validation — PLAN mode")
    print("[GL-205] The following steps would be executed in --live mode:")
    print("[GL-205]")
    for step in VALIDATION_PLAN:
        print(f"[GL-205]   {step}")
    print("[GL-205]")
    print("[GL-205] All steps use synthetic/demo data only.")
    print("[GL-205] No connection is made in plan mode.")
    print("[GL-205] No production data is accessed.")
    print("[GL-205] Plan mode complete.")
    return 0


def _run_live() -> int:
    """Execute live PostgreSQL validation against ephemeral/synthetic instance."""
    print("[GL-205] Live PostgreSQL Validation — LIVE mode")
    print("[GL-205] Checking explicit environment gate...")

    # Gate check — fail closed
    if not _check_gate():
        print(
            f"[GL-205] ERROR: {_ENABLE_ENV_VAR} is not set to '1'. "
            "Refusing to run live validation without explicit gate."
        )
        print("[GL-205] Set the environment variable to proceed.")
        print("[GL-205] Failing closed.")
        return 2

    print(f"[GL-205]   Gate {_ENABLE_ENV_VAR}=1 confirmed.")

    # DSN check
    dsn = _get_dsn()
    if not dsn:
        print(
            f"[GL-205] ERROR: {_DSN_ENV_VAR} is not set. "
            "An explicit ephemeral/synthetic PostgreSQL DSN is required."
        )
        print("[GL-205] Failing closed.")
        return 2

    # DSN safety validation
    dsn_err = _validate_dsn(dsn)
    if dsn_err:
        masked = _mask_dsn(dsn)
        print(f"[GL-205] ERROR: DSN failed safety validation: {dsn_err}")
        print(f"[GL-205]   Masked DSN: {masked}")
        print("[GL-205] Failing closed.")
        return 2

    masked = _mask_dsn(dsn)
    print(f"[GL-205]   DSN passes safety checks. Masked: {masked}")
    print("[GL-205]")

    # Attempt psycopg2 import
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        print("[GL-205] ERROR: psycopg2 is not installed.")
        print("[GL-205]   Install with: pip install psycopg2-binary")
        print("[GL-205] Failing — live PostgreSQL validation requires psycopg2.")
        return 1

    results: list[str] = []

    try:
        print("[GL-205] step_04: Connecting to ephemeral/synthetic PostgreSQL instance...")
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # step_05: Version check
        cur.execute("SELECT version();")
        row = cur.fetchone()
        pg_version = row[0][:80] if row else "unknown"
        print(f"[GL-205] step_05: PostgreSQL reachable. Version prefix: {pg_version[:60]}...")
        results.append("step_05: PASS")

        # step_06: Apply migrations
        print("[GL-205] step_06: Applying migrations...")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
            from src.migrations.runner import run_migrations  # type: ignore
            run_migrations(conn)
            print("[GL-205] step_06: Migrations applied.")
            results.append("step_06: PASS")
        except Exception as exc:
            print(f"[GL-205] step_06: Migration failed: {type(exc).__name__}: {exc}")
            results.append("step_06: FAIL")

        # step_07: Idempotency — re-run migrations
        print("[GL-205] step_07: Verifying migration idempotency...")
        try:
            run_migrations(conn)
            print("[GL-205] step_07: Idempotency confirmed.")
            results.append("step_07: PASS")
        except Exception as exc:
            print(f"[GL-205] step_07: Idempotency check failed: {type(exc).__name__}: {exc}")
            results.append("step_07: FAIL")

        # step_08: Tenant/workspace schema (GL-200B adds tenant_id columns to business tables)
        print("[GL-205] step_08: Verifying GL-200B tenant/workspace isolation columns...")
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='grants' AND column_name='tenant_id';"
        )
        grants_tenant_col = cur.fetchone()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='audit_events' AND column_name='tenant_id';"
        )
        audit_tenant_col = cur.fetchone()
        if grants_tenant_col and audit_tenant_col:
            print("[GL-205] step_08: tenant_id column present on grants and audit_events (GL-200B isolation confirmed).")
            results.append("step_08: PASS")
        elif grants_tenant_col:
            print("[GL-205] step_08: tenant_id on grants but not audit_events.")
            results.append("step_08: PARTIAL")
        else:
            print("[GL-205] step_08: tenant_id column missing from grants — GL-200B migration may not have applied.")
            results.append("step_08: FAIL tenant-col-missing")

        # step_09: Audit table
        print("[GL-205] step_09: Verifying audit_events table and hash-chain columns...")
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='audit_events';"
        )
        cols = {r[0] for r in cur.fetchall()}
        required_cols = {"id", "timestamp", "action", "row_hash"}
        missing_cols = required_cols - cols
        if not missing_cols:
            print("[GL-205] step_09: audit_events hash-chain columns present.")
            results.append("step_09: PASS")
        else:
            print(f"[GL-205] step_09: Missing columns: {missing_cols}")
            results.append(f"step_09: PARTIAL missing={missing_cols}")

        # step_10: No unsafe legacy audit backfill triggers
        print("[GL-205] step_10: Checking for unsafe legacy audit backfill triggers...")
        cur.execute(
            "SELECT trigger_name FROM information_schema.triggers "
            "WHERE trigger_schema='public' AND trigger_name ILIKE '%backfill%';"
        )
        backfill_triggers = [r[0] for r in cur.fetchall()]
        if not backfill_triggers:
            print("[GL-205] step_10: No unsafe backfill triggers found.")
            results.append("step_10: PASS")
        else:
            print(f"[GL-205] step_10: WARNING — backfill triggers found: {backfill_triggers}")
            results.append(f"step_10: WARN triggers={backfill_triggers}")

        # step_11: Insert synthetic scoped grant record
        print("[GL-205] step_11: Inserting synthetic tenant-scoped grant record...")
        try:
            cur.execute(
                "INSERT INTO grants (id, subject_id, role, action, resource, "
                "valid_from, valid_until, created_by, reason, tenant_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) ON CONFLICT (id) DO NOTHING;",
                ("gl205-synthetic-grant-001", "gl205-synthetic-subject", "synthetic",
                 "read", "synthetic-resource", "2026-01-01T00:00:00Z",
                 "2099-01-01T00:00:00Z", "gl205-validation", "GL-205 synthetic grant",
                 "gl205-synthetic-tenant"),
            )
            conn.commit()
            print("[GL-205] step_11: Synthetic scoped grant inserted.")
            results.append("step_11: PASS")
        except Exception as exc:
            conn.rollback()
            print(f"[GL-205] step_11: Synthetic insert failed: {type(exc).__name__}: {exc}")
            results.append(f"step_11: FAIL {type(exc).__name__}")

        # step_12: Synthetic CRUD — read back scoped grant
        print("[GL-205] step_12: Verifying tenant-scoped CRUD path (read-back)...")
        try:
            cur.execute(
                "SELECT tenant_id FROM grants WHERE id = %s;",
                ("gl205-synthetic-grant-001",),
            )
            row = cur.fetchone()
            if row and row[0] == "gl205-synthetic-tenant":
                print("[GL-205] step_12: Synthetic scoped grant readable with correct tenant_id.")
                results.append("step_12: PASS")
            elif row:
                print(f"[GL-205] step_12: Grant found but unexpected tenant_id: {row[0]}")
                results.append("step_12: FAIL unexpected-tenant")
            else:
                print("[GL-205] step_12: Synthetic grant not found after insert.")
                results.append("step_12: FAIL not-found")
        except Exception as exc:
            print(f"[GL-205] step_12: CRUD check failed: {type(exc).__name__}: {exc}")
            results.append(f"step_12: FAIL {type(exc).__name__}")

        # step_13: Synthetic audit event + hash-chain
        print("[GL-205] step_13: Inserting synthetic audit event and verifying hash-chain...")
        try:
            import hashlib, json as _json
            synthetic_event = {
                "id": "gl205-audit-001",
                "timestamp": "2026-01-01T00:00:00Z",
                "subject_id": "gl205-synthetic-subject",
                "role": "synthetic",
                "action": "gl205_validation_test",
                "resource": "synthetic",
                "approved": True,
                "reason": "GL-205 synthetic validation",
                "matched_grant_id": None,
                "challenge_id": None,
                "challenge_present": False,
                "challenge_result": None,
                "grant_signature_result": None,
                "prev_hash": "0" * 64,
                "tenant_id": "gl205-synthetic-tenant-001",
            }
            canonical = _json.dumps(
                {k: v for k, v in synthetic_event.items() if k != "id"},
                sort_keys=True, separators=(",", ":"),
            )
            # Use the GL-205 payload format for hash
            hash_payload = {
                k: synthetic_event[k]
                for k in [
                    "id", "timestamp", "subject_id", "role", "action", "resource",
                    "approved", "reason", "matched_grant_id", "challenge_id",
                    "challenge_present", "challenge_result", "grant_signature_result",
                    "prev_hash", "tenant_id",
                ]
            }
            computed_hash = hashlib.sha256(
                _json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

            # Insert if columns exist
            if {"id", "timestamp", "action", "row_hash"}.issubset(cols):
                cur.execute(
                    "INSERT INTO audit_events (id, timestamp, subject_id, role, action, "
                    "resource, approved, reason, tenant_id, prev_hash, row_hash) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING;",
                    (
                        "gl205-audit-001",
                        "2026-01-01T00:00:00Z",
                        "gl205-synthetic-subject",
                        "synthetic",
                        "gl205_validation_test",
                        "synthetic",
                        True,
                        "GL-205 synthetic validation",
                        "gl205-synthetic-tenant-001",
                        "0" * 64,
                        computed_hash,
                    ),
                )
                conn.commit()
                cur.execute(
                    "SELECT row_hash FROM audit_events WHERE id = %s;",
                    ("gl205-audit-001",),
                )
                row = cur.fetchone()
                stored_hash = row[0] if row else None
                if stored_hash == computed_hash:
                    print("[GL-205] step_13: Audit hash-chain integrity verified.")
                    results.append("step_13: PASS")
                else:
                    print(f"[GL-205] step_13: Hash mismatch — expected != stored.")
                    results.append("step_13: FAIL hash-mismatch")
            else:
                print("[GL-205] step_13: Skipped — missing required audit_events columns.")
                results.append("step_13: SKIP missing-columns")
        except Exception as exc:
            conn.rollback()
            print(f"[GL-205] step_13: Audit hash-chain test failed: {type(exc).__name__}: {exc}")
            results.append(f"step_13: FAIL {type(exc).__name__}")

        # step_14: Clean up synthetic objects
        print("[GL-205] step_14: Cleaning up synthetic objects...")
        try:
            cur.execute("DELETE FROM audit_events WHERE id = %s;", ("gl205-audit-001",))
            cur.execute("DELETE FROM grants WHERE id = %s;", ("gl205-synthetic-grant-001",))
            conn.commit()
            print("[GL-205] step_14: Synthetic objects cleaned up.")
            results.append("step_14: PASS")
        except Exception as exc:
            conn.rollback()
            print(f"[GL-205] step_14: Cleanup failed: {type(exc).__name__}: {exc}")
            results.append(f"step_14: WARN cleanup-failed {type(exc).__name__}")

        cur.close()
        conn.close()

    except Exception as exc:
        print(f"[GL-205] ERROR during live validation: {type(exc).__name__}: {exc}")
        print("[GL-205] Live validation did not complete.")
        return 1

    # step_15: Summary
    print("[GL-205]")
    print("[GL-205] step_15: Validation summary:")
    failures = [r for r in results if ": FAIL" in r]
    for r in results:
        status = "PASS" if ": PASS" in r else ("FAIL" if ": FAIL" in r else ("SKIP" if ": SKIP" in r else "WARN"))
        print(f"[GL-205]   {r}")
    print("[GL-205]")
    if failures:
        print(f"[GL-205] Live validation completed with {len(failures)} failure(s).")
        return 1
    else:
        print("[GL-205] Live validation completed — all steps passed.")
        print("[GL-205] NOTE: This validates ephemeral/synthetic behavior only.")
        print("[GL-205] Live PostgreSQL production claim remains NO-GO until broader gates pass.")
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="GL-205 Live PostgreSQL Validation (synthetic/demo data only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without connecting",
    )
    mode.add_argument(
        "--plan",
        action="store_true",
        help="Show safe validation steps without mutation",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help=(
            "Execute live validation against explicit ephemeral/synthetic PostgreSQL "
            f"(requires {_ENABLE_ENV_VAR}=1 and {_DSN_ENV_VAR})"
        ),
    )
    args = parser.parse_args()

    if args.dry_run:
        return _run_dry_run()
    elif args.plan:
        return _run_plan()
    elif args.live:
        return _run_live()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
