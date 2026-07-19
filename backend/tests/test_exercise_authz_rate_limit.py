"""/v1/exercise sits behind the shared mutation gate and the API rate limit.

Closes the documented allowlist exception: the exercise route now calls
require_mutation_authz like every sibling mutating route — a read_only API
key is refused with 403 insufficient_scope BEFORE the decision path runs
(no execution row, no audit event; previously the key could cause decision
writes). Accepted auth methods are unchanged — this is registration in the
authz machinery, not a semantic auth change.

Rate limiting: the app-level /v1/ middleware ("api" group, per-IP,
tier-capped) already covered this route — the 429 test below PINS that
existing coverage rather than adding a new limiter; there is no per-route
limiter convention except the stricter "auth" group on /v1/auth/token.

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

_JWT_SECRET = "test-secret-exercise-authz-rl"

_TUPLE = {
    "subjectId": "backup-agent",
    "role": "agent",
    "action": "pg_dump",
    "resource": "db/grantlayer-postgres",
}


class _Base(unittest.TestCase):
    api_limit_override = None

    def setUp(self):
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")
        self._orig_api_limit = _cfg.GRANTLAYER_RATE_LIMIT_API

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        if self.api_limit_override is not None:
            _cfg.GRANTLAYER_RATE_LIMIT_API = self.api_limit_override

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _cfg.GRANTLAYER_RATE_LIMIT_API = self._orig_api_limit
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

    def _jwt(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}

    def _count_executions(self) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            n = conn.execute(sa.text("SELECT COUNT(*) FROM grant_executions")).scalar()
        engine.dispose()
        return int(n or 0)


@_SKIP
class TestReadOnlyKeyBlockedBeforeDecision(_Base):
    def test_read_only_key_403_insufficient_scope_no_decision_recorded(self):
        r = self.client.post("/v1/api-keys",
                             json={"name": "ro", "scopes": ["read_only"]},
                             headers=self._jwt())
        self.assertEqual(r.status_code, 201, r.text)
        raw_key = r.json()["key"]

        resp = self.client.post("/v1/exercise", json=_TUPLE,
                                headers={"Authorization": f"Bearer {raw_key}"})
        self.assertEqual(resp.status_code, 403, resp.text)
        body = resp.json()
        code = (body.get("detail") or {}).get("errorCode") or body.get("errorCode")
        self.assertEqual(code, "insufficient_scope",
                         "the scope gate must refuse BEFORE the decision path")
        self.assertEqual(self._count_executions(), 0,
                         "a scope-refused call must not record a decision")

    def test_read_write_key_still_reaches_the_decision_path(self):
        r = self.client.post("/v1/api-keys",
                             json={"name": "rw", "scopes": ["read_write"]},
                             headers=self._jwt())
        self.assertEqual(r.status_code, 201, r.text)
        raw_key = r.json()["key"]
        resp = self.client.post("/v1/exercise", json=_TUPLE,
                                headers={"Authorization": f"Bearer {raw_key}"})
        # No grant exists → a recorded policy denial, not a scope refusal.
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertFalse(resp.json().get("approved", True))
        self.assertEqual(self._count_executions(), 1,
                         "a write-scoped key exercises the decision path unchanged")


@_SKIP
class TestApiRateLimitCoversExercise(_Base):
    # PINS existing app-middleware coverage (no new limiter added).
    api_limit_override = 3

    def test_429_after_limit(self):
        last = None
        for _ in range(4):
            last = self.client.post("/v1/exercise", json=_TUPLE, headers=self._jwt())
        self.assertEqual(last.status_code, 429, last.text)
        self.assertIn("Retry-After", last.headers)


if __name__ == "__main__":
    unittest.main()
