"""GL-032 — Production Readiness & Persistent Storage Baseline tests.

Covers:
1. Log level defaults to INFO and rejects invalid values
2. Health probe DB timeout defaults to 2000 ms
3. startup_warnings() never contains secret values
4. get_db_health() returns consistent structure for file DB
5. get_db_health() returns consistent structure for memory DB
6. /health response contains new readiness fields and no secrets
7. /health does not leak dbPath or absolute paths
8. Safe logging / safe error output (no token leakage in health)
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGL032ProductionReadiness(unittest.TestCase):
    """GL-032 production readiness hardening tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_log_level = os.environ.get("GRANTLAYER_LOG_LEVEL")
        self._orig_health_timeout = os.environ.get("GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for key, orig in [
            ("GRANTLAYER_LOG_LEVEL", self._orig_log_level),
            ("GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS", self._orig_health_timeout),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ──────────────────────────────────────────────
    # 1. Log level defaults to INFO
    # ──────────────────────────────────────────────
    def test_log_level_defaults_to_info(self):
        os.environ.pop("GRANTLAYER_LOG_LEVEL", None)
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_LOG_LEVEL, "INFO")

    # ──────────────────────────────────────────────
    # 2. Invalid log level falls back to default
    # ──────────────────────────────────────────────
    def test_log_level_rejects_invalid_value(self):
        os.environ["GRANTLAYER_LOG_LEVEL"] = "VERBOSE"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_LOG_LEVEL, "INFO")

    # ──────────────────────────────────────────────
    # 3. Valid log levels are accepted
    # ──────────────────────────────────────────────
    def test_log_level_accepts_valid_values(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            os.environ["GRANTLAYER_LOG_LEVEL"] = level
            importlib.reload(self.config_mod)
            self.assertEqual(self.config_mod.GRANTLAYER_LOG_LEVEL, level)

    # ──────────────────────────────────────────────
    # 4. Health probe DB timeout defaults to 2000
    # ──────────────────────────────────────────────
    def test_health_probe_timeout_defaults_to_2000(self):
        os.environ.pop("GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS", None)
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS, 2000)

    # ──────────────────────────────────────────────
    # 5. Health probe DB timeout accepts override
    # ──────────────────────────────────────────────
    def test_health_probe_timeout_override(self):
        os.environ["GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS"] = "5000"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS, 5000)

    # ──────────────────────────────────────────────
    # 6. startup_warnings() never contains secret values
    # ──────────────────────────────────────────────
    def test_startup_warnings_no_secret_values(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-token-xyz"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        importlib.reload(self.config_mod)
        warnings = self.config_mod.startup_warnings()
        warnings_text = "\n".join(warnings)
        self.assertNotIn("super-secret-token-xyz", warnings_text)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN=", warnings_text)

    # ──────────────────────────────────────────────
    # 7. get_db_health() returns consistent structure for file DB
    # ──────────────────────────────────────────────
    def test_get_db_health_file_db_structure(self):
        health = self.db_mod.get_db_health()
        self.assertIn("dbConnected", health)
        self.assertIn("dbWritable", health)
        self.assertIn("dbFilePresent", health)
        self.assertIn("dbDirectoryWritable", health)
        self.assertIn("dbSizeBytes", health)
        self.assertIn("journalMode", health)
        self.assertIn("dbPathKind", health)

        self.assertTrue(health["dbConnected"])
        self.assertTrue(health["dbWritable"])
        self.assertTrue(health["dbFilePresent"])
        self.assertTrue(health["dbDirectoryWritable"])
        self.assertIsInstance(health["dbSizeBytes"], int)
        self.assertGreaterEqual(health["dbSizeBytes"], 0)
        self.assertEqual(health["journalMode"], "wal")
        self.assertEqual(health["dbPathKind"], "file")

    # ──────────────────────────────────────────────
    # 8. get_db_health() returns consistent structure for memory DB
    # ──────────────────────────────────────────────
    def test_get_db_health_memory_db_structure(self):
        # Point DB to :memory: temporarily
        orig_path = self.db_mod.DB_PATH_OR_URL
        orig_backend = self.db_mod.DB_BACKEND
        try:
            self.db_mod.DB_PATH_OR_URL = ":memory:"
            self.db_mod.DB_BACKEND = "sqlite"
            health = self.db_mod.get_db_health()
            self.assertEqual(health["dbPathKind"], "memory")
            self.assertFalse(health["dbFilePresent"])
            self.assertFalse(health["dbDirectoryWritable"])
            self.assertIsNone(health["dbSizeBytes"])
            # In-memory DB should still be connectable and writable
            self.assertTrue(health["dbConnected"])
            self.assertTrue(health["dbWritable"])
        finally:
            self.db_mod.DB_PATH_OR_URL = orig_path
            self.db_mod.DB_BACKEND = orig_backend

    # ──────────────────────────────────────────────
    # 9. /health response contains new readiness fields and no secrets
    # ──────────────────────────────────────────────
    def test_health_response_contains_new_fields(self):
        # Build a simulated health payload (mirrors server.py logic)
        from backend.src.auth.auth import admin_token_is_configured
        import backend.src.core.config as c
        importlib.reload(c)

        payload = {
            "ok": True,
            "service": "grantlayer-mvp",
            "dbConfigured": bool(c.GRANTLAYER_DB),
            "adminTokenConfigured": admin_token_is_configured(),
            "requireAdminToken": c.REQUIRE_ADMIN_TOKEN,
            "requireChallenge": c.REQUIRE_CHALLENGE,
            "demoEndpointsEnabled": c.ENABLE_DEMO_ENDPOINTS,
            "operatorModelEnabled": c.ENABLE_OPERATOR_MODEL,
            "operatorsConfigured": False,
        }
        payload.update(self.db_mod.get_db_health())

        payload_str = json.dumps(payload)
        self.assertIn("dbConnected", payload_str)
        self.assertIn("dbWritable", payload_str)
        self.assertIn("dbFilePresent", payload_str)
        self.assertIn("dbDirectoryWritable", payload_str)
        self.assertIn("dbSizeBytes", payload_str)
        self.assertIn("journalMode", payload_str)
        self.assertIn("dbPathKind", payload_str)

    # ──────────────────────────────────────────────
    # 10. /health does not leak dbPath or absolute paths
    # ──────────────────────────────────────────────
    def test_health_does_not_leak_path(self):
        health = self.db_mod.get_db_health()
        health_str = json.dumps(health)
        # Must not contain raw DB path or common path fragments
        self.assertNotIn(self.db_mod.DB_PATH_OR_URL, health_str)
        self.assertNotIn("grantlayer.db", health_str)
        self.assertNotIn("/paperclip", health_str)
        self.assertNotIn("/tmp", health_str)

    # ──────────────────────────────────────────────
    # 11. Safe logging — token not present in health payload
    # ──────────────────────────────────────────────
    def test_health_no_token_leakage(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "leak-me-not-42"
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)

        from backend.src.auth.auth import admin_token_is_configured
        payload = {
            "ok": True,
            "adminTokenConfigured": admin_token_is_configured(),
        }
        payload.update(self.db_mod.get_db_health())
        payload_str = json.dumps(payload)
        self.assertNotIn("leak-me-not-42", payload_str)

    # ──────────────────────────────────────────────
    # 12. startup_warnings() includes precise messages for unsafe defaults
    # ──────────────────────────────────────────────
    def test_startup_warnings_precise_unsafe_defaults(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        importlib.reload(self.config_mod)
        warnings = self.config_mod.startup_warnings()
        self.assertTrue(any("GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true" in w for w in warnings))
        self.assertTrue(any("GRANTLAYER_REQUIRE_ADMIN_TOKEN is not true" in w for w in warnings))
        self.assertTrue(any("GRANTLAYER_REQUIRE_CHALLENGE is not true" in w for w in warnings))
        self.assertTrue(any("GRANTLAYER_ADMIN_TOKEN is not set" in w for w in warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
