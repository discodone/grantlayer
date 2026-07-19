"""Grant renewal must extend authority in place — witnessed, re-signed, atomic.

Today the only way to extend a grant past its validUntil is revoke + re-issue:
two chain events, a new grant id, and a reset use_count. These tests pin the
renewal contract for POST /v1/grants/{grant_id}/renew:

  * renewing returns the SAME grant id with the new validUntil, an untouched
    use_count, and a signature that verifies against the new payload
    (validUntil is inside the signed canonical payload, so renewal must
    re-sign — an in-place date edit alone would break verification);
  * exactly one `grant_renewed` audit event is appended, chain-linked to the
    prior head, attributed to the grant's workspace, carrying the old and the
    new validUntil in its reason;
  * a revoked grant refuses renewal (409) and appends nothing;
  * validation: validUntil must be parseable ISO-8601, strictly in the
    future, and not before the grant's validFrom;
  * atomicity: if the audit append fails, the re-sign and the date extension
    roll back together (authority is never extended unwitnessed);
  * the sync service path appends the same event on the SAME session.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import datetime
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

_JWT_SECRET = "test-secret-renewal-endpoint"


def _iso(days_from_now: float) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days_from_now)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    def _create_grant(self, valid_from: str | None = None, valid_until: str | None = None) -> dict:
        r = self.client.post("/v1/grants", json={
            "subjectId": "anchor-writer",
            "role": "agent",
            "action": "submit_anchor",
            "resource": "cardano/mainnet",
            "validFrom": valid_from or _iso(-1),
            "validUntil": valid_until or _iso(7),
            "createdBy": "test-op",
            "reason": "renewal test grant",
        }, headers=self._auth())
        assert r.status_code == 201, r.text
        return r.json()

    def _renew(self, grant_id: str, valid_until: str):
        return self.client.post(
            f"/v1/grants/{grant_id}/renew",
            json={"validUntil": valid_until},
            headers=self._auth(),
        )

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
                "SELECT valid_until, signature, payload_hash, use_count, revoked "
                "FROM grants WHERE id=:g"
            ), {"g": grant_id}).one()
        engine.dispose()
        return row


@_SKIP
class TestRenewEndpointContract(_Base):
    def test_renew_extends_in_place_same_id_new_valid_until(self):
        created = self._create_grant()
        new_until = _iso(37)
        r = self._renew(created["id"], new_until)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["id"], created["id"], "renewal must keep the grant id")
        self.assertEqual(body["validUntil"], new_until)
        self.assertEqual(body["validFrom"], created["validFrom"])
        self.assertEqual(body["useCount"], created["useCount"],
                         "renewal must not touch use_count")
        self.assertFalse(body["revoked"])

    def test_renewed_grant_signature_verifies_with_new_valid_until(self):
        created = self._create_grant()
        new_until = _iso(37)
        r = self._renew(created["id"], new_until)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["signatureValid"],
                        "renewal must re-sign: validUntil is in the signed payload")
        self.assertNotEqual(r.json()["payloadHash"], created["payloadHash"],
                            "payload hash must cover the new validUntil")
        # And the persisted row verifies too (not just the response echo).
        g = self.client.get(f"/v1/grants/{created['id']}", headers=self._auth())
        self.assertEqual(g.status_code, 200, g.text)
        self.assertTrue(g.json()["signatureValid"])
        self.assertEqual(g.json()["validUntil"], new_until)

    def test_renew_appends_exactly_one_chain_linked_grant_renewed_event(self):
        created = self._create_grant()
        create_ev = self._events()[-1]
        n_before = len(self._events())
        new_until = _iso(37)
        r = self._renew(created["id"], new_until)
        self.assertEqual(r.status_code, 200, r.text)
        after = self._events()
        self.assertEqual(len(after), n_before + 1,
                         "renewal must append exactly one audit event")
        ev = after[-1]
        self.assertEqual(ev.action, "grant_renewed")
        self.assertEqual(ev.resource, f"grant/{created['id']}")
        self.assertIn(created["validUntil"], ev.reason,
                      "event must carry the old validUntil")
        self.assertIn(new_until, ev.reason, "event must carry the new validUntil")
        # attributed to the grant's workspace, chain-linked to the prior head
        self.assertEqual(ev.workspace_id, create_ev.workspace_id)
        self.assertEqual(ev.tenant_id, create_ev.tenant_id)
        self.assertTrue(ev.row_hash)
        self.assertEqual(ev.prev_hash, create_ev.row_hash)

    def test_revoked_grant_refuses_renewal(self):
        created = self._create_grant()
        rv = self.client.post(f"/v1/grants/{created['id']}/revoke",
                              json={"reason": "revoked before renewal attempt"},
                              headers=self._auth())
        self.assertEqual(rv.status_code, 200, rv.text)
        n_before = len(self._events())
        r = self._renew(created["id"], _iso(37))
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "grant_revoked")
        self.assertEqual(len(self._events()), n_before,
                         "a refused renewal must not append an event")

    def test_unknown_grant_404(self):
        r = self._renew("00000000-0000-0000-0000-000000000000", _iso(37))
        self.assertEqual(r.status_code, 404, r.text)


@_SKIP
class TestRenewValidation(_Base):
    def test_unparseable_valid_until_400(self):
        created = self._create_grant()
        r = self._renew(created["id"], "not-a-timestamp")
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "invalid_timestamp")

    def test_valid_until_in_the_past_400(self):
        created = self._create_grant()
        r = self._renew(created["id"], _iso(-2))
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "invalid_date_range")

    def test_valid_until_before_valid_from_400(self):
        # Grant whose window opens in the future: renewing to a date after now
        # but before validFrom must refuse — the window would be empty.
        created = self._create_grant(valid_from=_iso(10), valid_until=_iso(20))
        r = self._renew(created["id"], _iso(5))
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "invalid_date_range")

    def test_validation_failure_appends_no_event(self):
        created = self._create_grant()
        n_before = len(self._events())
        self._renew(created["id"], _iso(-2))
        self.assertEqual(len(self._events()), n_before)


@_SKIP
class TestRenewalAtomicity(_Base):
    def test_audit_append_failure_rolls_back_the_resign(self):
        created = self._create_grant()
        row_before = self._grant_row(created["id"])
        n_before = len(self._events())

        with mock.patch(
            "backend.src.grants.grant_service._audit_log.append_event",
            side_effect=RuntimeError("audit backend unavailable"),
        ):
            r = self._renew(created["id"], _iso(37))
        self.assertEqual(r.status_code, 500,
                         "audit failure must surface, never be swallowed")
        row_after = self._grant_row(created["id"])
        self.assertEqual(row_after.valid_until, row_before.valid_until,
                         "the date extension must roll back")
        self.assertEqual(row_after.signature, row_before.signature,
                         "the re-sign must roll back with it")
        self.assertEqual(row_after.payload_hash, row_before.payload_hash)
        self.assertEqual(len(self._events()), n_before,
                         "no event may be committed either")
        # the untouched row must still verify
        g = self.client.get(f"/v1/grants/{created['id']}", headers=self._auth())
        self.assertTrue(g.json()["signatureValid"])


@_SKIP
class TestWitnessIdentityFailClosed(_Base):
    """A chain-witnessed lifecycle event must never carry subject 'unknown'.

    Identity is always resolvable after auth on these paths, so an
    unresolvable identity is a server-side invariant violation: the endpoint
    must refuse (500) instead of writing an event attributed to 'unknown'.
    """

    def _no_identity(self):
        ev = self._events()[-1]
        ws_ctx = {"tenant_id": ev.tenant_id, "workspace_id": ev.workspace_id}
        return (
            mock.patch(
                "backend.src.api.routers.grants.resolve_auth_and_workspace",
                return_value=({}, ws_ctx),
            ),
            mock.patch(
                "backend.src.api.routers.grants.require_mutation_authz",
                new=mock.AsyncMock(return_value=None),
            ),
        )

    def test_renew_refuses_without_resolvable_identity(self):
        created = self._create_grant()
        row_before = self._grant_row(created["id"])
        n_before = len(self._events())
        p1, p2 = self._no_identity()
        with p1, p2:
            r = self._renew(created["id"], _iso(37))
        self.assertEqual(r.status_code, 500, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "operator_identity_unresolved")
        row_after = self._grant_row(created["id"])
        self.assertEqual(row_after.valid_until, row_before.valid_until,
                         "no extension may happen without a witnessable identity")
        self.assertEqual(len(self._events()), n_before, "no event may be written")

    def test_revoke_refuses_without_resolvable_identity(self):
        created = self._create_grant()
        n_before = len(self._events())
        p1, p2 = self._no_identity()
        with p1, p2:
            r = self.client.post(f"/v1/grants/{created['id']}/revoke",
                                 json={"reason": "no identity"},
                                 headers=self._auth())
        self.assertEqual(r.status_code, 500, r.text)
        self.assertEqual(r.json()["detail"]["errorCode"], "operator_identity_unresolved")
        self.assertEqual(self._grant_row(created["id"]).revoked, 0,
                         "no revocation may happen without a witnessable identity")
        self.assertEqual(len(self._events()), n_before, "no event may be written")


@_SKIP
class TestSyncServiceRenew(_Base):
    def test_sync_service_appends_on_same_session(self):
        created = self._create_grant()
        create_ev = self._events()[-1]
        n_before = len(self._events())
        new_until = _iso(37)

        from backend.src.core.db import get_session_maker
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from backend.src.grants.grant_service import GrantService

        with get_session_maker()() as session:
            svc = GrantService(repo=SqlAlchemyGrantRepository(session), session=session)
            renewed = svc.renew_grant(
                created["id"],
                new_valid_until=new_until,
                renewed_by="sync-test-operator",
                tenant_id=create_ev.tenant_id,
                workspace_id=create_ev.workspace_id,
            )
            session.commit()
        self.assertIsNotNone(renewed)
        after = self._events()
        self.assertEqual(len(after), n_before + 1)
        self.assertEqual(after[-1].action, "grant_renewed")
        self.assertEqual(after[-1].subject_id, "sync-test-operator")
        row = self._grant_row(created["id"])
        self.assertEqual(row.valid_until, new_until)


if __name__ == "__main__":
    unittest.main()
