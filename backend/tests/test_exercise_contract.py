"""The /v1/exercise response contract: typed, honest, machine-readable.

The endpoint records an authorization decision — it executes nothing. The
response must say so without demo residue:

  * a typed response model backs the route (OpenAPI carries real properties,
    not an untyped object);
  * `result` states the decision as a word — "allowed" / "denied" (and
    "failed" only for the internal-error path) — alongside the compat
    `approved` boolean;
  * `reasonCode` is a stable machine code next to the human `reason`
    (access_granted, no_matching_grant, grant_expired, grant_revoked,
    challenge_required, grant_signature_invalid, ...);
  * no "[DEMO]" residue in any response string;
  * the execution row stops duplicating: `error_code` carries the machine
    code, `policy_result` the human reason.

Challenge mechanics and auth are deliberately unchanged here.
Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import datetime
import os
import tempfile
import unittest

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

_JWT_SECRET = "test-secret-exercise-contract"


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
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
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

        self.app = create_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        if self._orig_jwt_secret_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_secret_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _auth(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}

    _TUPLE = {
        "subjectId": "backup-agent",
        "role": "agent",
        "action": "pg_dump",
        "resource": "db/grantlayer-postgres",
    }

    def _create_grant(self, valid_from=None, valid_until=None) -> str:
        r = self.client.post("/v1/grants", json={
            **self._TUPLE,
            "validFrom": valid_from or _iso(-1),
            "validUntil": valid_until or _iso(30),
            "createdBy": "test-op",
            "reason": "exercise contract test grant",
        }, headers=self._auth())
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def _exercise(self, **overrides):
        return self.client.post("/v1/exercise", json={**self._TUPLE, **overrides},
                                headers=self._auth())

    def _execution_row(self, execution_id: str):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT policy_result, result, error_code FROM grant_executions WHERE id=:i"
            ), {"i": execution_id}).one()
        engine.dispose()
        return row


@_SKIP
class TestResultAndReasonCode(_Base):
    def test_allow_carries_result_allowed_and_access_granted_code(self):
        self._create_grant()
        r = self._exercise()
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["approved"])
        self.assertEqual(body["result"], "allowed")
        self.assertEqual(body["reasonCode"], "access_granted")

    def test_deny_no_grant_carries_result_denied_and_code(self):
        r = self._exercise(subjectId="no-such-agent")
        self.assertEqual(r.status_code, 403, r.text)
        body = r.json()
        self.assertFalse(body["approved"])
        self.assertEqual(body["result"], "denied")
        self.assertEqual(body["reasonCode"], "no_matching_grant")
        self.assertIn("no-such-agent", body["reason"],
                      "the human reason string must remain")

    def test_deny_expired_grant_code(self):
        self._create_grant(valid_from=_iso(-10), valid_until=_iso(-1))
        r = self._exercise()
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["reasonCode"], "grant_expired")

    def test_deny_revoked_grant_code(self):
        gid = self._create_grant()
        rv = self.client.post(f"/v1/grants/{gid}/revoke",
                              json={"reason": "contract test"}, headers=self._auth())
        self.assertEqual(rv.status_code, 200, rv.text)
        r = self._exercise()
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["reasonCode"], "grant_revoked")

    def test_challenge_required_deny_code(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        try:
            self._create_grant()
            r = self._exercise()
            self.assertEqual(r.status_code, 403, r.text)
            body = r.json()
            self.assertEqual(body["result"], "denied")
            self.assertEqual(body["reasonCode"], "challenge_required")
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)


@_SKIP
class TestNoDemoResidue(_Base):
    def test_allow_message_has_no_demo_tag(self):
        self._create_grant()
        r = self._exercise()
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("[DEMO]", r.text)
        self.assertIn("approved", r.json()["message"],
                      "the message stays honest: approved, not executed")


@_SKIP
class TestExecutionRowDeduplication(_Base):
    def test_deny_row_error_code_is_machine_code_not_reason_copy(self):
        self._create_grant(valid_from=_iso(-10), valid_until=_iso(-1))
        r = self._exercise()
        self.assertEqual(r.status_code, 403, r.text)
        row = self._execution_row(r.json()["executionId"])
        self.assertEqual(row.error_code, "grant_expired")
        self.assertIn("has expired", row.policy_result,
                      "policy_result keeps the human reason")
        self.assertNotEqual(row.error_code, row.policy_result,
                            "error_code must stop mirroring policy_result")

    def test_allow_row_error_code_stays_none(self):
        self._create_grant()
        r = self._exercise()
        self.assertEqual(r.status_code, 200, r.text)
        row = self._execution_row(r.json()["executionId"])
        self.assertIsNone(row.error_code)
        self.assertEqual(row.result, "succeeded")


@_SKIP
class TestTypedResponseModel(_Base):
    def test_openapi_response_schema_is_typed(self):
        schema = self.app.openapi()
        post = schema["paths"]["/v1/exercise"]["post"]
        ok = post["responses"]["200"]["content"]["application/json"]["schema"]
        if "$ref" in ok:
            ref = ok["$ref"].rsplit("/", 1)[-1]
            ok = schema["components"]["schemas"][ref]
        props = ok.get("properties", {})
        for field in ("approved", "result", "reasonCode", "executionId"):
            self.assertIn(field, props,
                          f"typed response model must declare '{field}'")


if __name__ == "__main__":
    unittest.main()
