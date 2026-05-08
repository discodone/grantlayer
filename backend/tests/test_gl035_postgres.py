"""GL-035 — PostgreSQL Deployment Hardening & Operational Verification.

Covers:
1. Docker Compose override file exists and has expected content
2. Environment variables for PostgreSQL are recognized (retry, password)
3. get_db_health() includes pgVersion / pgBackendPid / pgActiveConnections for PostgreSQL
4. Bounded retry on PostgreSQL connection failures
5. Secret safety: DSN/password never exposed in health, logs, exceptions
6. SQLite remains default when GRANTLAYER_DATABASE_URL is unset
7. Invalid DB URLs fail clearly without leaking secrets
"""

import os
import sys
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDockerComposePostgres(unittest.TestCase):
    """GL-035 Docker Compose PostgreSQL override file validation."""

    def test_postgres_compose_file_exists(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "docker-compose.postgres.yml")
        self.assertTrue(os.path.isfile(path))

    def test_postgres_compose_contains_expected_sections(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "docker-compose.postgres.yml")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("services:", content)
        self.assertIn("db:", content)
        self.assertIn("api:", content)
        self.assertIn("volumes:", content)
        self.assertIn("networks:", content)

    def test_postgres_compose_db_service_uses_postgres_image(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "docker-compose.postgres.yml")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("image: postgres:16-alpine", content)

    def test_postgres_compose_api_depends_on_db_healthcheck(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "docker-compose.postgres.yml")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("depends_on:", content)
        self.assertIn("condition: service_healthy", content)

    def test_postgres_compose_api_uses_postgres_url(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "docker-compose.postgres.yml")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_DATABASE_URL=postgres://", content)


class TestPostgresEnvironmentVariables(unittest.TestCase):
    """GL-035 PostgreSQL env vars are recognized by config."""

    def test_postgres_password_in_dot_env_example(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, ".env.example")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_POSTGRES_PASSWORD", content)

    def test_retry_max_in_dot_env_example(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, ".env.example")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_DB_RETRY_MAX", content)

    def test_retry_delay_in_dot_env_example(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, ".env.example")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_DB_RETRY_DELAY", content)


class TestPostgresHealthFields(unittest.TestCase):
    """GL-035 PostgreSQL health fields appear with simulated backend."""

    def test_health_postgres_struct_has_new_fields(self):
        import src.db as db_mod
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://localhost/test"
            health = db_mod.get_db_health()
            self.assertIn("pgVersion", health)
            self.assertIn("pgBackendPid", health)
            self.assertIn("pgActiveConnections", health)
            # Defaults are None when not connected
            self.assertIsNone(health["pgVersion"])
            self.assertIsNone(health["pgBackendPid"])
            self.assertIsNone(health["pgActiveConnections"])
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url


class TestPostgresBoundedRetry(unittest.TestCase):
    """GL-035 bounded retry on PostgreSQL connection failures."""

    def test_retry_max_defaults_to_five(self):
        import src.db as db_mod
        self.assertEqual(db_mod._db_retry_max, 5)

    def test_retry_delay_defaults_to_one_second(self):
        import src.db as db_mod
        self.assertEqual(db_mod._db_retry_delay, 1.0)

    def test_retry_max_env_override(self):
        """GRANTLAYER_DB_RETRY_MAX env var is respected."""
        orig = os.environ.get("GRANTLAYER_DB_RETRY_MAX")
        os.environ["GRANTLAYER_DB_RETRY_MAX"] = "3"
        try:
            import src.db as db_mod
            importlib.reload(db_mod)
            self.assertEqual(db_mod._db_retry_max, 3)
        finally:
            if orig is not None:
                os.environ["GRANTLAYER_DB_RETRY_MAX"] = orig
            else:
                os.environ.pop("GRANTLAYER_DB_RETRY_MAX", None)
            importlib.reload(db_mod)

    def test_retry_delay_env_override(self):
        """GRANTLAYER_DB_RETRY_DELAY env var is respected."""
        orig = os.environ.get("GRANTLAYER_DB_RETRY_DELAY")
        os.environ["GRANTLAYER_DB_RETRY_DELAY"] = "2.5"
        try:
            import src.db as db_mod
            importlib.reload(db_mod)
            self.assertEqual(db_mod._db_retry_delay, 2.5)
        finally:
            if orig is not None:
                os.environ["GRANTLAYER_DB_RETRY_DELAY"] = orig
            else:
                os.environ.pop("GRANTLAYER_DB_RETRY_DELAY", None)
            importlib.reload(db_mod)

    def test_postgres_connection_raises_after_retries(self):
        """When PostgreSQL is unreachable, get_conn raises after max retries."""
        import src.db as db_mod
        importlib.reload(db_mod)

        try:
            import psycopg2
        except ImportError:
            self.skipTest("psycopg2 is not installed")

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_max = db_mod._db_retry_max

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://localhost:19999/nonexistent"
            db_mod._db_retry_max = 2
            db_mod._db_retry_delay = 0.05  # keep test fast

            with self.assertRaises(RuntimeError) as ctx:
                db_mod.get_conn()
            msg = str(ctx.exception)
            self.assertIn("PostgreSQL connection failed after 2 attempt(s)", msg)
            self.assertIn("Check that the server is reachable", msg)
            # Ensure no DSN/password in the error
            self.assertNotIn("postgres://", msg)
            self.assertNotIn("nonexistent", msg)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._db_retry_max = orig_max
            db_mod._db_retry_delay = 1.0


class TestSecretSafety(unittest.TestCase):
    """GL-035 no DSN/password exposed in health, logs, exceptions."""

    def _health_never_contains(self, needle: str, backend: str, url: str):
        import src.db as db_mod
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = backend
            db_mod.DB_PATH_OR_URL = url
            health = db_mod.get_db_health()
            payload = str(health)
            self.assertNotIn(needle, payload)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_health_no_postgres_url(self):
        self._health_never_contains(
            "secret_password", "postgres", "postgres://user:secret_password@host/db"
        )

    def test_health_no_hostname(self):
        self._health_never_contains(
            "my-db-server.internal", "postgres", "postgres://user:pass@my-db-server.internal/db"
        )

    def test_health_no_dsn(self):
        self._health_never_contains(
            "postgres://", "postgres", "postgres://user:pass@host/db"
        )

    def test_exception_no_dsn_on_retry_exhaustion(self):
        import src.db as db_mod
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_max = db_mod._db_retry_max
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:secret_password@unreachable:19999/db"
            db_mod._db_retry_max = 1
            db_mod._db_retry_delay = 0.01

            try:
                import psycopg2
            except ImportError:
                self.skipTest("psycopg2 is not installed")

            with self.assertRaises(RuntimeError) as ctx:
                db_mod.get_conn()
            msg = str(ctx.exception)
            self.assertNotIn("secret_password", msg)
            self.assertNotIn("postgres://", msg)
            self.assertNotIn("unreachable", msg)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._db_retry_max = orig_max
            db_mod._db_retry_delay = 1.0


class TestSQLiteRemainsDefault(unittest.TestCase):
    """GL-035 SQLite is still the default when GRANTLAYER_DATABASE_URL is unset."""

    def test_default_backend_is_sqlite(self):
        import src.db as db_mod
        self.assertEqual(db_mod.DB_BACKEND, "sqlite")

    def test_default_db_path_is_file(self):
        import src.db as db_mod
        self.assertTrue(db_mod.DB_PATH_OR_URL.endswith("grantlayer.db"))

    def test_health_kind_is_file_for_default(self):
        import src.db as db_mod
        health = db_mod.get_db_health()
        self.assertEqual(health["dbPathKind"], "file")

    def test_sqlite_fallback_when_database_url_unset(self):
        """When GRANTLAYER_DATABASE_URL is unset, SQLite is used."""
        import src.db as db_mod
        importlib.reload(db_mod)
        self.assertEqual(db_mod.DB_BACKEND, "sqlite")


class TestInvalidUrlsFailCleanly(unittest.TestCase):
    """GL-035 invalid DB URLs fail without leaking secrets."""

    def test_unsupported_scheme_raises(self):
        from src.db import _parse_database_url
        with self.assertRaises(RuntimeError) as ctx:
            _parse_database_url("mysql://user:secret_password@host/db")
        msg = str(ctx.exception)
        self.assertIn("Unsupported", msg)
        self.assertNotIn("secret_password", msg)

    def test_empty_url_returns_sqlite(self):
        """Empty string is not an invalid URL per se; it's just not configured."""
        from src.db import _parse_database_url
        backend, path = _parse_database_url("")
        self.assertEqual(backend, "sqlite")


class TestAcceptanceScriptExists(unittest.TestCase):
    """GL-035 acceptance_postgres.sh exists and is executable."""

    def test_script_exists(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "scripts", "acceptance_postgres.sh")
        self.assertTrue(os.path.isfile(path), f"Script not found: {path}")

    def test_script_is_executable(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, "scripts", "acceptance_postgres.sh")
        self.assertTrue(os.access(path, os.X_OK), "Script is not executable")


class TestEnvExamplePostgresqlUrlComment(unittest.TestCase):
    """GL-035 .env.example contains PostgreSQL URL example."""

    def test_env_example_has_postgres_url(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, ".env.example")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_DATABASE_URL=postgres://", content)

    def test_env_example_has_postgres_password(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        path = os.path.join(repo_root, ".env.example")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GRANTLAYER_POSTGRES_PASSWORD", content)


class TestPostgresIntegrationWhenAvailable(unittest.TestCase):
    """GL-035 optional PostgreSQL integration test — skips if not available."""

    @classmethod
    def setUpClass(cls):
        cls.psycopg2_available = False
        cls.pg_url = os.environ.get("GRANTLAYER_DATABASE_URL", "")
        if not cls.pg_url:
            cls.pg_url = os.environ.get("GRANTLAYER_TEST_DATABASE_URL", "")
        if not cls.pg_url or not cls.pg_url.startswith("postgres"):
            raise unittest.SkipTest("No PostgreSQL test URL configured")
        try:
            import psycopg2
            conn = psycopg2.connect(cls.pg_url)
            conn.cursor().execute("SELECT 1")
            conn.close()
            cls.psycopg2_available = True
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL not reachable: {exc}")

    def test_postgres_fresh_initializes_schema(self):
        import src.db as db_mod
        importlib.reload(db_mod)
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            db_mod.init_db()
            with db_mod.get_conn() as conn:
                rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
                self.assertTrue(len(rows) >= 1)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_postgres_migrations_idempotent(self):
        import src.db as db_mod
        importlib.reload(db_mod)
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            db_mod.init_db()
            db_mod.init_db()
            with db_mod.get_conn() as conn:
                rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
                self.assertTrue(len(rows) >= 1)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_postgres_health_returns_pg_fields(self):
        import src.db as db_mod
        importlib.reload(db_mod)
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            health = db_mod.get_db_health()
            self.assertTrue(health["dbConnected"])
            self.assertTrue(health["dbWritable"])
            self.assertEqual(health["dbPathKind"], "postgres")
            self.assertIsNotNone(health["pgVersion"])
            self.assertRegex(health["pgVersion"], r"^\d+\.?\d*")
            self.assertIsNotNone(health["pgBackendPid"])
            self.assertIsInstance(health["pgBackendPid"], int)
            self.assertIsNotNone(health["pgActiveConnections"])
            self.assertIsInstance(health["pgActiveConnections"], int)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url


if __name__ == "__main__":
    unittest.main(verbosity=2)
