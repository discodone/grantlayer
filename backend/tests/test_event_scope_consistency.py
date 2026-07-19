"""Every emitted audit event carries its resolved tenant and a scope.

Live-chain evidence (seq 8): the api_key_created event landed with
tenant_id=None while every neighboring event carried the real tenant. The
audit mapped the inconsistent construction sites — api-key events (no
tenant, no scope), grant_created (no scope), gdpr events (no tenant even
when the caller has one). Historical rows are immutable; this pins the
forward-only contract:

  * api_key_created / api_key_revoked carry the resolved tenant and
    scope="tenant" (key management is tenant-plane, like workspace events);
  * grant_created carries scope="tenant" like its lifecycle siblings
    (grant_revoked / grant_renewed already do);
  * gdpr events keep scope="system" but carry the caller's tenant whenever
    one is resolvable (None stays legitimate for a deployment-level admin).

The scope taxonomy itself (tenant / tenant_admin / system / bulk / export
per event kind) is deliberate and unchanged — the defect was missing
values, not the variance.

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

_JWT_SECRET = "test-secret-event-scope"


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

    def _auth(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}

    def _last_event(self, action: str):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT action, subject_id, tenant_id, workspace_id, scope "
                "FROM audit_events WHERE action=:a ORDER BY seq DESC LIMIT 1"
            ), {"a": action}).mappings().first()
        engine.dispose()
        return row


@_SKIP
class TestApiKeyEventsCarryTenantAndScope(_Base):
    def _create_key(self) -> str:
        r = self.client.post("/v1/api-keys",
                             json={"name": "scope-test", "scopes": ["read_only"]},
                             headers=self._auth())
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_api_key_created_event(self):
        self._create_key()
        ev = self._last_event("api_key_created")
        self.assertIsNotNone(ev, "creation must emit an event")
        self.assertEqual(ev["tenant_id"], "demo",
                         "event must carry the resolved tenant, never None")
        self.assertEqual(ev["scope"], "tenant")

    def test_api_key_revoked_event(self):
        key_id = self._create_key()
        r = self.client.delete(f"/v1/api-keys/{key_id}", headers=self._auth())
        self.assertEqual(r.status_code, 200, r.text)
        ev = self._last_event("api_key_revoked")
        self.assertIsNotNone(ev, "revocation must emit an event")
        self.assertIsNotNone(ev["tenant_id"],
                             "event must carry the key's resolved owning tenant")
        self.assertEqual(ev["scope"], "tenant")


@_SKIP
class TestGrantCreatedCarriesScope(_Base):
    def test_grant_created_event_scope_tenant(self):
        r = self.client.post("/v1/grants", json={
            "subjectId": "agent-scope", "role": "agent", "action": "deploy",
            "resource": "svc/scope", "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z", "createdBy": "op",
            "reason": "scope consistency test",
        }, headers=self._auth())
        self.assertEqual(r.status_code, 201, r.text)
        ev = self._last_event("deploy")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["scope"], "tenant",
                         "grant_created must be tenant-scoped like revoke/renew")
        self.assertIsNotNone(ev["tenant_id"])


@_SKIP
class TestGdprEventsCarryResolvableTenant(_Base):
    def test_export_event_carries_caller_tenant(self):
        with mock.patch(
            "backend.src.api.routers.gdpr._resolve_caller",
            return_value={"role": "admin", "sub": "adm-1", "tenant_id": "tenant-x"},
        ):
            r = self.client.post("/v1/users/user-in-tenant-x/export-data",
                                 headers={"Authorization": "Bearer patched"})
        self.assertEqual(r.status_code, 202, r.text)
        ev = self._last_event("gdpr_export_requested")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["tenant_id"], "tenant-x",
                         "gdpr event must carry the caller's tenant when resolvable")
        self.assertEqual(ev["scope"], "system", "system scope stays deliberate")


if __name__ == "__main__":
    unittest.main()
