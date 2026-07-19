"""The grant-exercise endpoint lives at /v1/exercise; /v1/demo-action aliases it.

The decision-recorder endpoint was born as a demo but now serves production
callers. These tests pin the rename contract:

  * POST /v1/exercise is the real route: full decision flow (policy,
    signature gate, execution row + audit event) answers there;
  * POST /v1/demo-action keeps answering as a 307 alias (method + body
    preserved) so existing callers — the backup hook among them — keep
    working unchanged;
  * the unversioned /exercise path 307-redirects to /v1/exercise like every
    other route (versioning compat layer);
  * the alias is a pure redirect: the decision (execution row, audit event)
    is recorded once, by the /v1/exercise handler.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

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

_JWT_SECRET = "test-secret-exercise-rename"


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

    _TUPLE = {
        "subjectId": "backup-agent",
        "role": "agent",
        "action": "pg_dump",
        "resource": "db/grantlayer-postgres",
    }

    def _create_grant(self):
        r = self.client.post("/v1/grants", json={
            **self._TUPLE,
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z",
            "createdBy": "test-op",
            "reason": "exercise rename test grant",
        }, headers=self._auth())
        assert r.status_code == 201, r.text

    def _executions(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT id, action, result FROM grant_executions"
            )).fetchall()
        engine.dispose()
        return rows


@_SKIP
class TestExerciseRoute(_Base):
    def test_exercise_answers_with_full_decision_flow(self):
        self._create_grant()
        r = self.client.post("/v1/exercise", json=self._TUPLE, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["approved"])
        self.assertTrue(body.get("auditEventId"))
        self.assertTrue(body.get("executionId"))
        self.assertEqual(len(self._executions()), 1)

    def test_exercise_denies_without_grant(self):
        r = self.client.post("/v1/exercise", json={
            **self._TUPLE, "subjectId": "no-such-agent",
        }, headers=self._auth())
        self.assertEqual(r.status_code, 403, r.text)
        self.assertFalse(r.json()["approved"])


@_SKIP
class TestDemoActionAlias(_Base):
    def test_demo_action_307_aliases_to_exercise(self):
        r = self.client.post("/v1/demo-action", json=self._TUPLE,
                             headers=self._auth(), follow_redirects=False)
        self.assertEqual(r.status_code, 307, r.text)
        self.assertEqual(r.headers["location"], "/v1/exercise")

    def test_alias_preserves_method_and_body_end_to_end(self):
        self._create_grant()
        r = self.client.post("/v1/demo-action", json=self._TUPLE,
                             headers=self._auth(), follow_redirects=True)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["approved"])
        # the decision was recorded exactly once (by the /v1/exercise handler)
        self.assertEqual(len(self._executions()), 1)

    def test_unversioned_exercise_redirects_into_v1(self):
        r = self.client.post("/exercise", json=self._TUPLE,
                             headers=self._auth(), follow_redirects=False)
        self.assertEqual(r.status_code, 307, r.text)
        self.assertEqual(r.headers["location"], "/v1/exercise")


if __name__ == "__main__":
    unittest.main()
