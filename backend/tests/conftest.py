# Set GRANTLAYER_RUNTIME_MODE=test before any backend.src.core.config import
# so the startup gate is skipped and production-mode defaults don't break tests.
# Individual tests that need a specific mode override this in setUp/tearDown.
import os as _os
_os.environ.setdefault("GRANTLAYER_RUNTIME_MODE", "test")

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
        for item in items:
            module_name = item.module.__name__.split(".")[-1]
            if module_name in DOC_GUARD_MODULES:
                item.add_marker(doc_guard_mark)
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

    def _pg_app_tables(conn):
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        return [r["tablename"] for r in rows if r["tablename"] not in _APP_TABLES_SKIP]

    @pytest.fixture(scope="session", autouse=True)
    def _pg_capture_seed_rows():
        # Capture migration-seeded reference rows BEFORE any test runs (CI
        # initialises the schema before pytest). No-op / best-effort otherwise.
        import backend.src.core.db as _db

        if getattr(_db, "DB_BACKEND", None) == "postgres":
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

        import backend.src.core.db as _db

        # SQLite path is untouched → byte-for-byte zero change for local/CI-unit.
        if getattr(_db, "DB_BACKEND", None) != "postgres":
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

except ImportError:
    pass  # pytest not installed; conftest is a no-op in that environment
