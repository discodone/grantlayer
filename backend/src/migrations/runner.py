"""GrantLayer MVP — Schema migration runner.

Minimal migration system: file-based, no ORM, SQLite and PostgreSQL support.
"""

import datetime
import importlib.util
import os
from typing import Any, List, Tuple

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
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration module: {filepath}")
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


def _version_from_row(row: Any) -> str:
    """Extract version string from a query result row.

    Supports tuple/list rows, sqlite3.Row-like rows, and PostgreSQL
    dict-like rows.
    """
    if isinstance(row, dict):
        try:
            return row["version"]
        except KeyError:
            raise ValueError(f"Cannot extract version from migration row: {row!r}")
    try:
        return row[0]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return row["version"]
    except (KeyError, IndexError, TypeError):
        pass
    raise ValueError(f"Cannot extract version from migration row: {row!r}")


def _applied_versions(conn: Any) -> List[str]:
    """Return list of already-applied migration versions."""
    if not _table_exists(conn, "schema_migrations"):
        return []
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [_version_from_row(r) for r in rows]


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
# Baseline validation helpers for existing DBs
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
    """Raise RuntimeError if the existing DB does not look like baseline."""
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

_POSTGRES_UNSUPPORTED_MESSAGE = (
    "The file-based migration runner does not support PostgreSQL. It is frozen "
    "for local/SQLite development and test only and must never execute against a "
    "PostgreSQL database — its per-dialect SQL is unmaintained for Postgres and "
    "would risk a partial or divergent schema.\n"
    "Alembic is the authoritative provisioner for PostgreSQL. Run `make migrate` "
    "(equivalently `alembic upgrade head`) to provision or upgrade a production "
    "database. See docs/architecture.md (\"Schema migrations\").\n"
    "The runner refuses to run rather than corrupt the database."
)


_ALEMBIC_COLLISION_MESSAGE = (
    "Two migration systems detected on this database. The Alembic version table "
    "(alembic_version) exists, but the runner's schema_migrations tracker is empty "
    "while the application schema is already present. The runner refuses to mark its "
    "migrations as applied on an Alembic-provisioned database: doing so would record "
    "every migration as done without executing it, silently leaving the schema missing "
    "whatever the runner adds that Alembic does not (for example the audit-immutability "
    "triggers and the audit sequence column).\n"
    "Resolve this in one of two ways:\n"
    "  1. Make Alembic authoritative — port every runner migration's effect into the "
    "Alembic revisions so parity holds, and provision this database with Alembic only "
    "(do not run the file-based runner against it); or\n"
    "  2. Provision this database with the runner from an empty database (no Alembic), "
    "so the runner owns the complete schema.\n"
    "The application will not start until exactly one migration system owns this database."
)


def run_migrations(conn: Any) -> None:
    """Run all pending migrations in order.

    On a fresh DB the baseline migration creates the full schema.
    On an existing DB the baseline is validated and marked
    as applied without re-executing CREATE statements.
    """
    # Fail closed before any database access. When the connection's backend is
    # postgres (set from a postgres:// or postgresql:// URL scheme, either
    # variant), the runner must not touch the database at all: Alembic is the
    # authoritative provisioner for PostgreSQL.
    if _backend(conn) == "postgres":
        raise RuntimeError(_POSTGRES_UNSUPPORTED_MESSAGE)

    _ensure_migrations_table(conn)

    applied = set(_applied_versions(conn))

    # Detect legacy DB without migration tracker.
    # Such a DB already contains the full schema from before the migration
    # runner was introduced; mark all known migrations applied so incremental
    # runs can proceed from a clean state.
    if not applied and _table_exists(conn, "grants"):
        # Fail-closed guard against a two-migration-system collision. If the
        # Alembic version table is present, this database was provisioned by
        # Alembic. Marking the runner's migrations "applied" here would record
        # them as done without executing them, silently leaving out whatever the
        # runner adds that Alembic does not. Refuse rather than corrupt the DB.
        if _table_exists(conn, "alembic_version"):
            raise RuntimeError(_ALEMBIC_COLLISION_MESSAGE)
        _validate_gl032_baseline(conn)
        for version, _filepath in _discovery():
            _mark_applied(conn, version)
        return

    for version, filepath in _discovery():
        if version in applied:
            continue
        mod = _load_module(filepath)
        apply_fn = getattr(mod, "apply", None)
        if apply_fn is None:
            raise RuntimeError(f"Migration {version} missing apply(conn) function")
        try:
            apply_fn(conn)
        except Exception as exc:
            raise RuntimeError(
                f"Migration {version} failed during apply: {exc}"
            ) from exc
        _mark_applied(conn, version)


def list_pending_migrations(conn: Any) -> List[Tuple[str, str]]:
    """Return (version, filepath) pairs for migrations not yet applied.

    Safe to call at any point; does not modify the database.
    Intended for dry-run and readiness checks.
    """
    _ensure_migrations_table(conn)
    applied = set(_applied_versions(conn))
    return [(v, fp) for v, fp in _discovery() if v not in applied]


def get_applied_versions(conn: Any) -> List[str]:
    """Return currently-applied migration versions."""
    _ensure_migrations_table(conn)
    return _applied_versions(conn)
