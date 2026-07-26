"""Per-subject operational rate limit on /v1/exercise (gl-411).

An OPERATIONAL throttle, deliberately NOT a signed grant constraint: it lives
entirely at the pre-policy route seam (after subject binding, before
handle_demo_action), so a throttled request produces NO execution row, NO
audit event, and never touches the policy ladder or the signed-constraint
path. Verifiability stays intact: the constraint_violation witness column
remains exclusively for authorization violations reproducible from
grant + chain; a 429 is server-attested operations, not chain evidence.

Bucket: workspace-scoped per-subject ("exercise" group on the existing
limiter). Limit resolution mirrors limit_for_tier precedence: the
workspace's rate_limit_override wins when set, else the
GRANTLAYER_RATE_LIMIT_EXERCISE env floor. Fail-open is inherited from the
existing limiter (Redis error -> in-process fallback; never a hard deny
from infrastructure loss).

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import os
import tempfile
import unittest
import uuid

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

_JWT_SECRET = "test-secret-exercise-subject-rl"

_TUPLE = {
    "subjectId": "backup-agent",
    "role": "agent",
    "action": "pg_dump",
    "resource": "db/grantlayer-postgres",
}

_UNSET = object()


class _Base(unittest.TestCase):
    # Per-subject exercise floor patched onto the config module for the test.
    exercise_limit = 2

    def setUp(self):
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")
        self._orig_exercise_limit = getattr(
            _cfg, "GRANTLAYER_RATE_LIMIT_EXERCISE", _UNSET
        )

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.GRANTLAYER_RATE_LIMIT_EXERCISE = self.exercise_limit

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        if self._orig_exercise_limit is _UNSET:
            if hasattr(_cfg, "GRANTLAYER_RATE_LIMIT_EXERCISE"):
                delattr(_cfg, "GRANTLAYER_RATE_LIMIT_EXERCISE")
        else:
            _cfg.GRANTLAYER_RATE_LIMIT_EXERCISE = self._orig_exercise_limit
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

    def _exercise(self, subject_id: str, headers=None, **extra):
        payload = dict(_TUPLE, subjectId=subject_id, **extra)
        return self.client.post(
            "/v1/exercise", json=payload, headers=headers or self._jwt()
        )

    def _count_rows(self, table: str) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            n = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        engine.dispose()
        return int(n or 0)

    @staticmethod
    def _error_code(resp) -> str:
        body = resp.json()
        return (body.get("detail") or {}).get("errorCode") or body.get("errorCode")


@_SKIP
class TestPerSubjectThrottle(_Base):
    """R1 — the (N+1)th exercise for one subject inside the window is 429."""

    exercise_limit = 2

    def test_third_request_for_same_subject_is_429(self):
        subject = f"agent-{uuid.uuid4()}"
        for _ in range(self.exercise_limit):
            r = self._exercise(subject)
            self.assertNotEqual(
                r.status_code, 429,
                "requests within the per-subject limit must not be throttled",
            )
        r = self._exercise(subject)
        self.assertEqual(r.status_code, 429, r.text)
        self.assertIn("Retry-After", r.headers)
        self.assertEqual(self._error_code(r), "rate_limit_exceeded")


@_SKIP
class TestSubjectIsolation(_Base):
    """R3 — one subject's exhausted bucket never throttles another subject."""

    exercise_limit = 2

    def test_other_subject_not_throttled_by_exhausted_bucket(self):
        subject_a = f"agent-a-{uuid.uuid4()}"
        subject_b = f"agent-b-{uuid.uuid4()}"
        for _ in range(self.exercise_limit):
            self._exercise(subject_a)
        throttled = self._exercise(subject_a)
        self.assertEqual(
            throttled.status_code, 429,
            "subject A's bucket must be exhausted for this test to mean anything",
        )
        r = self._exercise(subject_b)
        self.assertNotEqual(
            r.status_code, 429,
            "subject B must have its own bucket (per-subject key correctness)",
        )


@_SKIP
class TestFailOpenOnRedisError(unittest.TestCase):
    """R2 — a Redis backend that errors degrades OPEN to the in-process
    fallback; the request proceeds and the fallback window keeps enforcing.
    Pins the existing soft-degradation for the exercise group; no
    fail-closed seam anywhere."""

    def test_eval_raising_redis_falls_back_open(self):
        from backend.src.core.rate_limiter import RedisRateLimiter

        class _RaisingRedis:
            def eval(self, *args, **kwargs):
                raise ConnectionError("redis down")

            def ping(self):
                raise ConnectionError("redis down")

        rl = RedisRateLimiter(redis_url="redis://127.0.0.1:1")
        rl._redis = _RaisingRedis()

        bucket = f"ws-{uuid.uuid4()}:backup-agent"
        allowed, _ = rl.check(bucket, "exercise", rate_limit_override=2)
        self.assertTrue(allowed, "Redis error must degrade OPEN, never deny")
        self.assertIsNone(rl._redis, "limiter must have dropped the dead client")

        # The in-process fallback window now enforces the same limit.
        allowed2, _ = rl.check(bucket, "exercise", rate_limit_override=2)
        self.assertTrue(allowed2)
        allowed3, retry_after = rl.check(bucket, "exercise", rate_limit_override=2)
        self.assertFalse(allowed3, "fallback must keep enforcing the window")
        self.assertGreaterEqual(retry_after, 1)


@_SKIP
class TestWorkspaceOverridePrecedence(_Base):
    """R4 — the existing per-workspace rate_limit_override (tiered-rate-limit
    column, PATCH /v1/workspaces/{id}/plan) wins over the env floor at the
    exercise seam."""

    exercise_limit = 100  # generous floor: only the override can cause a 429

    def setUp(self):
        super().setUp()
        from datetime import datetime, timezone

        from backend.src.core.db import get_session_maker
        from backend.src.core.orm import Workspace

        self.workspace_id = f"ws-{uuid.uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with get_session_maker()() as session:
            session.add(
                Workspace(
                    id=self.workspace_id,
                    tenant_id="demo",
                    name="override-test",
                    slug=f"override-{uuid.uuid4().hex[:8]}",
                    owner_id="dev-operator",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    def test_override_of_one_gates_second_request(self):
        r = self.client.patch(
            f"/v1/workspaces/{self.workspace_id}/plan",
            json={"plan_tier": "free", "rate_limit_override": 1},
            headers=self._jwt(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["rate_limit_override"], 1)

        subject = f"agent-{uuid.uuid4()}"
        headers = dict(self._jwt(), **{"X-Workspace-Id": self.workspace_id})
        first = self._exercise(subject, headers=headers)
        self.assertNotEqual(first.status_code, 429, first.text)
        second = self._exercise(subject, headers=headers)
        self.assertEqual(
            second.status_code, 429,
            "the workspace override (1) must win over the env floor (100)",
        )
        self.assertIn("Retry-After", second.headers)


@_SKIP
class TestNoLeakIntoSignedPath(_Base):
    """R5 — the signed-constraint path is untouched, and a 429 writes
    nothing: no execution row, no audit event, and therefore never the
    constraint_violation witness column."""

    exercise_limit = 2
    _LIMIT = 200_000
    _VIOLATION = '{"type":"max_fee_lovelace","limit":200000,"attempted":200001}'

    def _make_fee_constrained_grant(self):
        import backend.src.core.crypto_signing as crypto_mod
        from backend.src.core.models import Grant
        from backend.src.grants.grants import create_grant

        crypto_mod.ensure_demo_keypair()
        g = Grant(
            subject_id=_TUPLE["subjectId"],
            role=_TUPLE["role"],
            action=_TUPLE["action"],
            resource=_TUPLE["resource"],
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="ops",
            reason="throttle no-leak guard",
            constraints='{"max_fee_lovelace":200000}',
        )
        create_grant(g, tenant_id="demo")
        return g

    def test_fee_violation_still_witnessed_exactly_as_before(self):
        # Slice-1 regression via the HTTP route: declared-attempt vs signed
        # limit, denial witnessed as the pinned canonical JSON.
        g = self._make_fee_constrained_grant()
        r = self._exercise(
            _TUPLE["subjectId"], attemptedFeeLovelace=self._LIMIT + 1
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(r.json()["reasonCode"], "constraint_violated_max_fee")

        from backend.src.audit.audit_log import list_events
        events = list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].constraint_violation, self._VIOLATION)
        self.assertEqual(events[0].matched_grant_id, g.id)

    def test_429_writes_no_decision_and_no_witness(self):
        self._make_fee_constrained_grant()
        # Exhaust the per-subject bucket with fee-violating requests — each
        # IS a decision (witnessed denial); the throttled one must NOT be.
        for _ in range(self.exercise_limit):
            r = self._exercise(
                _TUPLE["subjectId"], attemptedFeeLovelace=self._LIMIT + 1
            )
            self.assertEqual(r.status_code, 403, r.text)

        events_before = self._count_rows("audit_events")
        executions_before = self._count_rows("grant_executions")
        self.assertEqual(events_before, self.exercise_limit)

        throttled = self._exercise(
            _TUPLE["subjectId"], attemptedFeeLovelace=self._LIMIT + 1
        )
        self.assertEqual(throttled.status_code, 429, throttled.text)
        self.assertEqual(
            self._count_rows("audit_events"), events_before,
            "a throttled request must never reach the decision path",
        )
        self.assertEqual(self._count_rows("grant_executions"), executions_before)


if __name__ == "__main__":
    unittest.main()
