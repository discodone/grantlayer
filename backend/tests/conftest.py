# Set GRANTLAYER_RUNTIME_MODE=test before any backend.src.core.config import
# so the startup gate is skipped and production-mode defaults don't break tests.
# Individual tests that need a specific mode override this in setUp/tearDown.
import os as _os

_os.environ.setdefault("GRANTLAYER_RUNTIME_MODE", "test")

# ── Per-xdist-worker SQLite isolation ────────────────────────────────────────
# Under `pytest -n auto` every worker is a separate PROCESS, but with no
# GRANTLAYER_DATABASE_URL and no GRANTLAYER_DB they ALL resolve the same default
# SQLite file (backend/data/grantlayer.db). Concurrent provisioning/reads of that
# one file race -> "Baseline validation failed: missing table 'audit_events'" /
# "duplicate column" / "UNIQUE constraint failed: schema_migrations.version" /
# "database is locked", and the victim roams by scheduler nondeterminism. Give
# each worker its OWN temp file so the shared-file contention is structurally
# impossible and the suite is safe under `-n auto`.
#
# No-op when a real Postgres DSN is configured (that path must use the real DSN)
# or when the user set GRANTLAYER_DB themselves (respect the caller's choice).
#
# Timing subtlety: the xdist CONTROLLER runs this block first (no worker id ->
# "main") and sets GRANTLAYER_DB; each WORKER then INHERITS that env var. So a
# plain "skip if GRANTLAYER_DB is set" guard would make every worker reuse the
# controller's "main" file. We instead tag the value we set with a sentinel and
# RE-DERIVE the per-worker path in each worker from PYTEST_XDIST_WORKER, while
# still leaving a genuinely user-supplied GRANTLAYER_DB untouched. Not under
# xdist, PYTEST_XDIST_WORKER is unset -> the single "main" file (identical to the
# historical single-process behaviour, just relocated to tmp).
_GL_MANAGED_DB = "_GL_MANAGED_WORKER_DB"
if not _os.environ.get("GRANTLAYER_DATABASE_URL") and (
    not _os.environ.get("GRANTLAYER_DB") or _os.environ.get(_GL_MANAGED_DB)
):
    import tempfile as _tempfile

    _xdist_worker = _os.environ.get("PYTEST_XDIST_WORKER", "main")
    # A per-worker DIRECTORY holding a file literally named grantlayer.db: keeps
    # the basename == the historical default so path-assertion tests
    # (endswith("grantlayer.db")) still hold, while the parent dir makes it unique
    # per worker.
    _worker_dir = _os.path.join(
        _tempfile.gettempdir(), f"grantlayer-test-{_xdist_worker}"
    )
    _os.makedirs(_worker_dir, exist_ok=True)
    _worker_db = _os.path.join(_worker_dir, "grantlayer.db")
    _os.environ["GRANTLAYER_DB"] = _worker_db
    _os.environ[_GL_MANAGED_DB] = "1"  # inherited by workers -> re-derive there
    # Start each session from a clean per-worker file so a stale schema from a
    # previous run can't fail baseline validation. Unique name per worker => no
    # cross-worker contention here. (It is re-provisioned by
    # _sqlite_provision_worker_db before the first test runs.)
    for _sfx in ("", "-wal", "-shm"):
        try:
            _os.remove(_worker_db + _sfx)
        except OSError:
            pass
    # If the db module was already imported (e.g. in a worker that inherited a
    # stale controller path), its module-level DB_PATH_OR_URL is stale; reload it
    # so it picks up the per-worker path. Common case (first import happens later)
    # reads the env directly, no reload.
    import sys as _sys

    if "backend.src.core.db" in _sys.modules:
        import importlib as _importlib

        _importlib.reload(_sys.modules["backend.src.core.db"])

"""
Pytest configuration for GrantLayer backend tests.

Auto-marks doc-guard and scope-guard tests so the suites can be run
independently:

  pytest -m "not doc_guard and not scope_guard"
  pytest                       # all tests (~9 400 tests, includes doc-guards)

Doc-guard tests verify that documentation artifacts (Markdown files, JSON
evidence bundles, scope-guard invariants) exist and contain the expected
content. They are correct and useful but do NOT exercise application code,
so they should not be counted when assessing functional test coverage.

The canonical module list lives in _doc_guard_modules.py so it can be
imported by both this conftest and the standalone runner script.
"""

try:
    import pytest

    from ._doc_guard_modules import DOC_GUARD_MODULES
    from ._sqlite_only_modules import SQLITE_ONLY_MODULES

    def _is_scope_guard_item(item) -> bool:
        item_name = item.name.lower()
        class_name = item.cls.__name__.lower() if item.cls is not None else ""
        return (
            "scopeguard" in class_name
            or "scope_guard" in class_name
            or "forbiddenchange" in class_name
            or "forbidden_change" in class_name
            or "noforbidden" in class_name
            or "no_forbidden" in class_name
            or "scopeguard" in item_name
            or "scope_guard" in item_name
            or "branch_scope_guard" in item_name
            or "changed_files" in item_name
            or "forbidden_files" in item_name
            or "forbidden_paths" in item_name
            or "forbidden_changes" in item_name
            or "no_backend_src" in item_name
            or "no_openapi" in item_name
            or "no_migration" in item_name
            or "no_dependency" in item_name
            or "no_github_workflow" in item_name
            or "no_frontend" in item_name
            or "no_production_deployment_config" in item_name
            or item_name in {
                "test_no_production_code_changed",
                "test_no_backend_src_changes",
            }
        )

    def pytest_collection_modifyitems(items: list) -> None:
        doc_guard_mark = pytest.mark.doc_guard
        scope_guard_mark = pytest.mark.scope_guard
        sqlite_only_mark = pytest.mark.sqlite_only
        for item in items:
            module_name = item.module.__name__.split(".")[-1]
            if module_name in DOC_GUARD_MODULES:
                item.add_marker(doc_guard_mark)
            if module_name in SQLITE_ONLY_MODULES:
                item.add_marker(sqlite_only_mark)
            if _is_scope_guard_item(item):
                item.add_marker(scope_guard_mark)

    # ──────────────────────────────────────────────────────────────
    # Per-test PostgreSQL isolation
    # ──────────────────────────────────────────────────────────────
    # On SQLite each test gets a fresh temp DB (GRANTLAYER_DB + reload), so it is
    # naturally isolated. On the PostgreSQL CI job GRANTLAYER_DATABASE_URL takes
    # precedence over GRANTLAYER_DB (intentionally — it points the suite at real
    # Postgres), so the per-test temp-SQLite isolation is a no-op and every test
    # shares ONE database with no cleanup. Prior tests' rows then leak in and can
    # flip results (e.g. an unlimited grant making an over-limit case approve).
    #
    # The app acquires connections through three independent sources (raw
    # get_conn() psycopg2 pool, sync SQLAlchemy engine, async asyncpg engine), so
    # transactional-rollback isolation is not feasible: there is no single shared
    # connection to wrap, and asyncpg cannot join a psycopg2 transaction. TRUNCATE
    # is connection-source-agnostic — it resets the one physical database that all
    # three sources read (READ COMMITTED), making Postgres behave like SQLite's
    # fresh-DB-per-test. Real Postgres is preserved; there is no SQLite fallback.

    # Migration bookkeeping must survive truncation so the schema is not dropped.
    _APP_TABLES_SKIP = {"schema_migrations"}

    # Migration-seeded reference data (the canonical demo workspace from migration
    # 0011) is created ONCE at schema-init time. On SQLite each test re-runs
    # migrations on a fresh temp DB, so that row is always present; truncating it
    # on PostgreSQL without restoring would diverge from the SQLite baseline and
    # 500 any code that resolves the demo workspace. We snapshot the seeded rows
    # once and re-insert them after every truncate, so each test starts from the
    # exact same baseline SQLite gets from a fresh migrated database.
    _PG_SEED_ROWS: dict = {}

    def _is_real_postgres(_db) -> bool:
        # The suite is running against real PostgreSQL ONLY when the backend is
        # "postgres" AND the resolved path/DSN is an actual postgres URL. A test
        # that self-provisions SQLite (importlib.reload(db) + GRANTLAYER_DB) can
        # leave DB_BACKEND == "postgres" (set once by the CI env) while
        # DB_PATH_OR_URL now points at a temp .db file. Guarding on the backend
        # string alone then hands that SQLite path to psycopg2 → "invalid dsn".
        # Requiring the URL scheme too makes that impossible.
        url = str(getattr(_db, "DB_PATH_OR_URL", "") or "")
        return (
            getattr(_db, "DB_BACKEND", None) == "postgres"
            and url.startswith(("postgres://", "postgresql://"))
        )

    # ── Belt-and-suspenders: canonical PG module-global snapshot/restore ──
    # The guard above stops psycopg2 from ever receiving a bad DSN. This
    # captures the canonical real-PG routing globals once at session start and
    # restores them after every test, so a test that reloads or repoints the db
    # module cannot leak a stale pointer (SQLite temp path, torn engine cache)
    # into the next test even cosmetically. No-op unless the suite is actually
    # running against real PostgreSQL — SQLite local/unit behaviour is unchanged.
    _DB_GLOBALS_TO_RESTORE = (
        "DB_BACKEND",
        "DB_PATH_OR_URL",
        "DB_PATH",
        "_sa_engine",
        "_engine_url",
        "_pg_pool",
        "_session_maker",
        "_session_maker_engine",
        "_async_engine",
        "_async_engine_url",
        "_async_session_maker",
        "_async_session_maker_engine",
    )
    _AUDIT_LOG_BACKEND_KEY = "__audit_log_DB_BACKEND"
    _PG_DB_GLOBALS: dict = {}

    # SQLite-mode counterpart of the PG snapshot/restore above. Captured once
    # (from the per-worker default set at import) and used by
    # _sqlite_reset_engine_cache to null the engine caches and restore the
    # canonical routing after every SQLite test, so a test that repoints
    # DB_PATH_OR_URL / swaps _sa_engine and forgets to restore cannot leak a
    # stale (temp-file) engine into a sibling test in the same worker.
    _SQLITE_BASELINE: dict = {}
    _SQLITE_ENGINE_CACHE_GLOBALS = (
        "_sa_engine",
        "_engine_url",
        "_session_maker",
        "_session_maker_engine",
        "_async_engine",
        "_async_engine_url",
        "_async_session_maker",
        "_async_session_maker_engine",
    )
    _SQLITE_ROUTING_GLOBALS = ("DB_BACKEND", "DB_PATH_OR_URL", "DB_PATH")

    def _restore_pg_db_globals():
        # No-op when the snapshot was never taken (SQLite mode).
        if not _PG_DB_GLOBALS:
            return
        import backend.src.core.db as _db

        for attr, value in _PG_DB_GLOBALS.items():
            if attr == _AUDIT_LOG_BACKEND_KEY:
                # audit_log.py takes an import-time copy of DB_BACKEND
                # (from ..core.db import DB_BACKEND) that does not track later
                # reloads of db, so restore it explicitly.
                try:
                    import backend.src.audit.audit_log as _al

                    _al.DB_BACKEND = value
                except Exception:
                    pass
                continue
            setattr(_db, attr, value)

    def _pg_app_tables(conn):
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        return [r["tablename"] for r in rows if r["tablename"] not in _APP_TABLES_SKIP]

    @pytest.fixture(scope="session", autouse=True)
    def _sqlite_provision_worker_db():
        # Provision the per-worker SQLite file ONCE, before any test runs, so
        # non-self-provisioning tests find a migrated schema regardless of xdist
        # scheduling. Historically these tests relied on the committed
        # backend/data/grantlayer.db always being present and provisioned; the
        # per-worker file (set at import) starts EMPTY, so without this a test
        # whose worker hadn't yet run an init_db()-triggering sibling would hit
        # "no such table: audit_events" — the roaming flake this fix targets.
        # No-op in real-Postgres mode (schema is provisioned by the CI job).
        import backend.src.core.db as _db

        if not _is_real_postgres(_db):
            try:
                _db.init_db()
            except Exception:
                pass
        yield

    @pytest.fixture(scope="session", autouse=True)
    def _pg_capture_seed_rows():
        # Capture migration-seeded reference rows BEFORE any test runs (CI
        # initialises the schema before pytest). No-op / best-effort otherwise.
        import backend.src.core.db as _db

        if _is_real_postgres(_db):
            # Snapshot the canonical real-PG routing globals once, for the
            # per-test restore (belt-and-suspenders against leaked pointers).
            for attr in _DB_GLOBALS_TO_RESTORE:
                if hasattr(_db, attr):
                    _PG_DB_GLOBALS[attr] = getattr(_db, attr)
            try:
                import backend.src.audit.audit_log as _al

                _PG_DB_GLOBALS[_AUDIT_LOG_BACKEND_KEY] = _al.DB_BACKEND
            except Exception:
                pass
            try:
                conn = _db.get_conn()
                try:
                    for t in _pg_app_tables(conn):
                        rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
                        if rows:
                            _PG_SEED_ROWS[t] = [dict(r) for r in rows]
                finally:
                    conn.close()
            except Exception:
                pass  # schema not ready yet → restore is a harmless no-op
        yield

    @pytest.fixture(autouse=True)
    def _pg_clean_between_tests(request):
        # Post-test (yield → truncate): ordering-independent w.r.t. unittest
        # setUp/tearDown; the next test's setUp seeds into a clean database,
        # exactly like SQLite handing it a fresh temp file.
        yield

        # (1) Restore the canonical PG module globals FIRST — before the guard
        #     and the truncate below — so a test that reloaded or repointed db
        #     can't leak a stale pointer forward AND so the truncate runs
        #     against the real PG connection (not a leaked SQLite path). No-op
        #     in SQLite mode (snapshot never taken).
        _restore_pg_db_globals()

        import backend.src.core.db as _db

        # SQLite path is untouched → byte-for-byte zero change for local/CI-unit.
        # Guard on the URL scheme too: never hand a non-postgres DSN to psycopg2.
        if not _is_real_postgres(_db):
            return
        # Opt-out for classes that seed shared data in setUpClass.
        if request.node.get_closest_marker("no_db_truncate"):
            return

        conn = _db.get_conn()
        try:
            tables = _pg_app_tables(conn)
            if tables:
                quoted = ", ".join(f'"{t}"' for t in tables)
                conn.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
            # Restore migration-seeded reference rows (e.g. the demo workspace).
            for table, rows in _PG_SEED_ROWS.items():
                for row in rows:
                    cols = list(row.keys())
                    collist = ", ".join(f'"{c}"' for c in cols)
                    placeholders = ", ".join("?" for _ in cols)
                    conn.execute(
                        f'INSERT INTO "{table}" ({collist}) VALUES ({placeholders})',
                        tuple(row[c] for c in cols),
                    )
            conn.commit()
        finally:
            conn.close()

    @pytest.fixture(autouse=True)
    def _sqlite_reset_engine_cache():
        # SQLite-mode per-test engine-cache reset (mirror of _pg_clean_between_tests).
        # PG mode is fully handled by _pg_clean_between_tests and left byte-for-byte
        # unchanged here (both guards below return early when real Postgres is
        # configured). Capture the canonical per-worker routing once, before any
        # test's setUp has run.
        import backend.src.core.db as _db

        if not _SQLITE_BASELINE and not _is_real_postgres(_db):
            for attr in _SQLITE_ROUTING_GLOBALS:
                if hasattr(_db, attr):
                    _SQLITE_BASELINE[attr] = getattr(_db, attr)
        yield
        # Nothing to restore in real-PG mode or before the baseline was captured.
        if _is_real_postgres(_db) or not _SQLITE_BASELINE:
            return
        # Dispose the cached sync engine (release the SQLite file handle) then null
        # every engine-cache global so the next test rebuilds cleanly, and restore
        # the canonical per-worker routing so a leaked temp-file pointer can't roll
        # forward. Async engines are nulled (not disposed — dispose is a coroutine;
        # GC closes them) to avoid touching the event loop from a sync fixture.
        _eng = getattr(_db, "_sa_engine", None)
        if _eng is not None:
            try:
                _eng.dispose()
            except Exception:
                pass
        for attr in _SQLITE_ENGINE_CACHE_GLOBALS:
            if hasattr(_db, attr):
                setattr(_db, attr, None)
        for attr, value in _SQLITE_BASELINE.items():
            setattr(_db, attr, value)

    @pytest.fixture(autouse=True)
    def _reset_leaked_runtime_mode():
        # app.py's lifespan fail-closes when config.RUNTIME_MODE is not
        # "test"/"local". RUNTIME_MODE is module state derived from
        # GRANTLAYER_RUNTIME_MODE at import; the gate DEFAULTS to "production"
        # when that env var is unset, so a prior test that popped/overrode it and
        # reloaded config can leave the module flag at "production". That was
        # inert until tests began entering the TestClient context (which runs the
        # lifespan and its startup gate). If the environment says test/local but
        # the config module drifted, reset the flag BEFORE this test runs so an
        # unrelated leak cannot abort a lifespan startup. Tests that genuinely
        # need production mode set it in their own setUp, which runs after this.
        env_mode = _os.environ.get("GRANTLAYER_RUNTIME_MODE", "test")
        if env_mode in ("test", "local"):
            try:
                import backend.src.core.config as _cfg

                if getattr(_cfg, "RUNTIME_MODE", "test") not in ("test", "local"):
                    _cfg.RUNTIME_MODE = env_mode
                # Reconciling RUNTIME_MODE alone leaves the flags whose defaults are
                # keyed on it (GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE,
                # REQUIRE_ADMIN_TOKEN) at their stale production values, which then
                # roam forward (grant signing refused / admin token wrongly forced).
                # Re-derive that whole class from the reconciled mode.
                if hasattr(_cfg, "recompute_mode_derived_flags"):
                    _cfg.recompute_mode_derived_flags()
            except Exception:
                pass
        yield

except ImportError:
    pass  # pytest not installed; conftest is a no-op in that environment
