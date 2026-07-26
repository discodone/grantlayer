"""GET /v1/audit/verify must use the real chain verifier, ordered by seq.

Defect B: the endpoint reconstructs hashes with _entry_canonical/_chain_hash
(the EXPORT-fold scheme) and compares them to the stored row_hash (produced by
_compute_row_hash — a different field set/separator with prev_hash inside the
payload). The two can NEVER match, so the endpoint reports valid:false on an
INTACT chain. Fix: route the endpoint through verify_audit_hash_chain(), the
same DB-row_hash verifier the anchor/report path uses.

Defect C: verify_audit_hash_chain() reads events ordered by timestamp ASC, but
timestamp is assigned BEFORE the write lock and seq UNDER it, so parallel writes
can invert timestamp vs seq. The chain is linked in insertion (seq) order, so a
timestamp-ordered walk flags an HONEST chain as tampered. Fix: order the verify
read by seq (mirroring the anchor export's seq-ASC determinism contract).

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

_JWT_SECRET = "test-secret-audit-verify-seq"
# The demo auditor JWT resolves to tenant "demo" / workspace "default", so
# events land where the (currently workspace-scoped) endpoint walks them —
# reproducing the "valid:false on an intact chain" symptom pre-fix.
_WS = "default"
_TENANT = "demo"


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

    def _append(self, action: str, timestamp: str | None = None):
        from backend.src.audit.audit_log import append_event
        from backend.src.core.models import AuditEvent
        kw = dict(
            subject_id="subj-1", role="agent", action=action,
            resource="db/x", approved=True, reason="test",
            workspace_id=_WS, tenant_id=_TENANT, scope="tenant",
        )
        if timestamp is not None:
            kw["timestamp"] = timestamp
        evt = AuditEvent(**kw)
        append_event(evt)
        return evt

    def _tamper_one_row_hash(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.begin() as conn:
            # audit_events is append-only (immutability triggers); drop the
            # no-update trigger to simulate an at-rest tamper, as the adversarial
            # tamper suite does.
            conn.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_events_no_update"))
            rid = conn.execute(sa.text(
                "SELECT id FROM audit_events ORDER BY seq ASC LIMIT 1")).scalar()
            conn.execute(sa.text("UPDATE audit_events SET row_hash=:h WHERE id=:i"),
                         {"h": "0"*64, "i": rid})
        engine.dispose()


@_SKIP
class TestVerifyEndpoint(_Base):
    """Defect B — the endpoint must report valid:true on an INTACT chain."""

    def _jwt(self) -> dict:
        from backend.src.api.auth_jwt import encode_token
        return {"Authorization": "Bearer " + encode_token(
            {"role": "auditor", "tenant_id": _TENANT,
             "iss": "grantlayer", "aud": "grantlayer-api"}, _JWT_SECRET)}

    def test_intact_chain_verifies_true(self):
        for a in ("a", "b", "c"):
            self._append(a)
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/v1/audit/verify", headers=self._jwt())
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["valid"],
                        "intact chain reported invalid: %s" % resp.text)
        self.assertEqual(data["checked"], 3, resp.text)

    def test_tampered_chain_verifies_false(self):
        for a in ("a", "b", "c"):
            self._append(a)
        self._tamper_one_row_hash()
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/v1/audit/verify", headers=self._jwt())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(resp.json()["valid"], resp.text)


@_SKIP
class TestVerifyOrdersBySeq(_Base):
    """Defect C — an honest chain whose timestamps diverge from seq must verify."""

    def test_seq_timestamp_divergence_is_not_flagged(self):
        from backend.src.audit.audit_log import verify_audit_hash_chain
        # Insert A first (seq=1) with a LATER timestamp, then B (seq=2) with an
        # EARLIER timestamp — the parallel-write inversion. append links B->A by
        # insertion order (seq), so the chain is honest; only a timestamp-ordered
        # verify walk would flag it.
        self._append("first-inserted", timestamp="2026-03-01T00:00:02+00:00")
        self._append("second-inserted", timestamp="2026-03-01T00:00:01+00:00")
        result = verify_audit_hash_chain()
        self.assertEqual(result["checked"], 2, result)
        self.assertTrue(result["valid"],
                        "honest chain flagged as tampered due to timestamp "
                        "ordering: %s" % result)


if __name__ == "__main__":
    unittest.main()
