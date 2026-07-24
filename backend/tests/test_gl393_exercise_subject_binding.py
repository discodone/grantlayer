"""/v1/exercise must bind subject identity to the API key.

Defect being closed: the endpoint authenticates the CALLER but passes
body.subjectId unchecked into grant matching, so any holder of an authorized
API key can claim to be any subject — the chain then witnesses a
caller-asserted string, not an established identity. Same class as the
body-workspace_id coercion closed earlier (creation binding = resolved
workspace, body workspace_id -> 400).

Contract pinned here (API-key auth only; JWT/operator callers unchanged —
they are privileged owner/grant_admin identities attributed via operator_id):
  * a key may carry a subject binding (api_keys.subject_id, additive column);
  * bound key + matching body subjectId  -> decision path as before;
  * bound key + mismatching subjectId    -> 400 subject_id_mismatch,
    no execution row, no audit event (refused BEFORE the decision path);
  * bound key + absent subjectId         -> subject derived from the binding;
  * UNBOUND key -> 403 api_key_subject_unbound (fail-closed: existing keys
    without a binding cannot assert subjects at all).

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

_JWT_SECRET = "test-secret-exercise-subject-binding"

_GRANT_TUPLE = {
    "role": "agent",
    "action": "pg_dump",
    "resource": "db/grantlayer-postgres",
}


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

    def _jwt(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}

    def _mint_key(self, name: str, subject_id: str | None = None) -> str:
        body: dict = {"name": name, "scopes": ["read_write"]}
        if subject_id is not None:
            body["subjectId"] = subject_id
        r = self.client.post("/v1/api-keys", json=body, headers=self._jwt())
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["key"]

    def _create_grant(self, subject_id: str) -> str:
        r = self.client.post("/v1/grants", headers=self._jwt(), json={
            "subjectId": subject_id,
            **_GRANT_TUPLE,
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "test-admin",
            "reason": "subject-binding test grant",
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _exercise(self, raw_key: str, subject_id: str | None):
        body = {**_GRANT_TUPLE}
        if subject_id is not None:
            body["subjectId"] = subject_id
        return self.client.post(
            "/v1/exercise", json=body,
            headers={"Authorization": f"Bearer {raw_key}"},
        )

    def _count(self, table: str) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            n = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        engine.dispose()
        return int(n or 0)

    @staticmethod
    def _error_code(resp) -> str | None:
        body = resp.json()
        return (body.get("detail") or {}).get("errorCode") or body.get("errorCode")


@_SKIP
class TestSubjectAssertionDefect(_Base):
    def test_api_key_cannot_exercise_another_subjects_grant(self):
        """THE defect: a key must not authorize as an arbitrary asserted subject.

        The grant belongs to 'someone-else'; the key carries no binding for
        that subject. Pre-fix this is APPROVED — the caller-asserted string
        walks straight into matching.
        """
        self._create_grant("someone-else")
        raw_key = self._mint_key("impersonator")
        resp = self._exercise(raw_key, "someone-else")
        self.assertNotEqual(resp.status_code, 200,
                            "an API key asserted an arbitrary subject and was "
                            f"APPROVED: {resp.text}")
        self.assertFalse(resp.json().get("approved", False), resp.text)


@_SKIP
class TestBoundKeyContract(_Base):
    def test_mismatching_body_subject_is_400_before_decision_path(self):
        self._create_grant("someone-else")
        raw_key = self._mint_key("agent-key", subject_id="agent-7")
        # Setup itself writes audit events (grant_created, api_key_created);
        # the refusal must add NOTHING on top of that baseline.
        events_before = self._count("audit_events")
        resp = self._exercise(raw_key, "someone-else")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(self._error_code(resp), "subject_id_mismatch", resp.text)
        self.assertEqual(self._count("grant_executions"), 0,
                         "a refused assertion must not record a decision")
        self.assertEqual(self._count("audit_events"), events_before,
                         "a refused assertion must not enter the chain")

    def test_matching_body_subject_reaches_decision_path(self):
        self._create_grant("agent-7")
        raw_key = self._mint_key("agent-key", subject_id="agent-7")
        resp = self._exercise(raw_key, "agent-7")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["approved"], resp.text)

    def test_absent_body_subject_derives_from_binding(self):
        self._create_grant("agent-7")
        raw_key = self._mint_key("agent-key", subject_id="agent-7")
        resp = self._exercise(raw_key, None)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["approved"], resp.text)

    def test_unbound_key_fail_closed_403(self):
        """Existing keys have no binding: they must be refused, not accepted."""
        self._create_grant("agent-7")
        raw_key = self._mint_key("legacy-unbound-key")
        resp = self._exercise(raw_key, "agent-7")
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._error_code(resp), "api_key_subject_unbound", resp.text)
        self.assertEqual(self._count("grant_executions"), 0)


@_SKIP
class TestJwtCallersUnchanged(_Base):
    def test_jwt_admin_may_still_assert_subjects(self):
        """JWT owner/grant_admin callers keep today's semantics: they record
        decisions for subjects and are attributed via operator_id."""
        self._create_grant("agent-7")
        resp = self.client.post(
            "/v1/exercise",
            json={"subjectId": "agent-7", **_GRANT_TUPLE},
            headers=self._jwt(),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["approved"], resp.text)


if __name__ == "__main__":
    unittest.main()
