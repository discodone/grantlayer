"""Exercise-time enforcement of the signed max_wallet_balance_lovelace constraint.

Slice 2 of grant-policy, mirroring the max_fee_lovelace pattern exactly:
declared-attempt (the request declares walletBalanceLovelace; the ladder
compares the declaration against the SIGNED limit), fail-closed on
undeclared/unknown/malformed, violation witnessed as the pinned type-generic
canonical {"type","limit","attempted"}. NO external I/O — no chain read ever
enters the exercise path; the anchor writer's balance gate stays the
deployment-level backstop.

Also pins the multi-constraint contract: a grant may carry BOTH
max_fee_lovelace AND max_wallet_balance_lovelace; each is checked
independently, and the two-key constraints object serializes to one fixed
canonical (sorted keys, compact separators) inside the signed payload.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import datetime
import importlib
import os
import tempfile
import unittest

_LIMIT_BAL = 5_000_000
_LIMIT_FEE = 200_000
_VIOLATION_BAL = (
    '{"type":"max_wallet_balance_lovelace","limit":5000000,"attempted":5000001}'
)
_TWO_KEY_CANONICAL = (
    '{"max_fee_lovelace":200000,"max_wallet_balance_lovelace":5000000}'
)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

    def _make_grant(self, constraints=None):
        from backend.src.core.models import Grant

        g = Grant(
            subject_id="backup-agent",
            role="agent",
            action="pg_dump",
            resource="db/grantlayer-postgres",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="ops",
            reason="nightly backup",
            constraints=constraints,
        )
        self.grants_mod.create_grant(g, tenant_id="demo")
        return g

    def _exercise(self, attempted_fee=None, wallet_balance=None):
        return self.demo_mod.handle_demo_action(
            "backup-agent", "agent", "pg_dump", "db/grantlayer-postgres",
            tenant_id="demo",
            workspace_id="default",
            attempted_fee_lovelace=attempted_fee,
            wallet_balance_lovelace=wallet_balance,
        )


class TestWalletBalanceEnforcement(_Base):
    def test_balance_below_limit_is_allowed(self):
        self._make_grant(constraints='{"max_wallet_balance_lovelace":5000000}')
        result = self._exercise(wallet_balance=4_000_000)
        self.assertTrue(result["approved"], result)
        self.assertEqual(result["reasonCode"], "access_granted")

    def test_balance_equal_to_limit_is_allowed(self):
        self._make_grant(constraints='{"max_wallet_balance_lovelace":5000000}')
        result = self._exercise(wallet_balance=_LIMIT_BAL)
        self.assertTrue(result["approved"], result)

    def test_balance_above_limit_is_denied_and_witnessed(self):
        g = self._make_grant(constraints='{"max_wallet_balance_lovelace":5000000}')
        result = self._exercise(wallet_balance=_LIMIT_BAL + 1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"],
                         "constraint_violated_max_wallet_balance")

        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        denied = events[0]
        self.assertFalse(denied.approved)
        self.assertEqual(denied.matched_grant_id, g.id)
        self.assertEqual(
            denied.constraint_violation, _VIOLATION_BAL,
            "the violation must be witnessed with the wallet-balance type in "
            "the pinned {type,limit,attempted} canonical",
        )

    def test_undeclared_balance_is_denied_fail_closed(self):
        self._make_grant(constraints='{"max_wallet_balance_lovelace":5000000}')
        result = self._exercise(wallet_balance=None)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_attempt_undeclared")

    def test_unknown_constraint_type_still_denied(self):
        self._make_grant(constraints='{"rate_limit":5}')
        result = self._exercise(wallet_balance=1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_unknown")

    def test_malformed_balance_value_is_denied_fail_closed(self):
        self._make_grant(constraints='{"max_wallet_balance_lovelace":"much"}')
        result = self._exercise(wallet_balance=1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_invalid")

    def test_unconstrained_grant_stays_allowed(self):
        self._make_grant(constraints=None)
        result = self._exercise()
        self.assertTrue(result["approved"], result)

    def test_denied_attempt_does_not_consume_a_use(self):
        g = self._make_grant(constraints='{"max_wallet_balance_lovelace":5000000}')
        self._exercise(wallet_balance=_LIMIT_BAL + 1)
        refreshed = self.grants_mod.get_grant(g.id, tenant_id="demo")
        self.assertEqual(refreshed.use_count, 0)


class TestMultiConstraintGrant(_Base):
    """One grant carrying BOTH constraints — each checked independently."""

    def test_fee_passes_but_balance_violates_denies_on_balance(self):
        self._make_grant(constraints=_TWO_KEY_CANONICAL)
        result = self._exercise(attempted_fee=150_000,
                                wallet_balance=_LIMIT_BAL + 1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"],
                         "constraint_violated_max_wallet_balance")
        events = self.audit_mod.list_events()
        self.assertEqual(events[0].constraint_violation, _VIOLATION_BAL)

    def test_balance_passes_but_fee_violates_denies_on_fee(self):
        self._make_grant(constraints=_TWO_KEY_CANONICAL)
        result = self._exercise(attempted_fee=_LIMIT_FEE + 1,
                                wallet_balance=1_000_000)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_violated_max_fee")

    def test_both_pass_is_allowed(self):
        self._make_grant(constraints=_TWO_KEY_CANONICAL)
        result = self._exercise(attempted_fee=150_000,
                                wallet_balance=1_000_000)
        self.assertTrue(result["approved"], result)
        self.assertEqual(result["reasonCode"], "access_granted")

    def test_only_one_declared_denies_undeclared_other(self):
        self._make_grant(constraints=_TWO_KEY_CANONICAL)
        result = self._exercise(attempted_fee=150_000, wallet_balance=None)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_attempt_undeclared")


class TestTwoConstraintCanonicalBytes(unittest.TestCase):
    """Byte-identity: a two-constraint object has ONE deterministic canonical
    (sorted keys, compact separators) and the signed payload embeds it."""

    def test_two_key_canonical_is_pinned_and_order_independent(self):
        from backend.src.policy.constraints import canonical_constraints

        a = canonical_constraints(
            {"max_fee_lovelace": 200000, "max_wallet_balance_lovelace": 5000000}
        )
        b = canonical_constraints(
            {"max_wallet_balance_lovelace": 5000000, "max_fee_lovelace": 200000}
        )
        self.assertEqual(a, _TWO_KEY_CANONICAL)
        self.assertEqual(a, b, "construction order must not matter — the "
                               "canonical sorts keys")

    def test_signed_payload_embeds_two_key_canonical(self):
        from backend.src.core.crypto_signing import canonical_grant_payload
        from backend.src.core.models import Grant

        kwargs = dict(
            subject_id="backup-agent", role="agent", action="pg_dump",
            resource="db/grantlayer-postgres",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2027-01-01T00:00:00Z",
            created_by="ops", reason="nightly backup",
            id="00000000-0000-0000-0000-000000000002",
        )
        plain = canonical_grant_payload(Grant(**kwargs))
        both = canonical_grant_payload(
            Grant(**kwargs, constraints=_TWO_KEY_CANONICAL)
        )
        self.assertEqual(
            both,
            plain + b"\nconstraints=" + _TWO_KEY_CANONICAL.encode(),
            "two-constraint grants sign over the single sorted canonical; "
            "the constraint-free prefix stays byte-identical",
        )

    def test_wallet_balance_violation_canonical_pinned(self):
        from backend.src.policy.constraints import canonical_violation

        self.assertEqual(
            canonical_violation("max_wallet_balance_lovelace", 5000000, 5000001),
            _VIOLATION_BAL,
        )


try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_JWT_SECRET = "test-secret-wallet-balance-constraint"


@unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")
class TestEndpointPlumbing(unittest.TestCase):
    """walletBalanceLovelace and the new constraint key flow through the API."""

    def setUp(self):
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
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

    def _create_grant(self, constraints):
        r = self.client.post(
            "/v1/grants",
            json={
                "subjectId": "backup-agent",
                "role": "agent",
                "action": "pg_dump",
                "resource": "db/grantlayer-postgres",
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2099-12-31T23:59:59Z",
                "createdBy": "ops",
                "reason": "nightly backup",
                "constraints": constraints,
            },
            headers=self._jwt(),
        )
        return r

    def _exercise(self, wallet_balance=None):
        body = {
            "subjectId": "backup-agent",
            "role": "agent",
            "action": "pg_dump",
            "resource": "db/grantlayer-postgres",
        }
        if wallet_balance is not None:
            body["walletBalanceLovelace"] = wallet_balance
        return self.client.post("/v1/exercise", json=body, headers=self._jwt())

    def test_creation_accepts_wallet_balance_constraint(self):
        r = self._create_grant({"max_wallet_balance_lovelace": _LIMIT_BAL})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json().get("constraints"),
                         {"max_wallet_balance_lovelace": _LIMIT_BAL})

    def test_creation_accepts_both_constraints(self):
        r = self._create_grant({"max_fee_lovelace": _LIMIT_FEE,
                                "max_wallet_balance_lovelace": _LIMIT_BAL})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json().get("constraints"),
                         {"max_fee_lovelace": _LIMIT_FEE,
                          "max_wallet_balance_lovelace": _LIMIT_BAL})

    def test_over_limit_balance_is_403_with_violation_code(self):
        self._create_grant({"max_wallet_balance_lovelace": _LIMIT_BAL})
        resp = self._exercise(wallet_balance=_LIMIT_BAL + 1)
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("reasonCode"),
                         "constraint_violated_max_wallet_balance")

    def test_within_limit_balance_is_200(self):
        self._create_grant({"max_wallet_balance_lovelace": _LIMIT_BAL})
        resp = self._exercise(wallet_balance=_LIMIT_BAL)
        self.assertEqual(resp.status_code, 200, resp.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
