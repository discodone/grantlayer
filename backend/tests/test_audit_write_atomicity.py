"""Audit-write atomicity — a committed mutation must never outlive a failed audit write.

Three security-critical endpoints (api-key create, api-key revoke, GDPR erasure)
historically committed their mutation FIRST and then wrote the audit event in a
separate ``try/except: pass`` block — so an audit failure was silently swallowed
and the mutation stood without an audit record. For an anchored audit chain that
is a permanent, cryptographically-attested lie.

These tests force the audit write to fail and assert the MUTATION rolled back:

  1. api-key create   → 500, no api_keys row, no audit row.
  2. api-key revoke   → 500, key still ACTIVE (revoked_at IS NULL), no revoke audit row.
  3. GDPR erasure     → 500, PII STILL INTACT (operator name unchanged). The critical one.
  4. GDPR export      → the swallow is gone; an audit failure SURFACES (500), not 202.
  5. happy path       → all four succeed AND write their audit row (no over-correction
                        into permanent 500s).

They MUST fail against the pre-fix code (mutation committed before a swallowed audit)
and pass after the restructure onto the shared request session with no early commit.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from unittest import mock

_TEST_SECRET = "gl-audit-atomicity-hs256-secret-32c!"


def _jwt(sub: str, role: str = "owner", workspace_id: str = "default", tenant_id: str = "demo") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token

    return encode_token(
        {
            "sub": sub,
            "role": role,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


class _AtomicityBase(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        from fastapi.testclient import TestClient

        from backend.src.api.app import create_app

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        try:
            os.unlink(self.tmp_db.name)
        except OSError:
            pass
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

    # ── helpers ────────────────────────────────────────────────
    def _count(self, sql, params=()):
        row = self.db_mod.query_one(sql, params)
        return list(row.values())[0] if row else 0

    def _raise_audit(self):
        """Patch append_event in BOTH router modules to raise."""
        def _boom(*a, **k):
            raise RuntimeError("simulated audit-store failure")

        return mock.patch.multiple(
            "backend.src.api.routers.api_keys",
            append_event=_boom,
        ), mock.patch.multiple(
            "backend.src.api.routers.gdpr",
            append_event=_boom,
        )


class TestApiKeyCreateAtomicity(_AtomicityBase):
    def test_api_key_create_rolls_back_when_audit_fails(self):
        auth = {"Authorization": f"Bearer {_jwt('user-create')}"}
        p_api, _ = self._raise_audit()
        with p_api:
            resp = self.client.post(
                "/v1/api-keys", json={"name": "k1", "scopes": ["read_write"]}, headers=auth
            )
        self.assertEqual(resp.status_code, 500, resp.text)
        # The mutation must NOT have persisted.
        self.assertEqual(self._count("SELECT COUNT(*) AS c FROM api_keys"), 0)
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS c FROM audit_events WHERE action='api_key_created'"
            ),
            0,
        )


class TestApiKeyRevokeAtomicity(_AtomicityBase):
    def test_api_key_revoke_rolls_back_when_audit_fails(self):
        auth = {"Authorization": f"Bearer {_jwt('user-revoke')}"}
        # Create a key normally (audit intact).
        created = self.client.post(
            "/v1/api-keys", json={"name": "k2", "scopes": ["read_write"]}, headers=auth
        )
        self.assertEqual(created.status_code, 201, created.text)
        key_id = created.json()["id"]

        p_api, _ = self._raise_audit()
        with p_api:
            resp = self.client.delete(f"/v1/api-keys/{key_id}", headers=auth)
        self.assertEqual(resp.status_code, 500, resp.text)
        # The key must still be ACTIVE — the revoke rolled back.
        row = self.db_mod.query_one(
            "SELECT revoked_at FROM api_keys WHERE id=?", (key_id,)
        )
        self.assertIsNotNone(row)
        self.assertIsNone(row["revoked_at"], "key was revoked despite audit failure")
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS c FROM audit_events WHERE action='api_key_revoked'"
            ),
            0,
        )


class TestGdprErasureAtomicity(_AtomicityBase):
    def test_gdpr_erasure_rolls_back_when_audit_fails(self):
        uid = "erase-me"
        # Seed an operator row carrying PII (self-service erasure of own id).
        self.db_mod.execute(
            "INSERT INTO operators (id, name, role, token_hash, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "Real Name PII", "operator", "hash", 1, "2026-01-01T00:00:00Z"),
        )
        auth = {"Authorization": f"Bearer {_jwt(uid, role='owner')}"}

        _, p_gdpr = self._raise_audit()
        with p_gdpr:
            resp = self.client.post(f"/v1/users/{uid}/erase", headers=auth)
        self.assertEqual(resp.status_code, 500, resp.text)
        # PII MUST still be intact — erasure rolled back (never erase without audit).
        row = self.db_mod.query_one("SELECT name FROM operators WHERE id=?", (uid,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Real Name PII", "PII was anonymized despite audit failure")
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS c FROM audit_events WHERE action='gdpr_erasure_completed'"
            ),
            0,
        )


class TestGdprExportDeSwallow(_AtomicityBase):
    def test_gdpr_export_audit_failure_is_not_swallowed(self):
        uid = "export-me"
        auth = {"Authorization": f"Bearer {_jwt(uid, role='owner')}"}
        _, p_gdpr = self._raise_audit()
        with p_gdpr:
            resp = self.client.post(f"/v1/users/{uid}/export-data", headers=auth)
        # Export commits no mutation, but the audit failure must SURFACE, not pass silently.
        self.assertEqual(resp.status_code, 500, resp.text)


class TestHappyPathStillWrites(_AtomicityBase):
    def test_happy_path_still_works(self):
        # api-key create
        auth = {"Authorization": f"Bearer {_jwt('happy-user')}"}
        c = self.client.post(
            "/v1/api-keys", json={"name": "hk", "scopes": ["read_write"]}, headers=auth
        )
        self.assertEqual(c.status_code, 201, c.text)
        key_id = c.json()["id"]
        self.assertEqual(self._count("SELECT COUNT(*) AS c FROM api_keys"), 1)
        self.assertEqual(
            self._count("SELECT COUNT(*) AS c FROM audit_events WHERE action='api_key_created'"),
            1,
        )
        # api-key revoke
        r = self.client.delete(f"/v1/api-keys/{key_id}", headers=auth)
        self.assertEqual(r.status_code, 200, r.text)
        row = self.db_mod.query_one("SELECT revoked_at FROM api_keys WHERE id=?", (key_id,))
        self.assertIsNotNone(row["revoked_at"])
        self.assertEqual(
            self._count("SELECT COUNT(*) AS c FROM audit_events WHERE action='api_key_revoked'"),
            1,
        )
        # GDPR export (self-service)
        e = self.client.post("/v1/users/happy-user/export-data", headers=auth)
        self.assertEqual(e.status_code, 202, e.text)
        self.assertEqual(
            self._count("SELECT COUNT(*) AS c FROM audit_events WHERE action='gdpr_export_requested'"),
            1,
        )
        # GDPR erasure (self-service)
        er = self.client.post("/v1/users/happy-user/erase", headers=auth)
        self.assertEqual(er.status_code, 202, er.text)
        self.assertEqual(
            self._count("SELECT COUNT(*) AS c FROM audit_events WHERE action='gdpr_erasure_completed'"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
