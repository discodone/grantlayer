"""GrantLayer MVP — Schema migration runner (GL-033 / GL-034).

Minimal migration system: file-based, no ORM, SQLite and PostgreSQL support.
"""

import importlib.util
import inspect
import os
import datetime
from typing import List, Tuple, Any

_MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def _discovery() -> List[Tuple[str, str]]:
    """Return sorted list of (version, filepath) for all migration modules."""
    migrations = []
    for filename in sorted(os.listdir(_MIGRATIONS_DIR)):
        if filename.endswith(".py") and filename[0:4].isdigit() and filename[4] == "_":
            version = filename[:-3]
            migrations.append((version, os.path.join(_MIGRATIONS_DIR, filename)))
    return migrations


def _load_module(filepath: str):
    """Load a migration module from an absolute file path."""
    spec = importlib.util.spec_from_file_location("migration", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _backend(conn: Any) -> str:
    """Return the database backend for a connection or wrapper."""
    return getattr(conn, "backend", "sqlite")


def _ensure_migrations_table(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _applied_versions(conn: Any) -> List[str]:
    """Return list of already-applied migration versions."""
    try:
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        return [r[0] for r in rows]
    except Exception:
        # schema_migrations does not exist yet (or backend-specific error)
        return []


def _mark_applied(conn: Any, version: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (version, now),
    )
    conn.commit()


def _table_exists(conn: Any, name: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (name,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
    return row is not None


def _column_exists(conn: Any, table: str, column: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        try:
            row = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r[1] == column for r in rows)
        except Exception:
            return False


# ──────────────────────────────────────────────────────────────
# Baseline validation helpers for existing GL-032 DBs
# ──────────────────────────────────────────────────────────────

_EXPECTED_TABLES = {
    "grants": [
        "id", "subject_id", "role", "action", "resource",
        "valid_from", "valid_until", "created_by", "reason",
        "revoked", "revoked_by", "revoked_reason", "revoked_at", "created_at",
        "signature", "signing_key_id", "payload_hash",
        "max_uses", "use_count",
    ],
    "audit_events": [
        "id", "timestamp", "subject_id", "role", "action", "resource",
        "approved", "reason", "matched_grant_id",
        "challenge_id", "challenge_present", "challenge_result",
        "grant_signature_result",
    ],
    "challenges": [
        "id", "subject_id", "action", "resource",
        "created_at", "expires_at", "used_at", "status",
    ],
    "operators": [
        "id", "name", "role", "token_hash", "active", "created_at",
    ],
    "grant_requests": [
        "id", "subject_id", "role", "action", "resource",
        "valid_from", "valid_until", "requested_by", "reason",
        "status", "approved_by", "approved_at",
        "denied_by", "denied_at", "denial_reason",
        "revoked_by", "revoked_at", "revoked_reason",
        "grant_id", "created_at", "updated_at",
    ],
    "grant_executions": [
        "id", "grant_id", "grant_request_id", "operator_id",
        "action", "resource", "challenge_id", "challenge_result",
        "policy_result", "result", "error_code", "executed_at",
        "audit_event_id", "metadata_json",
    ],
}

_EXPECTED_INDEXES = [
    ("idx_grant_executions_grant_id", "grant_executions"),
    ("idx_grant_executions_grant_request_id", "grant_executions"),
    ("idx_grant_executions_operator_id", "grant_executions"),
    ("idx_grant_executions_executed_at", "grant_executions"),
]


def _validate_gl032_baseline(conn: Any) -> None:
    """Raise RuntimeError if the existing DB does not look like GL-032 baseline."""
    for table, columns in _EXPECTED_TABLES.items():
        if not _table_exists(conn, table):
            raise RuntimeError(f"Baseline validation failed: missing table '{table}'")
        for col in columns:
            if not _column_exists(conn, table, col):
                raise RuntimeError(
                    f"Baseline validation failed: missing column '{col}' in '{table}'"
                )
    # Validate expected indexes
    backend = _backend(conn)
    for idx_name, idx_table in _EXPECTED_INDEXES:
        if backend == "postgres":
            row = conn.execute(
                "SELECT 1 FROM pg_indexes WHERE indexname = %s AND tablename = %s",
                (idx_name, idx_table),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=? AND tbl_name=?",
                (idx_name, idx_table),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Baseline validation failed: missing index '{idx_name}' on '{idx_table}'"
            )


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def run_migrations(conn: Any) -> None:
    """Run all pending migrations in order.

    On a fresh DB the baseline migration creates the full schema.
    On an existing GL-032 DB the baseline is validated and marked
    as applied without re-executing CREATE statements.
    """
    _ensure_migrations_table(conn)

    applied = set(_applied_versions(conn))

    # Detect legacy GL-032 DB without migration tracker
    if not applied and _table_exists(conn, "grants"):
        # This is an existing DB that predates the migration table.
        _validate_gl032_baseline(conn)
        # Mark every known migration as applied so far
        for version, filepath in _discovery():
            _mark_applied(conn, version)
        return

    for version, filepath in _discovery():
        if version in applied:
            continue
        mod = _load_module(filepath)
        apply_fn = getattr(mod, "apply", None)
        if apply_fn is None:
            raise RuntimeError(f"Migration {version} missing apply(conn) function")
        apply_fn(conn)
        _mark_applied(conn, version)


def get_applied_versions(conn: Any) -> List[str]:
    """Return currently-applied migration versions."""
    _ensure_migrations_table(conn)
    return _applied_versions(conn)
