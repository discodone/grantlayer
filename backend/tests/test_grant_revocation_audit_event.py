"""Grant revocation must be witnessed in the audit chain.

Revoking a grant is an active lifecycle mutation with real authority
consequences, yet the revoke path (router → GrantService.revoke_grant →
repo.revoke) historically appended NO audit event — the grants table carried
the truth but the immutable chain was blind to it. These tests pin:

  * revoking via the router appends exactly one `grant_revoked` event,
    attributed to the grant's workspace, chain-linked to the prior head;
  * the sync service path appends the same event on the SAME session;
  * atomicity: if the audit append fails, the revocation itself rolls back
    (no half-state where authority is gone but history says nothing).

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

_JWT_SECRET = "test-secret-revocation-audit"


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = True
        _cfg.GRANTLAYER_ADMIN_TOKEN = ""
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
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

    def _create_grant(self) -> str:
        r = self.client.post("/v1/grants", json={
            "subjectId": "backup-agent",
            "role": "agent",
            "action": "pg_dump",
            "resource": "db/grantlayer-postgres",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-12-31T23:59:59Z",
            "createdBy": "test-op",
            "reason": "revocation audit test grant",
        }, headers=self._auth())
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def _events(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT seq, action, subject_id, resource, reason, tenant_id, "
                "workspace_id, row_hash, prev_hash FROM audit_events ORDER BY seq"
            )).fetchall()
        engine.dispose()
        return rows

    def _grant_row(self, grant_id: str):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT revoked, revoked_by, revoked_reason FROM grants WHERE id=:g"
            ), {"g": grant_id}).one()
        engine.dispose()
        return row


@_SKIP
class TestRouterRevokeAppendsEvent(_Base):
    def test_revoke_appends_exactly_one_grant_revoked_event(self):
        gid = self._create_grant()
        before = self._events()
        r = self.client.post(f"/v1/grants/{gid}/revoke",
                             json={"reason": "rotation: superseded by new key"},
                             headers=self._auth())
        self.assertEqual(r.status_code, 200, r.text)
        after = self._events()
        self.assertEqual(len(after), len(before) + 1,
                         "revocation must append exactly one audit event")
        ev = after[-1]
        self.assertEqual(ev.action, "grant_revoked")
        self.assertEqual(ev.resource, f"grant/{gid}")
        self.assertIn("rotation: superseded by new key", ev.reason)

    def test_event_attributed_to_grants_workspace_and_chain_linked(self):
        gid = self._create_grant()
        create_ev = self._events()[-1]
        r = self.client.post(f"/v1/grants/{gid}/revoke",
                             json={"reason": "attribution check"},
                             headers=self._auth())
        self.assertEqual(r.status_code, 200, r.text)
        ev = self._events()[-1]
        # Attribution pin: the revocation lands in the SAME workspace/tenant as
        # the grant's own creation event (in this legacy-auth harness that is
        # the demo workspace; production resolution is covered elsewhere).
        self.assertEqual(ev.workspace_id, create_ev.workspace_id)
        self.assertEqual(ev.tenant_id, create_ev.tenant_id)
        # chain-linked to the prior head
        self.assertTrue(ev.row_hash)
        self.assertEqual(ev.prev_hash, create_ev.row_hash)


@_SKIP
class TestSyncServiceRevokeAppendsEvent(_Base):
    def test_sync_service_appends_on_same_session(self):
        gid = self._create_grant()
        n_before = len(self._events())

        from backend.src.core.db import get_session_maker
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from backend.src.grants.grant_service import GrantService

        create_ev = self._events()[-1]
        with get_session_maker()() as session:
            svc = GrantService(repo=SqlAlchemyGrantRepository(session), session=session)
            ok = svc.revoke_grant(
                gid,
                tenant_id=create_ev.tenant_id,
                workspace_id=create_ev.workspace_id,
                revoked_by="sync-test-operator",
                reason="sync path revocation",
            )
            session.commit()
        self.assertTrue(ok)
        after = self._events()
        self.assertEqual(len(after), n_before + 1)
        self.assertEqual(after[-1].action, "grant_revoked")
        self.assertEqual(after[-1].subject_id, "sync-test-operator")


@_SKIP
class TestRevocationAtomicity(_Base):
    def test_audit_append_failure_rolls_back_revocation(self):
        gid = self._create_grant()
        n_before = len(self._events())

        with mock.patch(
            "backend.src.grants.grant_service._audit_log.append_event",
            side_effect=RuntimeError("audit backend unavailable"),
        ):
            r = self.client.post(f"/v1/grants/{gid}/revoke",
                                 json={"reason": "must roll back"},
                                 headers=self._auth())
        self.assertEqual(r.status_code, 500,
                         "audit failure must surface, never be swallowed")
        # the revocation itself must have rolled back — no half-state
        row = self._grant_row(gid)
        self.assertEqual(row.revoked, 0,
                         "revocation must roll back when its audit write fails")
        self.assertEqual(len(self._events()), n_before,
                         "no event may be committed either")


if __name__ == "__main__":
    unittest.main()
