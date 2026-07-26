"""Exercise-time enforcement of the signed max_fee_lovelace constraint.

Declared-attempt model: the exercise request declares attemptedFeeLovelace and
the policy ladder compares the declaration against the SIGNED grant limit —
GrantLayer records the decision; it cannot observe the fee actually paid. The
deployment-level writer fee guard stays untouched as the fail-safe backstop
(see test_constraint_backstop_writer_guard).

Fail-closed matrix pinned here:
  attempted <= limit          -> allowed
  attempted >  limit          -> denied constraint_violated_max_fee, violation
                                 witnessed as pinned canonical JSON
  attempt undeclared          -> denied constraint_attempt_undeclared
  unknown constraint type     -> denied constraint_unknown
  malformed constraint value  -> denied constraint_invalid
  grant without constraints   -> behavior unchanged (the additive guarantee)

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import datetime
import importlib
import os
import tempfile
import unittest

_LIMIT = 200_000
_VIOLATION_200001 = (
    '{"type":"max_fee_lovelace","limit":200000,"attempted":200001}'
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

    def _exercise(self, attempted_fee_lovelace=None):
        return self.demo_mod.handle_demo_action(
            "backup-agent", "agent", "pg_dump", "db/grantlayer-postgres",
            tenant_id="demo",
            workspace_id="default",
            attempted_fee_lovelace=attempted_fee_lovelace,
        )


class TestMaxFeeEnforcement(_Base):
    def test_attempt_below_limit_is_allowed(self):
        self._make_grant(constraints='{"max_fee_lovelace":200000}')
        result = self._exercise(attempted_fee_lovelace=150_000)
        self.assertTrue(result["approved"], result)
        self.assertEqual(result["reasonCode"], "access_granted")

    def test_attempt_equal_to_limit_is_allowed(self):
        self._make_grant(constraints='{"max_fee_lovelace":200000}')
        result = self._exercise(attempted_fee_lovelace=_LIMIT)
        self.assertTrue(result["approved"], result)

    def test_attempt_above_limit_is_denied_and_witnessed(self):
        g = self._make_grant(constraints='{"max_fee_lovelace":200000}')
        result = self._exercise(attempted_fee_lovelace=_LIMIT + 1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_violated_max_fee")

        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        denied = events[0]
        self.assertFalse(denied.approved)
        self.assertEqual(denied.reason_code, "constraint_violated_max_fee")
        self.assertEqual(denied.matched_grant_id, g.id)
        self.assertEqual(
            denied.constraint_violation, _VIOLATION_200001,
            "the violation must be witnessed as the pinned canonical "
            "{type,limit,attempted} JSON — proof of the exact signed limit "
            "the denial happened under",
        )

    def test_undeclared_attempt_is_denied_fail_closed(self):
        self._make_grant(constraints='{"max_fee_lovelace":200000}')
        result = self._exercise(attempted_fee_lovelace=None)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_attempt_undeclared")

        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].approved)
        self.assertEqual(events[0].reason_code, "constraint_attempt_undeclared")
        self.assertIsNone(
            events[0].constraint_violation,
            "no limit/attempted pair exists when the attempt is undeclared; "
            "the reason_code carries the denial",
        )

    def test_unknown_constraint_type_is_denied_fail_closed(self):
        self._make_grant(constraints='{"max_wallet_balance_lovelace":1000000}')
        result = self._exercise(attempted_fee_lovelace=1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_unknown")

    def test_malformed_constraint_value_is_denied_fail_closed(self):
        self._make_grant(constraints='{"max_fee_lovelace":"lots"}')
        result = self._exercise(attempted_fee_lovelace=1)
        self.assertFalse(result["approved"], result)
        self.assertEqual(result["reasonCode"], "constraint_invalid")

    def test_denied_attempt_does_not_consume_a_use(self):
        g = self._make_grant(constraints='{"max_fee_lovelace":200000}')
        self._exercise(attempted_fee_lovelace=_LIMIT + 1)
        refreshed = self.grants_mod.get_grant(g.id, tenant_id="demo")
        self.assertEqual(refreshed.use_count, 0)


class TestAdditiveGuarantee(_Base):
    """Grants without constraints behave exactly as before this feature."""

    def test_unconstrained_grant_without_declaration_is_allowed(self):
        self._make_grant(constraints=None)
        result = self._exercise(attempted_fee_lovelace=None)
        self.assertTrue(result["approved"], result)

    def test_unconstrained_grant_with_declaration_is_allowed(self):
        self._make_grant(constraints=None)
        result = self._exercise(attempted_fee_lovelace=10**9)
        self.assertTrue(
            result["approved"],
            "a declared attempt against an unconstrained grant is not a "
            "violation — there is no signed limit to violate",
        )


class TestPolicyEngineLadder(_Base):
    """Unit-level: the check sits in the candidate ladder, best_denial style."""

    def _eval(self, grant, attempted):
        from backend.src.core.models import AccessRequest
        from backend.src.policy.policy_engine import evaluate_access

        req = AccessRequest(
            subject_id="backup-agent",
            role="agent",
            action="pg_dump",
            resource="db/grantlayer-postgres",
            attempted_fee_lovelace=attempted,
        )
        return evaluate_access(
            req, [grant], datetime.datetime(2026, 6, 1, 12, 0, 0)
        )

    def _grant(self, constraints):
        from backend.src.core.models import Grant

        return Grant(
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

    def test_violation_carries_matched_grant_and_canonical(self):
        grant = self._grant('{"max_fee_lovelace":200000}')
        result = self._eval(grant, _LIMIT + 1)
        self.assertFalse(result.approved)
        self.assertEqual(result.reason_code, "constraint_violated_max_fee")
        self.assertEqual(result.matched_grant_id, grant.id)
        self.assertEqual(result.constraint_violation, _VIOLATION_200001)

    def test_another_grant_can_still_approve(self):
        """Mirrors revoked/exhausted semantics: a constraint-denied grant
        records best_denial and the ladder continues to the next candidate."""
        constrained = self._grant('{"max_fee_lovelace":200000}')
        unconstrained = self._grant(None)
        result = self._eval_multi([constrained, unconstrained], _LIMIT + 1)
        self.assertTrue(result.approved)
        self.assertEqual(result.matched_grant_id, unconstrained.id)

    def _eval_multi(self, grants, attempted):
        from backend.src.core.models import AccessRequest
        from backend.src.policy.policy_engine import evaluate_access

        req = AccessRequest(
            subject_id="backup-agent",
            role="agent",
            action="pg_dump",
            resource="db/grantlayer-postgres",
            attempted_fee_lovelace=attempted,
        )
        return evaluate_access(
            req, grants, datetime.datetime(2026, 6, 1, 12, 0, 0)
        )


try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_JWT_SECRET = "test-secret-constraint-enforcement"


@unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")
class TestEndpointPlumbing(unittest.TestCase):
    """attemptedFeeLovelace and constraints flow through the public API."""

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

    def _create_constrained_grant(self):
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
                "constraints": {"max_fee_lovelace": _LIMIT},
            },
            headers=self._jwt(),
        )
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def _exercise(self, attempted):
        body = {
            "subjectId": "backup-agent",
            "role": "agent",
            "action": "pg_dump",
            "resource": "db/grantlayer-postgres",
        }
        if attempted is not None:
            body["attemptedFeeLovelace"] = attempted
        return self.client.post("/v1/exercise", json=body, headers=self._jwt())

    def test_grant_response_exposes_constraints(self):
        created = self._create_constrained_grant()
        self.assertEqual(created.get("constraints"),
                         {"max_fee_lovelace": _LIMIT})

    def test_over_limit_attempt_is_403_with_violation_code(self):
        self._create_constrained_grant()
        resp = self._exercise(_LIMIT + 1)
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("reasonCode"),
                         "constraint_violated_max_fee")

    def test_within_limit_attempt_is_200(self):
        self._create_constrained_grant()
        resp = self._exercise(_LIMIT)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_unknown_constraint_type_is_422_at_creation(self):
        """Creation-side hard gate mirrors the api-keys invalid_scopes 422:
        an unknown type never reaches the DB (exercise-side unknown-deny then
        only covers version skew)."""
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
                "constraints": {"max_wallet_balance_lovelace": 1},
            },
            headers=self._jwt(),
        )
        self.assertEqual(r.status_code, 422, r.text)
        body = r.json()
        code = (body.get("detail") or {}).get("errorCode") or body.get("errorCode")
        self.assertEqual(code, "invalid_constraints")


if __name__ == "__main__":
    unittest.main(verbosity=2)
