"""SDK tests — GrantLayerClient against an in-process FastAPI app via ASGITransport."""

from __future__ import annotations

import datetime
import importlib
import os
import sys
import tempfile
import unittest

# Make sure the repo root is on sys.path so backend.* imports work.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Make sure sdk/ is on sys.path so 'grantlayer' package is importable.
_SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SDK_ROOT not in sys.path:
    sys.path.insert(0, _SDK_ROOT)

from fastapi.testclient import TestClient as _FastAPITestClient

from grantlayer import GrantLayerClient
from grantlayer.exceptions import GrantLayerAuthError, GrantLayerNotFoundError

_ADMIN_TOKEN = "gl263-sdk-test-token"
_JWT_SECRET = "gl263-sdk-jwt-secret"


def _now_iso() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()


def _future_iso(hours: int = 24) -> str:
    dt = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(hours=hours)
    return dt.isoformat()


def _make_app() -> tuple:
    """Create an isolated app instance with HS256 JWT enabled."""
    tmp = tempfile.mktemp(suffix=".db")
    env_patch = {
        "GRANTLAYER_DB": tmp,
        "GRANTLAYER_ADMIN_TOKEN": _ADMIN_TOKEN,
        "GRANTLAYER_JWT_SECRET": _JWT_SECRET,
        "GRANTLAYER_JWT_ALGORITHM": "HS256",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL": "false",
        "GRANTLAYER_ENABLE_DEMO_ENDPOINTS": "false",
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
    import backend.src.core.config as cfg_mod
    importlib.reload(cfg_mod)
    import backend.src.api.app as app_mod
    importlib.reload(app_mod)


def _client(app, token: str | None = None) -> GrantLayerClient:
    """Return a GrantLayerClient wired to *app* via FastAPI TestClient (no real server needed)."""
    tc = _FastAPITestClient(app, raise_server_exceptions=False)
    return GrantLayerClient(
        base_url="http://testserver",
        token=token,
        _http_client=tc,
    )


class TestAuthenticate(unittest.TestCase):
    """authenticate() exchanges admin token for a JWT."""

    def test_authenticate_returns_token_string(self):
        app, saved = _make_app()
        try:
            c = _client(app)
            token = c.authenticate("test-operator", _ADMIN_TOKEN)
            self.assertIsInstance(token, str)
            self.assertTrue(len(token) > 10)
        finally:
            _restore_env(saved)

    def test_authenticate_stores_token_for_subsequent_calls(self):
        app, saved = _make_app()
        try:
            c = _client(app)
            c.authenticate("test-operator", _ADMIN_TOKEN)
            # After authenticate, list_grants should work (token stored)
            result = c.list_grants()
            self.assertIsInstance(result, list)
        finally:
            _restore_env(saved)

    def test_authenticate_bad_credentials_raises_auth_error(self):
        app, saved = _make_app()
        try:
            c = _client(app)
            with self.assertRaises(GrantLayerAuthError):
                c.authenticate("test-operator", "wrong-password")
        finally:
            _restore_env(saved)


def _authenticated_client(app) -> GrantLayerClient:
    """Return a GrantLayerClient that has already exchanged credentials for a JWT."""
    c = _client(app)
    c.authenticate("test-operator", _ADMIN_TOKEN)
    return c


class TestCreateGrant(unittest.TestCase):
    """create_grant() returns a grant dict with an id field."""

    def _grant_body(self) -> dict:
        return {
            "subjectId": "agent-001",
            "role": "viewer",
            "action": "read",
            "resource": "reports",
            "validFrom": _now_iso(),
            "validUntil": _future_iso(24),
            "createdBy": "sdk-test",
            "reason": "SDK integration test",
        }

    def test_create_grant_returns_dict_with_id(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            grant = c.create_grant(**self._grant_body())
            self.assertIsInstance(grant, dict)
            self.assertIn("id", grant)
            self.assertTrue(grant["id"])
        finally:
            _restore_env(saved)

    def test_create_grant_fields_match_input(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            body = self._grant_body()
            grant = c.create_grant(**body)
            self.assertEqual(grant.get("subjectId"), "agent-001")
            self.assertEqual(grant.get("role"), "viewer")
            self.assertEqual(grant.get("action"), "read")
        finally:
            _restore_env(saved)


class TestGetGrant(unittest.TestCase):
    """get_grant() returns the grant dict for a known ID."""

    def test_get_grant_returns_dict(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            created = c.create_grant(
                subjectId="agent-get",
                role="viewer",
                action="read",
                resource="data",
                validFrom=_now_iso(),
                validUntil=_future_iso(24),
                createdBy="sdk-test",
                reason="get_grant test",
            )
            grant_id = created["id"]
            fetched = c.get_grant(grant_id)
            self.assertIsInstance(fetched, dict)
            self.assertEqual(fetched["id"], grant_id)
        finally:
            _restore_env(saved)

    def test_get_grant_not_found_raises_not_found_error(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            with self.assertRaises(GrantLayerNotFoundError):
                c.get_grant("nonexistent-grant-id-99999")
        finally:
            _restore_env(saved)


class TestListGrants(unittest.TestCase):
    """list_grants() returns a list."""

    def test_list_grants_returns_list(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            result = c.list_grants()
            self.assertIsInstance(result, list)
        finally:
            _restore_env(saved)

    def test_list_grants_includes_created_grant(self):
        app, saved = _make_app()
        try:
            c = _authenticated_client(app)
            created = c.create_grant(
                subjectId="agent-list",
                role="viewer",
                action="read",
                resource="logs",
                validFrom=_now_iso(),
                validUntil=_future_iso(24),
                createdBy="sdk-test",
                reason="list_grants test",
            )
            grants = c.list_grants()
            ids = [g["id"] for g in grants]
            self.assertIn(created["id"], ids)
        finally:
            _restore_env(saved)


if __name__ == "__main__":
    unittest.main()
