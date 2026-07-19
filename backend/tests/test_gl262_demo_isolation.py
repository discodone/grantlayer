"""Tests for GL-262: Demo tamper-grant endpoint isolation via GRANTLAYER_ENABLE_DEMO_ENDPOINTS.

The tamper-grant endpoint lives in demo.tamper_router, which is only registered
when GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true.  The demo-action endpoint stays in
demo.router and is always registered.

Without flag: /v1/demo/tamper-grant/* → 404 (router not mounted).
With flag:    /v1/demo/tamper-grant/* → non-404 (405 for wrong method, 4xx for auth).
demo-action is always available regardless of the flag.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app(enable_demo: bool, admin_token: str = "gl262-admin-token") -> tuple:
    """Create an isolated app instance with demo flag set as specified."""
    tmp = tempfile.mktemp(suffix=".db")
    env_patch = {
        "GRANTLAYER_DB": tmp,
        "GRANTLAYER_ADMIN_TOKEN": admin_token,
        "GRANTLAYER_ENABLE_DEMO_ENDPOINTS": "true" if enable_demo else "false",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL": "false",
    }
    saved = {k: os.environ.get(k) for k in env_patch}
    os.environ.update(env_patch)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH_OR_URL = tmp
    db_mod.DB_PATH = tmp
    db_mod.init_db()

    import backend.src.core.config as cfg_mod
    importlib.reload(cfg_mod)

    import backend.src.api.app as app_mod
    importlib.reload(app_mod)

    return app_mod.app, saved


def _restore_env(saved: dict) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    # Reload config and app so module-level state is fully restored for subsequent
    # tests in the same worker process.
    import backend.src.core.config as cfg_mod
    importlib.reload(cfg_mod)
    import backend.src.api.app as app_mod
    importlib.reload(app_mod)


class TestTamperGrantDisabled(unittest.TestCase):
    """When GRANTLAYER_ENABLE_DEMO_ENDPOINTS is false, tamper-grant must be 404."""

    def test_tamper_grant_get_returns_404_without_flag(self):
        """GET /v1/demo/tamper-grant/x → 404 when demo is disabled (router not mounted)."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=False)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/v1/demo/tamper-grant/test-grant-id")
            self.assertEqual(resp.status_code, 404, resp.text)
        finally:
            _restore_env(saved)

    def test_tamper_grant_post_returns_404_without_flag(self):
        """POST /v1/demo/tamper-grant/x → 404 when demo is disabled."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=False)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/demo/tamper-grant/test-grant-id",
                headers={"Authorization": "Bearer gl262-admin-token"},
            )
            self.assertEqual(resp.status_code, 404, resp.text)
        finally:
            _restore_env(saved)


class TestTamperGrantEnabled(unittest.TestCase):
    """When GRANTLAYER_ENABLE_DEMO_ENDPOINTS is true, tamper-grant is reachable."""

    def test_tamper_grant_get_returns_not_404_with_flag(self):
        """GET /v1/demo/tamper-grant/x → 405 (not 404) when demo is enabled."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=True)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/v1/demo/tamper-grant/test-grant-id")
            self.assertNotEqual(resp.status_code, 404, resp.text)
        finally:
            _restore_env(saved)

    def test_tamper_grant_post_requires_auth_with_flag(self):
        """POST /v1/demo/tamper-grant/x returns auth error (not 404) when enabled."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=True)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/v1/demo/tamper-grant/test-grant-id")
            self.assertNotEqual(resp.status_code, 404, resp.text)
            self.assertIn(resp.status_code, {400, 401, 403, 422, 500}, resp.text)
        finally:
            _restore_env(saved)


class TestDemoActionAlwaysAvailable(unittest.TestCase):
    """demo-action is always registered, regardless of ENABLE_DEMO_ENDPOINTS."""

    def test_demo_action_reachable_without_flag(self):
        """POST /v1/exercise → not 404 even when ENABLE_DEMO_ENDPOINTS=false."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=False)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/exercise",
                json={"subjectId": "a", "role": "r", "action": "a", "resource": "r"},
            )
            self.assertNotEqual(resp.status_code, 404, resp.text)
        finally:
            _restore_env(saved)

    def test_demo_action_reachable_with_flag(self):
        """POST /v1/exercise → not 404 when ENABLE_DEMO_ENDPOINTS=true."""
        from fastapi.testclient import TestClient
        app, saved = _make_app(enable_demo=True)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/exercise",
                json={"subjectId": "a", "role": "r", "action": "a", "resource": "r"},
            )
            self.assertNotEqual(resp.status_code, 404, resp.text)
        finally:
            _restore_env(saved)


class TestDemoDefaultIsDisabled(unittest.TestCase):
    """Verify that the default configuration has demo endpoints disabled."""

    def test_default_enable_demo_endpoints_is_false(self):
        """config.ENABLE_DEMO_ENDPOINTS defaults to False when env var is not set."""
        saved_val = os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        try:
            import backend.src.core.config as cfg_mod
            importlib.reload(cfg_mod)
            self.assertFalse(cfg_mod.ENABLE_DEMO_ENDPOINTS)
        finally:
            if saved_val is not None:
                os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = saved_val
            else:
                os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
            import backend.src.core.config as cfg_mod
            importlib.reload(cfg_mod)


if __name__ == "__main__":
    unittest.main()
