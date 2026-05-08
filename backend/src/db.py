"""GrantLayer MVP — SQLite database setup."""

import os
import sqlite3
from urllib.parse import urlparse

from . import migrations


def _parse_database_url(url: str) -> str:
    """Parse a database URL and return a SQLite path or raise for unsupported schemes."""
    parsed = urlparse(url)

    if parsed.scheme in ("postgres", "postgresql"):
        raise RuntimeError("PostgreSQL is not supported yet in GL-033")

    if parsed.scheme != "sqlite":
        raise RuntimeError(f"Unsupported database URL scheme: {parsed.scheme}")

    # sqlite:///absolute/path or sqlite:///:memory:
    if url.startswith("sqlite:///"):
        path = url[10:]
        if path == ":memory:":
            return ":memory:"
        return "/" + path
    # sqlite://relative/path or sqlite://:memory:
    elif url.startswith("sqlite://"):
        return url[9:]
    # sqlite:relative/path or sqlite::memory:
    elif url.startswith("sqlite:"):
        return url[7:]
    else:
        return url


def _resolve_db_path() -> str:
    """Resolve database path from env vars with precedence: DATABASE_URL > DB > default."""
    url = os.environ.get("GRANTLAYER_DATABASE_URL", "")
    if url:
        return _parse_database_url(url)
    legacy = os.environ.get("GRANTLAYER_DB", "")
    if legacy:
        return legacy
    return os.path.join(os.path.dirname(__file__), "../../data/grantlayer.db")


DB_PATH = _resolve_db_path()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    if DB_PATH != ":memory:" and not DB_PATH.startswith("file::memory:"):
        db_dir = os.path.dirname(os.path.abspath(DB_PATH))
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
# Health / Readiness helpers (GL-032)
# ──────────────────────────────────────────────────────────────

def _db_is_file() -> bool:
    """Return True if DB_PATH points to an on-disk file (not :memory:)."""
    return DB_PATH != ":memory:" and not DB_PATH.startswith("file::memory:")


def get_db_health() -> dict:
    """Return safe, additive readiness fields for the SQLite backend.

    No absolute paths, no raw dbPath values, no secrets.
    """
    result: dict = {
        "dbConnected": False,
        "dbWritable": False,
        "dbFilePresent": False,
        "dbDirectoryWritable": False,
        "dbSizeBytes": None,
        "journalMode": None,
        "dbPathKind": "file" if _db_is_file() else "memory",
    }

    # dbFilePresent / dbSizeBytes
    if _db_is_file():
        try:
            result["dbFilePresent"] = os.path.isfile(DB_PATH)
            if result["dbFilePresent"]:
                result["dbSizeBytes"] = os.path.getsize(DB_PATH)
        except OSError:
            pass

    # dbDirectoryWritable
        try:
            db_dir = os.path.dirname(os.path.abspath(DB_PATH))
            result["dbDirectoryWritable"] = os.access(db_dir, os.W_OK)
        except OSError:
            pass

    # dbConnected + journalMode + dbWritable
    try:
        conn = get_conn()
        try:
            # connected
            conn.execute("SELECT 1")
            result["dbConnected"] = True

            # journal mode
            row = conn.execute("PRAGMA journal_mode").fetchone()
            if row:
                result["journalMode"] = row[0]

            # writable — use a TEMP table so no persistent schema change
            conn.execute("CREATE TEMP TABLE _gl032_health_probe (id INTEGER)")
            conn.execute("INSERT INTO _gl032_health_probe VALUES (1)")
            conn.execute("DROP TABLE _gl032_health_probe")
            result["dbWritable"] = True
        finally:
            conn.close()
    except Exception:
        pass

    return result
