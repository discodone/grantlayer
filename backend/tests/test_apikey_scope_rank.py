"""API-key creation scope check must use privilege RANK, not literal set subset.

Defect A: the creation gate rejects a request whose scopes are not a literal
subset of the caller's scopes (`set(body.scopes) <= set(caller.scopes)`). Since
scopes form a privilege ladder (read_only < read_write < admin), a read_write
caller minting a LOWER-privilege read_only key is wrongly refused with 403
insufficient_scope. The correct rule: a caller may mint keys at or below its own
privilege rank; anything above (escalation) is refused. This must NOT weaken
C-1: a read_only caller still cannot mint a read_write key.

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

_JWT_SECRET = "test-secret-apikey-scope-rank"


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

    def _jwt(self, role: str = "owner") -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET, role=role)}"}

    def _mint_caller(self, scopes: list[str], subject_id: str) -> str:
        """Provision a bound caller key via the admin JWT path (unconstrained)."""
        r = self.client.post(
            "/v1/api-keys",
            json={"name": "caller-%s" % "-".join(scopes), "scopes": scopes, "subjectId": subject_id},
            headers=self._jwt(),
        )
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["key"]

    def _create_as(self, raw_key: str, scopes: list[str]):
        return self.client.post(
            "/v1/api-keys",
            json={"name": "child", "scopes": scopes},
            headers={"Authorization": f"Bearer {raw_key}"},
        )

    @staticmethod
    def _ec(resp):
        b = resp.json()
        return (b.get("detail") or {}).get("errorCode") or b.get("errorCode")


@_SKIP
class TestScopeRank(_Base):
    def test_read_write_caller_may_mint_lower_priv_read_only(self):
        """RA: read_write caller minting a read_only key is a DE-escalation → 201."""
        caller = self._mint_caller(["read_write"], "rank-caller")
        resp = self._create_as(caller, ["read_only"])
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json().get("scopes"), ["read_only"], resp.text)
        self.assertEqual(resp.json().get("subjectId"), "rank-caller", resp.text)

    def test_read_only_caller_still_cannot_mint_read_write(self):
        """C-1 regression: escalation from read_only stays blocked."""
        caller = self._mint_caller(["read_only"], "rank-caller")
        resp = self._create_as(caller, ["read_write"])
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._ec(resp), "insufficient_scope", resp.text)

    def test_read_write_caller_cannot_mint_admin(self):
        """No escalation: read_write caller minting admin is refused."""
        caller = self._mint_caller(["read_write"], "rank-caller")
        resp = self._create_as(caller, ["admin"])
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._ec(resp), "insufficient_scope", resp.text)

    def test_read_write_caller_may_mint_read_write(self):
        """Equal privilege is allowed (baseline, already passes)."""
        caller = self._mint_caller(["read_write"], "rank-caller")
        resp = self._create_as(caller, ["read_write"])
        self.assertEqual(resp.status_code, 201, resp.text)


if __name__ == "__main__":
    unittest.main()
