"""No audit-attributed write may fall back to subject 'unknown'.

The renew/revoke endpoints already refuse (500 operator_identity_unresolved)
when no caller identity resolves. The same fallback class survived at seven
other sites that attribute rows or chain events to
``payload.get("sub", "unknown")``:

  * api_keys: create (key owner + created event), list (owner-scoped query),
    revoke (owner/authz basis + revoked event);
  * gdpr: export-data and erase (chain events subject_id — erase also
    mutates PII before the event);
  * grant_templates: create and new-version (created_by attribution).

These tests pin the fail-closed contract for each site-group: an
authenticated-but-identity-less payload (no ``sub``) must be refused with
500 operator_identity_unresolved BEFORE any row is written, any event is
appended, or any identity-based authorization is evaluated against the
literal string 'unknown'.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import os
import tempfile
import unittest
from unittest import mock

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_JWT_SECRET = "test-secret-identity-fallbacks"


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        if self._orig_jwt_secret_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_secret_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    _HDRS = {"Authorization": "Bearer irrelevant-resolver-is-patched"}

    def _assert_refused(self, resp):
        self.assertEqual(resp.status_code, 500, resp.text)
        self.assertEqual(resp.json()["detail"]["errorCode"], "operator_identity_unresolved")

    def _count(self, table: str) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            n = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        engine.dispose()
        return int(n or 0)


@_SKIP
class TestApiKeysIdentityFailClosed(_Base):
    def test_create_refuses_without_sub(self):
        ws_ctx = {"workspace_id": "ws-ident", "tenant_id": "t-ident",
                  "resolution_mode": "test", "operator_id": None}
        with mock.patch(
            "backend.src.api.routers.api_keys.async_resolve_auth_and_workspace",
            new=mock.AsyncMock(return_value=({}, ws_ctx)),
        ):
            r = self.client.post("/v1/api-keys",
                                 json={"name": "k1", "scopes": ["read_only"]},
                                 headers=self._HDRS)
        self._assert_refused(r)
        self.assertEqual(self._count("api_keys"), 0, "no key may be minted")
        self.assertEqual(self._count("audit_events"), 0, "no event may be written")

    def test_list_refuses_without_sub(self):
        with mock.patch(
            "backend.src.api.routers.api_keys._resolve_user", return_value={},
        ):
            r = self.client.get("/v1/api-keys", headers=self._HDRS)
        self._assert_refused(r)

    def test_revoke_refuses_without_sub(self):
        with mock.patch(
            "backend.src.api.routers.api_keys._resolve_user", return_value={},
        ):
            r = self.client.delete("/v1/api-keys/some-key-id", headers=self._HDRS)
        self._assert_refused(r)
        self.assertEqual(self._count("audit_events"), 0)


@_SKIP
class TestGdprIdentityFailClosed(_Base):
    # role=admin passes the permission gate; the missing sub is exactly the
    # bug: an admin token without identity used to witness events as 'unknown'.
    _CALLER = {"role": "admin"}

    def test_export_refuses_without_sub(self):
        with mock.patch(
            "backend.src.api.routers.gdpr._resolve_caller", return_value=dict(self._CALLER),
        ):
            r = self.client.post("/v1/users/target-user-1/export-data",
                                 headers=self._HDRS)
        self._assert_refused(r)
        self.assertEqual(self._count("audit_events"), 0, "no event may be written")

    def test_erase_refuses_without_sub_before_any_mutation(self):
        with mock.patch(
            "backend.src.api.routers.gdpr._resolve_caller", return_value=dict(self._CALLER),
        ):
            r = self.client.post("/v1/users/target-user-1/erase",
                                 headers=self._HDRS)
        self._assert_refused(r)
        self.assertEqual(self._count("audit_events"), 0,
                         "no event may be written — and no PII mutation may precede the refusal")


@_SKIP
class TestGrantTemplatesIdentityFailClosed(_Base):
    _PAYLOAD = {"workspace_id": "ws-ident"}

    def test_create_refuses_without_sub(self):
        with mock.patch(
            "backend.src.api.routers.grant_templates._resolve_user",
            return_value=dict(self._PAYLOAD),
        ):
            r = self.client.post("/v1/grant-templates",
                                 json={"name": "tmpl-1"}, headers=self._HDRS)
        self._assert_refused(r)
        self.assertEqual(self._count("grant_templates"), 0, "no template row may be written")

    def test_new_version_refuses_without_sub(self):
        with mock.patch(
            "backend.src.api.routers.grant_templates._resolve_user",
            return_value=dict(self._PAYLOAD),
        ):
            r = self.client.post("/v1/grant-templates/some-template/new-version",
                                 json={"name": "tmpl-2"}, headers=self._HDRS)
        self._assert_refused(r)


if __name__ == "__main__":
    unittest.main()
