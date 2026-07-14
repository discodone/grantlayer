"""GL-299 — Operational Readiness Hardening tests.

Covers:
1. _q_to_named correctly converts ? positional placeholders (already in test_gl034)
2. startup_errors gate in __main__ (via config.startup_errors integration)
3. docker-compose defaults documented (RUNTIME_MODE=production, REQUIRE_ADMIN_TOKEN=true)
4. GRANTLAYER_JWT_STRICT_CLAIMS documented in DEPLOYMENT.md
5. Generic 500 exception handler returns structured JSON
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────
# FIX 1: _q_to_named (covered by test_gl034, tested here for doc-completeness)
# ──────────────────────────────────────────────────────────────

class TestQToNamedIntegration(unittest.TestCase):
    """Verify _q_to_named is exported and works end-to-end."""

    def test_exported_from_db(self):
        from backend.src.core.db import _q_to_named
        self.assertTrue(callable(_q_to_named))

    def test_no_custom_parsers_exported(self):
        """_translate_placeholders and _translate_to_named_params must not exist."""
        import backend.src.core.db as db_mod
        self.assertFalse(hasattr(db_mod, "_translate_placeholders"))
        self.assertFalse(hasattr(db_mod, "_translate_to_named_params"))

    def test_audit_log_does_not_import_translate(self):
        """audit_log must not import the removed parser."""
        import backend.src.audit.audit_log as al_mod
        self.assertFalse(hasattr(al_mod, "_translate_to_named_params"))

    def test_insert_sql_uses_named_params(self):
        """_INSERT_SQL must use :named params, not ? placeholders."""
        from backend.src.audit.audit_log import _INSERT_SQL
        self.assertNotIn("?", _INSERT_SQL)
        self.assertIn(":id", _INSERT_SQL)
        self.assertIn(":timestamp", _INSERT_SQL)

    def test_build_insert_params_returns_dict(self):
        """_build_insert_params must return a dict, not a tuple."""
        from backend.src.audit.audit_log import _build_insert_params
        from backend.src.core.models import AuditEvent
        event = AuditEvent(workspace_id="default",
            subject_id="s", role="r", action="a", resource="res",
            approved=True, reason="test",
        )
        params = _build_insert_params(event, "hash", None)
        self.assertIsInstance(params, dict)
        self.assertIn("id", params)
        self.assertIn("timestamp", params)
        self.assertIn("subject_id", params)


# ──────────────────────────────────────────────────────────────
# FIX 2: startup_errors integration (config gate)
# ──────────────────────────────────────────────────────────────

class TestStartupGate(unittest.TestCase):
    """startup_errors() is callable and used by __main__."""

    def test_startup_errors_callable_from_config(self):
        from backend.src.core.config import startup_errors
        self.assertTrue(callable(startup_errors))

    def test_startup_ok_callable(self):
        from backend.src.core.config import startup_ok
        self.assertTrue(callable(startup_ok))

    def test_main_imports_startup_errors_conditionally(self):
        """__main__.py must reference startup_errors in production mode guard."""
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "__main__.py"
        )
        with open(main_path) as f:
            source = f.read()
        self.assertIn("startup_errors", source)
        self.assertIn("sys.exit(1)", source)
        self.assertIn("SKIP_STARTUP_CHECK_MODES", source)

    def test_test_mode_skips_gate(self):
        """In test/local mode, startup gate must be skipped."""
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "__main__.py"
        )
        with open(main_path) as f:
            source = f.read()
        # Both 'test' and 'local' must be in the skip list
        self.assertIn('"test"', source)
        self.assertIn('"local"', source)


# ──────────────────────────────────────────────────────────────
# FIX 3: docker-compose.yml secure defaults
# ──────────────────────────────────────────────────────────────

class TestDockerComposeSecureDefaults(unittest.TestCase):
    """docker-compose.yml must default to production-safe settings."""

    def _read_compose(self):
        compose_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-compose.yml"
        )
        with open(compose_path) as f:
            return f.read()

    def test_runtime_mode_defaults_to_production(self):
        content = self._read_compose()
        self.assertIn("GRANTLAYER_RUNTIME_MODE", content)
        self.assertIn("production", content)

    def test_require_admin_token_defaults_to_true(self):
        content = self._read_compose()
        # Should NOT default to false
        self.assertNotIn("GRANTLAYER_REQUIRE_ADMIN_TOKEN:-false", content)
        self.assertIn("GRANTLAYER_REQUIRE_ADMIN_TOKEN:-true", content)

    def test_has_override_comment(self):
        content = self._read_compose()
        self.assertIn("Override with .env file", content)


# ──────────────────────────────────────────────────────────────
# FIX 4: DEPLOYMENT.md documents JWT_STRICT_CLAIMS
# ──────────────────────────────────────────────────────────────

class TestDeploymentMdJwtStrictClaims(unittest.TestCase):
    """DEPLOYMENT.md must document GRANTLAYER_JWT_STRICT_CLAIMS."""

    def _read_deployment_md(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "DEPLOYMENT.md"
        )
        with open(path) as f:
            return f.read()

    def test_jwt_strict_claims_in_table(self):
        content = self._read_deployment_md()
        self.assertIn("GRANTLAYER_JWT_STRICT_CLAIMS", content)

    def test_recommended_true_documented(self):
        content = self._read_deployment_md()
        # Must indicate true is recommended
        lower = content.lower()
        self.assertIn("jwt_strict_claims", lower)
        idx = lower.find("jwt_strict_claims")
        surrounding = lower[idx : idx + 200]
        self.assertIn("true", surrounding)


# ──────────────────────────────────────────────────────────────
# FIX 5: Generic 500 exception handler
# ──────────────────────────────────────────────────────────────

class TestGeneric500Handler(unittest.TestCase):
    """app.py generic Exception handler returns structured JSON."""

    def _make_app(self):
        from fastapi.testclient import TestClient

        from backend.src.api.app import create_app
        app = create_app()

        @app.get("/v1/test-500")
        def _raise_error():
            raise RuntimeError("deliberate test error")

        return TestClient(app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_500_json(self):
        client = self._make_app()
        resp = client.get("/v1/test-500")
        self.assertEqual(resp.status_code, 500)
        body = resp.json()
        self.assertIn("error", body)
        # GL-339: error body uses {error, errorCode, reason} not {error, message}
        self.assertIn("errorCode", body)
        self.assertIn("reason", body)

    def test_unhandled_exception_no_stack_trace_in_response(self):
        """Stack trace must NOT appear in the response body in test mode."""
        client = self._make_app()
        resp = client.get("/v1/test-500")
        body_text = resp.text
        # RuntimeError repr is allowed in local/test mode but traceback not
        self.assertNotIn("Traceback", body_text)
        self.assertNotIn("File ", body_text)

    def test_404_still_works_after_handler(self):
        client = self._make_app()
        resp = client.get("/v1/nonexistent-route-xyz")
        self.assertEqual(resp.status_code, 404)

    def test_handler_registered_in_app(self):
        """create_app() must register an Exception handler."""
        from backend.src.api.app import create_app
        app = create_app()
        handlers = app.exception_handlers
        self.assertIn(Exception, handlers)


# ──────────────────────────────────────────────────────────────
# GL-350b: CardanoConfig wired into the global startup gate
# ──────────────────────────────────────────────────────────────

class TestCardanoStartupGateIntegration(unittest.TestCase):
    """The global config.startup_errors() must surface CardanoConfig errors.

    Mirrors the OIDCConfig integration: config.startup_errors() extends with
    CardanoConfig.from_env().startup_errors() so an enabled-but-misconfigured
    anchoring setup refuses to boot (third fail-closed gate).
    """

    _CARDANO_KEYS = [
        "GRANTLAYER_ENABLE_CARDANO_ANCHORING",
        "GRANTLAYER_BLOCKFROST_PROJECT_ID",
        "GRANTLAYER_CARDANO_SIGNING_KEY",
        "GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID",
    ]

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self._CARDANO_KEYS}
        for k in self._CARDANO_KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_global_startup_errors_includes_cardano_when_enabled_misconfigured(self):
        from backend.src.core.config import startup_errors
        os.environ["GRANTLAYER_ENABLE_CARDANO_ANCHORING"] = "true"
        errs = startup_errors()
        assert any("GRANTLAYER_BLOCKFROST_PROJECT_ID" in e for e in errs), errs
        assert any("GRANTLAYER_CARDANO_SIGNING_KEY" in e for e in errs), errs
        assert any("GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID" in e for e in errs), errs

    def test_global_startup_errors_clean_when_cardano_disabled(self):
        from backend.src.core.config import startup_errors
        # anchoring disabled (default) → no Cardano entries in the global gate
        errs = startup_errors()
        assert not any("CARDANO" in e or "BLOCKFROST" in e for e in errs), errs


if __name__ == "__main__":
    unittest.main()
