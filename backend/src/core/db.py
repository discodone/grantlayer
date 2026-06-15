"""GrantLayer MVP — Database connection factory and query helpers.

Supports SQLite (default) and PostgreSQL backends.
psycopg2 is lazy-imported only when a postgres:// URL is configured.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .. import migrations

# ──────────────────────────────────────────────────────────────
# SQLAlchemy engine (ORM layer)
# ──────────────────────────────────────────────────────────────

_sa_engine = None
_engine_url = None


def get_engine():
    """Return the SQLAlchemy engine for the configured backend."""
    global _sa_engine, _engine_url
    url = DB_PATH_OR_URL
    if DB_BACKEND == "postgres":
        # SQLAlchemy requires 'postgresql://' not 'postgres://'
        if url.startswith("postgres://"):
            url = "postgresql" + url[8:]
        current_url = url
    else:
        current_url = f"sqlite:///{url}"
    if _sa_engine is None or _engine_url != current_url:
        _engine_url = current_url
        if DB_BACKEND == "postgres":
            _sa_engine = create_engine(current_url)
        else:
            _sa_engine = create_engine(current_url)
            from sqlalchemy import event

            @event.listens_for(_sa_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _sa_engine


def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    return Session(get_engine())


_session_maker: Any = None
_session_maker_engine: Any = None


def get_session_maker() -> Any:
    """Return the session maker factory, rebuilding it when the engine changes.

    Rebuilding on engine change is required for test isolation: tests swap
    DB_PATH_OR_URL between runs, which causes get_engine() to return a new
    engine.  The cached sessionmaker must follow.
    """
    global _session_maker, _session_maker_engine
    engine = get_engine()
    if _session_maker is None or _session_maker_engine is not engine:
        _session_maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        _session_maker_engine = engine
    return _session_maker


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a SQLAlchemy Session per request.

    Usage in a router:
        @router.get("/example")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    SessionLocal = get_session_maker()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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


def _translate_to_named_params(sql: str, params: tuple) -> tuple[str, dict[str, Any]]:
    """Translate SQLite ? placeholders to :p1, :p2 ... named placeholders.

    Returns (translated_sql, param_dict) so the statement can be executed
    via SQLAlchemy text() with a dict binding.
    """
    result: list[str] = []
    i = 0
    n = len(sql)
    param_idx = 0
    param_dict: dict[str, Any] = {}

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
            param_idx += 1
            key = f"p{param_idx}"
            result.append(f":{key}")
            param_dict[key] = params[param_idx - 1]
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result), param_dict


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

# PostgreSQL connection pool state
_pg_pool: Any = None
_pg_pool_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────
# Bounded retry config (PostgreSQL transient failures)
# ──────────────────────────────────────────────────────────────

# Maximum connection attempts for PostgreSQL on startup
_db_retry_max = int(os.environ.get("GRANTLAYER_DB_RETRY_MAX", "5"))
# Delay between retries in seconds
_db_retry_delay = float(os.environ.get("GRANTLAYER_DB_RETRY_DELAY", "1.0"))

# Connection pool sizing for PostgreSQL
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

    def execute(self, sql: Any, parameters: Any = None) -> Any:
        """Execute SQL and return the cursor.

        Accepts both plain SQL strings and SQLAlchemy text() clause elements
        (with named :p1 parameters) for backward compatibility with code that
        uses the SQLAlchemy connection interface.
        """
        from sqlalchemy import TextClause

        if isinstance(sql, TextClause):
            sql_str = sql.text
            if isinstance(parameters, dict):
                # Convert :p1, :p2 named params → positional ? params
                pos_params: list[Any] = []
                parts: list[str] = []
                i = 0
                while i < len(sql_str):
                    if sql_str[i] == ":" and i + 1 < len(sql_str) and (
                        sql_str[i + 1].isalpha() or sql_str[i + 1] == "_"
                    ):
                        j = i + 1
                        while j < len(sql_str) and (sql_str[j].isalnum() or sql_str[j] == "_"):
                            j += 1
                        key = sql_str[i + 1 : j]
                        if key in parameters:
                            pos_params.append(parameters[key])
                            parts.append("?")
                            i = j
                            continue
                    parts.append(sql_str[i])
                    i += 1
                sql = "".join(parts)
                parameters = tuple(pos_params)
            else:
                sql = sql_str
                parameters = parameters or ()
        else:
            parameters = parameters or ()

        cur = self._conn.cursor()
        if self.backend == "postgres":
            sql, _ = _translate_placeholders(sql)
        cur.execute(sql, parameters)
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

    For PostgreSQL, uses a ThreadedConnectionPool with bounded retry
    on transient pool-creation failures. Connections are returned to the pool
    via wrapper.close() so existing finally-block patterns continue to work.
    """
    if DB_BACKEND == "postgres":
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            from psycopg2.pool import ThreadedConnectionPool
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
                            _pg_pool = ThreadedConnectionPool(
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
        # Bootstrap operators if needed
        from ..auth import operators

        operators.ensure_operators_table()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Bounded CRUD query helpers
# ──────────────────────────────────────────────────────────────

def execute(sql: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE via SQLAlchemy and return rowcount."""
    sql, param_dict = _translate_to_named_params(sql, params)
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), param_dict)
        conn.commit()
        return result.rowcount or 0


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute a single-row SELECT via SQLAlchemy and return a dict or None."""
    sql, param_dict = _translate_to_named_params(sql, params)
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), param_dict)
        row = result.fetchone()
        return _orm_to_dict(row) if row else None


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a multi-row SELECT via SQLAlchemy and return a list of dicts."""
    sql, param_dict = _translate_to_named_params(sql, params)
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), param_dict)
        rows = result.fetchall()
        return [d for r in rows if (d := _orm_to_dict(r)) is not None]


def executemany(sql: str, params_list: list) -> int:
    """Execute a statement against multiple parameter sets via SQLAlchemy."""
    with get_engine().connect() as conn:
        total = 0
        for params in params_list:
            sql_inner, param_dict = _translate_to_named_params(sql, params)
            result = conn.execute(text(sql_inner), param_dict)
            total += result.rowcount or 0
        conn.commit()
        return total


# ──────────────────────────────────────────────────────────────
# Health / Readiness helpers
# ──────────────────────────────────────────────────────────────

def _db_is_file() -> bool:
    """Return True if the current SQLite backend uses an on-disk file."""
    return (
        DB_BACKEND == "sqlite"
        and DB_PATH_OR_URL != ":memory:"
        and not DB_PATH_OR_URL.startswith("file::memory:")
    )


def _orm_to_dict(row: Any) -> dict[str, Any] | None:
    """Convert an ORM result or dict to a plain dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    # SQLAlchemy 2.0 Row objects
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return dict(mapping)
    d = {}
    for key in getattr(row, "_fields", ()):
        d[key] = getattr(row, key)
    if not d and hasattr(row, "__dict__"):
        d = dict(row.__dict__)
        d.pop("_sa_instance_state", None)
    return d


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
        # PostgreSQL additive fields
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
        with get_engine().connect() as conn:
            # connected
            conn.execute(text("SELECT 1"))
            result["dbConnected"] = True

            # journal mode (SQLite only)
            if DB_BACKEND == "sqlite":
                row = conn.execute(text("PRAGMA journal_mode")).fetchone()
                if row:
                    result["journalMode"] = row[0]

            # writable — use a TEMP table so no persistent schema change
            if DB_BACKEND == "postgres":
                conn.execute(text("CREATE TEMP TABLE _gl032_health_probe (id INTEGER)"))
                conn.execute(text("INSERT INTO _gl032_health_probe VALUES (1)"))
                conn.execute(text("DROP TABLE _gl032_health_probe"))
            else:
                conn.execute(text("CREATE TEMP TABLE _gl032_health_probe (id INTEGER)"))
                conn.execute(text("INSERT INTO _gl032_health_probe VALUES (1)"))
                conn.execute(text("DROP TABLE _gl032_health_probe"))
            result["dbWritable"] = True

            # PostgreSQL version (available without elevated privileges)
            if DB_BACKEND == "postgres":
                try:
                    row = conn.execute(text("SELECT version()")).fetchone()
                    if row:
                        # version() returns e.g. "PostgreSQL 16.2 on ..."
                        version_str = row[0] if isinstance(row, dict) else row[0]
                        if version_str.startswith("PostgreSQL "):
                            result["pgVersion"] = version_str.split(" ")[1]
                except Exception:
                    pass

                # Backend PID (no elevated privileges needed)
                try:
                    row = conn.execute(text("SELECT pg_backend_pid()")).fetchone()
                    if row:
                        result["pgBackendPid"] = row[0] if isinstance(row, dict) else row[0]
                except Exception:
                    pass

                # Active connections count (no elevated privileges needed for pg_stat_activity)
                try:
                    row = conn.execute(
                        text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                    ).fetchone()
                    if row:
                        result["pgActiveConnections"] = row[0] if isinstance(row, dict) else row[0]
                except Exception:
                    pass
    except Exception:
        pass

    return result
