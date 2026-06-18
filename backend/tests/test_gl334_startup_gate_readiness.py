"""GL-334 — Fix bypassable startup gate and lying readiness probe.

Tests:
- startup_errors() runs inside lifespan (not only in __main__.py).
- /readiness probes DB and returns 503 when DB is down.
- /readiness returns 200 when DB is up.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


def _make_client():
    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestReadinessProbeDb(unittest.TestCase):
    def test_readiness_returns_200_when_db_is_up(self):
        """GET /readiness must return 200 when DB is reachable."""
        client = _make_client()
        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get("status"), "ready")
        self.assertEqual(body.get("checkType"), "readiness")

    def test_readiness_returns_503_when_db_is_down(self):
        """GET /readiness must return 503 when DB SELECT 1 fails (lying probe is fixed)."""
        from sqlalchemy.exc import OperationalError

        class _FakeConn:
            def execute(self, *a, **kw):
                raise OperationalError("fake", None, Exception("DB is down"))
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class _FakeEngine:
            def connect(self): return _FakeConn()

        with patch("backend.src.api.routers.health.get_engine", return_value=_FakeEngine()):
            client = _make_client()
            resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body.get("status"), "not_ready")
        self.assertEqual(body.get("errorCode"), "DEPENDENCY_UNAVAILABLE")

    def test_readiness_has_request_param(self):
        """readiness endpoint must accept request (needed for Redis probe)."""
        import inspect
        from backend.src.api.routers.health import readiness
        sig = inspect.signature(readiness)
        self.assertIn("request", sig.parameters)


class TestStartupGateInLifespan(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_raises_runtimeerror_for_production_config_errors(self):
        """Lifespan must raise RuntimeError when startup_errors() returns errors in production mode."""
        from backend.src.api.app import _lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()
        mock_app.state.start_time = 0

        with (
            patch("backend.src.api.app.config") as mock_config,
            patch("backend.src.api.app.init_db"),
            patch("backend.src.api.app.setup_telemetry"),
            patch("backend.src.api.app.instrument_fastapi"),
        ):
            mock_config.RUNTIME_MODE = "production"
            mock_config.startup_errors.return_value = ["ERROR: GRANTLAYER_ADMIN_TOKEN not set"]
            with self.assertRaises(RuntimeError) as ctx:
                async with _lifespan(mock_app):
                    pass
        self.assertIn("startup aborted", str(ctx.exception).lower())

    async def test_lifespan_does_not_raise_for_test_mode(self):
        """Lifespan must not raise RuntimeError in test mode even if startup_errors returns errors."""
        from backend.src.api.app import _lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()
        mock_app.state.start_time = 0

        with (
            patch("backend.src.api.app.config") as mock_config,
            patch("backend.src.api.app.init_db"),
            patch("backend.src.api.app.setup_telemetry"),
            patch("backend.src.api.app.instrument_fastapi"),
        ):
            mock_config.RUNTIME_MODE = "test"
            mock_config.startup_errors.return_value = ["ERROR: would be fatal in prod"]
            # Should NOT raise
            async with _lifespan(mock_app):
                pass

    async def test_lifespan_does_not_raise_for_local_mode(self):
        """Lifespan must not raise in local mode."""
        from backend.src.api.app import _lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()
        mock_app.state.start_time = 0

        with (
            patch("backend.src.api.app.config") as mock_config,
            patch("backend.src.api.app.init_db"),
            patch("backend.src.api.app.setup_telemetry"),
            patch("backend.src.api.app.instrument_fastapi"),
        ):
            mock_config.RUNTIME_MODE = "local"
            mock_config.startup_errors.return_value = ["ERROR: would be fatal in prod"]
            async with _lifespan(mock_app):
                pass

    def test_startup_gate_skipped_for_test_env(self):
        """Integration: startup gate does not fire in test environment."""
        client = _make_client()
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
