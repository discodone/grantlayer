"""POST /v1/api-keys must gate API-key CALLERS the same way /v1/exercise does.

Defect being closed (C-1): the create handler authenticates the caller but
takes the new key's ``subjectId`` unchecked from the body and applies no
write-scope / scope-subset gate to API-key callers. So a ``read_only``
``gl_live_`` key can mint a ``read_write`` key bound to a FOREIGN subject and
walk it all the way to ``approved:true`` at /v1/exercise. Same class as the
exercise-side defect closed earlier (subject binding held at exercise, not at
creation).

Contract pinned here (API-KEY callers only; JWT/OIDC admin callers unchanged —
they are the legitimate operator provisioning path, e.g. the backup-agent key,
still gated by the admin-role check for admin scope):
  * caller is an UNBOUND api key (no subject binding) -> 403
    api_key_subject_unbound (strict mirror of the exercise-side refusal);
  * caller is read_only                               -> 403 insufficient_scope;
  * created subject_id := caller's bound subject; body subjectId differing
    -> 400 subject_id_mismatch; body subjectId omitted -> caller subject;
    body subjectId == caller subject -> allowed;
  * requested scopes NOT a subset of caller scopes    -> 403 insufficient_scope.

JWT/OIDC admin callers keep today's semantics: they may name any subjectId and
provision any scope subject to the existing admin-role gate.

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

_JWT_SECRET = "test-secret-apikey-creation-gate"


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

    # --- helpers -----------------------------------------------------------

    def _jwt(self, role: str = "owner") -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET, role=role)}"}

    def _mint_key_via_jwt(
        self, name: str, scopes: list[str], subject_id: str | None = None
    ) -> tuple[str, str]:
        """Provision a caller key through the admin JWT path (always allowed).

        Returns (raw_key, key_id).
        """
        body: dict = {"name": name, "scopes": scopes}
        if subject_id is not None:
            body["subjectId"] = subject_id
        r = self.client.post("/v1/api-keys", json=body, headers=self._jwt())
        self.assertEqual(r.status_code, 201, r.text)
        data = r.json()
        return data["key"], data["id"]

    def _create_as_key(self, raw_caller_key: str, body: dict):
        return self.client.post(
            "/v1/api-keys",
            json=body,
            headers={"Authorization": f"Bearer {raw_caller_key}"},
        )

    @staticmethod
    def _error_code(resp) -> str | None:
        body = resp.json()
        return (body.get("detail") or {}).get("errorCode") or body.get("errorCode")

    def _key_subject(self, key_id: str) -> str | None:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT subject_id FROM api_keys WHERE id=:id"),
                {"id": key_id},
            ).first()
        engine.dispose()
        return row[0] if row is not None else None

    def _count(self, table: str) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            n = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        engine.dispose()
        return int(n or 0)


@_SKIP
class TestR1MutationGate(_Base):
    """R1: a read_only API-key caller must not mint a key at all."""

    def test_read_only_api_key_caller_cannot_create(self):
        # Bound so the unbound check does NOT pre-empt the scope check.
        caller_key, _ = self._mint_key_via_jwt(
            "attacker-ro", ["read_only"], subject_id="agent-a"
        )
        keys_before = self._count("api_keys")
        resp = self._create_as_key(
            caller_key, {"name": "escalated", "scopes": ["read_write"]}
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._error_code(resp), "insufficient_scope", resp.text)
        self.assertEqual(
            self._count("api_keys"), keys_before,
            "a refused creation must not insert a key row",
        )


@_SKIP
class TestR2SubjectEquality(_Base):
    """R2: created key binds to the caller's subject, never a body-asserted one."""

    def test_foreign_body_subject_is_400(self):
        caller_key, _ = self._mint_key_via_jwt(
            "agent-a-key", ["read_write"], subject_id="agent-a"
        )
        keys_before = self._count("api_keys")
        resp = self._create_as_key(
            caller_key,
            {"name": "foreign", "scopes": ["read_write"], "subjectId": "victim-b"},
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(self._error_code(resp), "subject_id_mismatch", resp.text)
        self.assertEqual(
            self._count("api_keys"), keys_before,
            "a refused creation must not insert a key row",
        )

    def test_omitted_body_subject_binds_to_caller(self):
        caller_key, _ = self._mint_key_via_jwt(
            "agent-a-key", ["read_write"], subject_id="agent-a"
        )
        resp = self._create_as_key(
            caller_key, {"name": "derived", "scopes": ["read_write"]}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self._key_subject(resp.json()["id"]), "agent-a", resp.text)

    def test_matching_body_subject_is_allowed(self):
        caller_key, _ = self._mint_key_via_jwt(
            "agent-a-key", ["read_write"], subject_id="agent-a"
        )
        resp = self._create_as_key(
            caller_key,
            {"name": "matching", "scopes": ["read_write"], "subjectId": "agent-a"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self._key_subject(resp.json()["id"]), "agent-a", resp.text)


@_SKIP
class TestR3ScopeSubset(_Base):
    """R3: requested scopes must be a subset of the caller's scopes."""

    def test_scope_escalation_is_403_insufficient_scope(self):
        # read_write caller (passes R1) requesting admin (not in caller scopes).
        caller_key, _ = self._mint_key_via_jwt(
            "agent-a-key", ["read_write"], subject_id="agent-a"
        )
        resp = self._create_as_key(
            caller_key, {"name": "escalate-admin", "scopes": ["admin"]}
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._error_code(resp), "insufficient_scope", resp.text)

    def test_subset_scope_is_allowed(self):
        caller_key, _ = self._mint_key_via_jwt(
            "agent-a-key", ["read_write"], subject_id="agent-a"
        )
        resp = self._create_as_key(
            caller_key, {"name": "same-scope", "scopes": ["read_write"]}
        )
        self.assertEqual(resp.status_code, 201, resp.text)


@_SKIP
class TestR4UnboundCaller(_Base):
    """R4: an unbound API-key caller cannot mint keys (strict exercise mirror)."""

    def test_unbound_api_key_caller_is_403_subject_unbound(self):
        caller_key, _ = self._mint_key_via_jwt(
            "legacy-unbound", ["read_write"], subject_id=None
        )
        keys_before = self._count("api_keys")
        resp = self._create_as_key(
            caller_key, {"name": "child", "scopes": ["read_write"]}
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self._error_code(resp), "api_key_subject_unbound", resp.text)
        self.assertEqual(
            self._count("api_keys"), keys_before,
            "a refused creation must not insert a key row",
        )


@_SKIP
class TestR5AdminProvisioningUnbroken(_Base):
    """R5 (regression guard): JWT admin provisioning keeps working unchanged.

    Passes today and MUST still pass after the fix — the operator flow that
    minted the live backup-agent key (caller subject != key subject).
    """

    def test_jwt_admin_may_mint_key_for_foreign_subject(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "backup-agent", "scopes": ["read_write"],
                  "subjectId": "backup-agent"},
            headers=self._jwt(),
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(self._key_subject(resp.json()["id"]), "backup-agent", resp.text)

    def test_jwt_admin_may_mint_admin_scoped_key(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "admin-key", "scopes": ["admin"]},
            headers=self._jwt(role="owner"),
        )
        self.assertEqual(resp.status_code, 201, resp.text)


if __name__ == "__main__":
    unittest.main()
