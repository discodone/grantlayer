"""GrantLayer MVP — Database connection factory and query helpers (GL-034 / GL-035).

Supports SQLite (default) and PostgreSQL backends.
psycopg2 is lazy-imported only when a postgres:// URL is configured.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any
from urllib.parse import urlparse

from . import migrations


# ──────────────────────────────────────────────────────────────
# Placeholder scanner
# ──────────────────────────────────────────────────────────────

def _translate_placeholders(sql: str) -> tuple[str, int]:
    """Translate SQLite ? placeholders to PostgreSQL %s.

    Returns (translated_sql, placeholder_count).

    Only translates ? outside of:
    - single-quoted string literals
    - doubled single-quote escapes inside string literals
    - double-quoted identifiers
    - line comments (-- ...)
    - block comments (/* ... */)
    """
    result: list[str] = []
    i = 0
    n = len(sql)
    count = 0

    while i < n:
        ch = sql[i]

        # Block comment /* */
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            if j == -1:
                result.append(sql[i:])
                break
            result.append(sql[i : j + 2])
            i = j + 2
            continue

        # Line comment -- \n
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i + 2)
            if j == -1:
                result.append(sql[i:])
                break
            result.append(sql[i : j + 1])
            i = j + 1
            continue

        # Single-quoted string literal
        if ch == "'":
            result.append("'")
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    result.append("''")
                    i += 2
                    continue
                if sql[i] == "'":
                    result.append("'")
                    i += 1
                    break
                result.append(sql[i])
                i += 1
            continue

        # Double-quoted identifier
        if ch == '"':
            result.append('"')
            i += 1
            while i < n and sql[i] != '"':
                result.append(sql[i])
                i += 1
            if i < n:
                result.append('"')
                i += 1
            continue

        # Placeholder
        if ch == "?":
            result.append("%s")
            count += 1
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result), count


# ──────────────────────────────────────────────────────────────
# Connection factory
# ──────────────────────────────────────────────────────────────

def _parse_database_url(url: str) -> tuple[str, str]:
    """Parse a database URL and return (backend, path_or_dsn).

    SQLite formats:
      sqlite:///absolute/path or sqlite:///:memory:
      sqlite://relative/path or sqlite://:memory:
      sqlite:relative/path or sqlite::memory:

    PostgreSQL formats:
      postgres://... or postgresql://...
    """
    if not url:
        return "sqlite", ""

    parsed = urlparse(url)

    if parsed.scheme in ("postgres", "postgresql"):
        return "postgres", url

    if parsed.scheme != "sqlite":
        raise RuntimeError(f"Unsupported database URL scheme: {parsed.scheme}")

    # sqlite:///absolute/path or sqlite:///:memory:
    if url.startswith("sqlite:///"):
        path = url[10:]
        if path == ":memory:":
            return "sqlite", ":memory:"
        return "sqlite", "/" + path
    # sqlite://relative/path or sqlite://:memory:
    elif url.startswith("sqlite://"):
        return "sqlite", url[9:]
    # sqlite:relative/path or sqlite::memory:
    elif url.startswith("sqlite:"):
        return "sqlite", url[7:]
    else:
        return "sqlite", url


def _resolve_db_url() -> tuple[str, str]:
    """Resolve database backend and path/DSN from env vars."""
    url = os.environ.get("GRANTLAYER_DATABASE_URL", "")
    if url:
        return _parse_database_url(url)
    legacy = os.environ.get("GRANTLAYER_DB", "")
    if legacy:
        return "sqlite", legacy
    return "sqlite", os.path.join(os.path.dirname(__file__), "../../data/grantlayer.db")


DB_BACKEND, DB_PATH_OR_URL = _resolve_db_url()

# Backward-compatible alias for code that references the single path variable.
DB_PATH = DB_PATH_OR_URL

# PostgreSQL connection pool state (GL-123)
_pg_pool: Any = None
_pg_pool_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────
# Bounded retry config (GL-035: PostgreSQL transient failures)
# ──────────────────────────────────────────────────────────────

# Maximum connection attempts for PostgreSQL on startup
_db_retry_max = int(os.environ.get("GRANTLAYER_DB_RETRY_MAX", "5"))
# Delay between retries in seconds
_db_retry_delay = float(os.environ.get("GRANTLAYER_DB_RETRY_DELAY", "1.0"))

# Connection pool sizing for PostgreSQL (GL-123)
_db_pool_min = int(os.environ.get("GRANTLAYER_DB_POOL_MIN", "2"))
_db_pool_max = int(os.environ.get("GRANTLAYER_DB_POOL_MAX", "10"))


class _ConnectionWrapper:
    """Wraps either sqlite3.Connection or psycopg2 connection.

    Provides a unified interface so existing code patterns continue to work:
      conn.execute(sql, params) -> cursor
      conn.executemany(sql, params_list) -> cursor
      conn.executescript(sql) -> None
      conn.commit()
      conn.rollback()
      conn.close()
    """

    def __init__(self, raw_conn: Any, backend: str, pool: Any = None) -> None:
        self._conn = raw_conn
        self.backend = backend
        self._pool = pool

    def cursor(self) -> Any:
        return self._conn.cursor()

    def execute(self, sql: str, parameters: Any = None) -> Any:
        """Execute SQL and return the cursor."""
        cur = self._conn.cursor()
        if self.backend == "postgres":
            sql, _ = _translate_placeholders(sql)
        cur.execute(sql, parameters or ())
        return cur

    def executemany(self, sql: str, parameters: Any) -> Any:
        """Execute SQL against multiple parameter sets and return the cursor."""
        cur = self._conn.cursor()
        if self.backend == "postgres":
            sql, _ = _translate_placeholders(sql)
        cur.executemany(sql, parameters)
        return cur

    def executescript(self, sql: str) -> None:
        """Execute a script of semicolon-separated statements."""
        if self.backend == "postgres":
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                # Strip leading line comments so a statement like
                # "-- comment\nCREATE TABLE ..." is not mistakenly skipped.
                non_comment_lines = [
                    line for line in stmt.splitlines()
                    if not line.strip().startswith("--")
                ]
                actual = "\n".join(non_comment_lines).strip()
                if actual:
                    cur = self._conn.cursor()
                    cur.execute(actual)
                    cur.close()
        else:
            self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.putconn(self._conn)
        else:
            self._conn.close()

    def __enter__(self) -> "_ConnectionWrapper":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def get_conn() -> _ConnectionWrapper:
    """Return a connection wrapper for the configured backend.

    For PostgreSQL, uses a SimpleConnectionPool (GL-123) with bounded retry
    on transient pool-creation failures. Connections are returned to the pool
    via wrapper.close() so existing finally-block patterns continue to work.
    """
    if DB_BACKEND == "postgres":
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            from psycopg2.pool import SimpleConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL is configured but psycopg2 is not installed. "
                "Install it with: pip install psycopg2-binary"
            ) from exc

        global _pg_pool
        if _pg_pool is None:
            with _pg_pool_lock:
                if _pg_pool is None:
                    last_err: Exception | None = None
                    max_attempts = max(1, _db_retry_max)
                    for attempt in range(1, max_attempts + 1):
                        try:
                            _pg_pool = SimpleConnectionPool(
                                max(1, _db_pool_min),
                                max(1, _db_pool_max),
                                DB_PATH_OR_URL,
                                cursor_factory=RealDictCursor,
                            )
                            break
                        except psycopg2.OperationalError as exc:
                            last_err = exc
                            if attempt < max_attempts:
                                time.sleep(_db_retry_delay)
                            continue
                    if _pg_pool is None:
                        raise RuntimeError(
                            f"PostgreSQL connection failed after {max_attempts} attempt(s). "
                            "Check that the server is reachable and the DSN is correct."
                        ) from last_err

        raw = _pg_pool.getconn()
        return _ConnectionWrapper(raw, "postgres", pool=_pg_pool)

    conn = sqlite3.connect(DB_PATH_OR_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return _ConnectionWrapper(conn, "sqlite")


def _close_pg_pool() -> None:
    """Close the PostgreSQL connection pool and release all connections.

    Safe to call when no pool exists. Intended for test cleanup and graceful
    shutdown; not required for normal operation.
    """
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None


def init_db() -> None:
    if DB_BACKEND == "sqlite" and DB_PATH_OR_URL != ":memory:" and not DB_PATH_OR_URL.startswith("file::memory:"):
        db_dir = os.path.dirname(os.path.abspath(DB_PATH_OR_URL))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    conn = get_conn()
    try:
        migrations.run_migrations(conn)
        # GL-021: Bootstrap operators if needed
        from . import operators

        operators.ensure_operators_table()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Bounded CRUD query helpers
# ──────────────────────────────────────────────────────────────

def execute(sql: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute a single-row SELECT and return a dict or None."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a multi-row SELECT and return a list of dicts."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def executemany(sql: str, params_list: list) -> int:
    """Execute a statement against multiple parameter sets and return rowcount."""
    conn = get_conn()
    try:
        cur = conn.executemany(sql, params_list)
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Health / Readiness helpers (GL-032 / GL-034)
# ──────────────────────────────────────────────────────────────

def _db_is_file() -> bool:
    """Return True if the current SQLite backend uses an on-disk file."""
    return (
        DB_BACKEND == "sqlite"
        and DB_PATH_OR_URL != ":memory:"
        and not DB_PATH_OR_URL.startswith("file::memory:")
    )


def get_db_health() -> dict[str, Any]:
    """Return safe, additive readiness fields for the current backend.

    No absolute paths, no raw dbPath values, no secrets.
    """
    result: dict[str, Any] = {
        "dbConnected": False,
        "dbWritable": False,
        "dbFilePresent": False,
        "dbDirectoryWritable": False,
        "dbSizeBytes": None,
        "journalMode": None,
        "dbPathKind": "memory"
        if DB_BACKEND == "sqlite" and DB_PATH_OR_URL == ":memory:"
        else "postgres"
        if DB_BACKEND == "postgres"
        else "file",
        # GL-035: PostgreSQL additive fields
        "pgVersion": None,
        "pgBackendPid": None,
        "pgActiveConnections": None,
    }

    # dbFilePresent / dbSizeBytes / dbDirectoryWritable (SQLite file only)
    if _db_is_file():
        try:
            result["dbFilePresent"] = os.path.isfile(DB_PATH_OR_URL)
            if result["dbFilePresent"]:
                result["dbSizeBytes"] = os.path.getsize(DB_PATH_OR_URL)
        except OSError:
            pass

        try:
            db_dir = os.path.dirname(os.path.abspath(DB_PATH_OR_URL))
            result["dbDirectoryWritable"] = os.access(db_dir, os.W_OK)
        except OSError:
            pass

    # dbConnected + journalMode + dbWritable + PostgreSQL fields
    try:
        conn = get_conn()
        try:
            # connected
            conn.execute("SELECT 1")
            result["dbConnected"] = True

            # journal mode (SQLite only)
            if DB_BACKEND == "sqlite":
                row = conn.execute("PRAGMA journal_mode").fetchone()
                if row:
                    result["journalMode"] = row[0]

            # writable — use a TEMP table so no persistent schema change
            if DB_BACKEND == "postgres":
                conn.execute("CREATE TEMP TABLE _gl032_health_probe (id INTEGER)")
                conn.execute("INSERT INTO _gl032_health_probe VALUES (1)")
                conn.execute("DROP TABLE _gl032_health_probe")
            else:
                conn.execute("CREATE TEMP TABLE _gl032_health_probe (id INTEGER)")
                conn.execute("INSERT INTO _gl032_health_probe VALUES (1)")
                conn.execute("DROP TABLE _gl032_health_probe")
            result["dbWritable"] = True

            # GL-035: PostgreSQL version (available without elevated privileges)
            if DB_BACKEND == "postgres":
                try:
                    row = conn.execute("SELECT version()").fetchone()
                    if row:
                        # version() returns e.g. "PostgreSQL 16.2 on ..."
                        version_str = row[0] if isinstance(row, dict) else row[0]
                        if version_str.startswith("PostgreSQL "):
                            result["pgVersion"] = version_str.split(" ")[1]
                except Exception:
                    pass

                # Backend PID (no elevated privileges needed)
                try:
                    row = conn.execute("SELECT pg_backend_pid()").fetchone()
                    if row:
                        result["pgBackendPid"] = row[0] if isinstance(row, dict) else row[0]
                except Exception:
                    pass

                # Active connections count (no elevated privileges needed for pg_stat_activity)
                try:
                    row = conn.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                    ).fetchone()
                    if row:
                        result["pgActiveConnections"] = row[0] if isinstance(row, dict) else row[0]
                except Exception:
                    pass
        finally:
            conn.close()
    except Exception:
        pass

    return result
