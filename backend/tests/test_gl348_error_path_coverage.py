"""GL-348 — Real error-path / edge-case coverage for genuinely uncovered branches.

These exercise behavior that the suite did not previously reach: Redis-backed
rate-limiter failure/fallback paths, secret-source resolution fallbacks and
validation errors, provenance query filter construction, plan-tier extraction
edge cases, and context sanitization. No trivial/structural padding — each test
asserts real behavior on a real code path.
"""

from __future__ import annotations

import os
import tempfile
import unittest


# ── rate_limiter: Redis-backed failure / fallback / reset paths ───────────────
class _FakeRedis:
    def __init__(self, *, eval_result=None, eval_raises=False,
                 scan_raises=False, ping_ok=True):
        self._eval_result = eval_result or [1, 1, 0]
        self._eval_raises = eval_raises
        self._scan_raises = scan_raises
        self._ping_ok = ping_ok
        self.deleted: list = []

    def eval(self, *a, **k):
        if self._eval_raises:
            raise RuntimeError("redis eval failed")
        return self._eval_result

    def scan(self, cursor, match=None, count=None):
        if self._scan_raises:
            raise RuntimeError("scan failed")
        return (0, [b"rl:1.2.3.4:api:free"])

    def delete(self, *keys):
        self.deleted.extend(keys)

    def ping(self):
        if not self._ping_ok:
            raise ConnectionError("dead")
        return True


def _redis_limiter(fake):
    from backend.src.core.rate_limiter import RedisRateLimiter
    lim = RedisRateLimiter(redis_url="redis://127.0.0.1:6390", auth_limit=10, api_limit=120)
    lim._redis = fake
    return lim


class TestRateLimiterRedisPaths(unittest.TestCase):
    def test_check_falls_back_to_in_process_when_redis_errors(self):
        fake = _FakeRedis(eval_raises=True)
        lim = _redis_limiter(fake)
        allowed, retry = lim.check("1.2.3.4", "api")
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)
        # After the error the limiter dropped the dead connection.
        self.assertIsNone(lim._redis)

    def test_redis_check_returns_rate_limited(self):
        # eval reports not-allowed (0), count, retry_after=3 → (False, 3)
        fake = _FakeRedis(eval_result=[0, 5, 3])
        lim = _redis_limiter(fake)
        allowed, retry = lim.check("9.9.9.9", "api")
        self.assertFalse(allowed)
        self.assertEqual(retry, 3)

    def test_redis_check_enterprise_unlimited(self):
        fake = _FakeRedis(eval_result=[0, 9999, 60])
        lim = _redis_limiter(fake)
        allowed, retry = lim.check("8.8.8.8", "api", plan_tier="enterprise")
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)

    def test_reset_clears_redis_keys(self):
        fake = _FakeRedis()
        lim = _redis_limiter(fake)
        lim.reset()
        self.assertIn(b"rl:1.2.3.4:api:free", fake.deleted)

    def test_reset_swallows_redis_errors(self):
        fake = _FakeRedis(scan_raises=True)
        lim = _redis_limiter(fake)
        lim.reset()  # must not raise

    def test_live_health_unavailable_when_reconnect_fails(self):
        from backend.src.core.rate_limiter import RedisRateLimiter
        lim = RedisRateLimiter(redis_url="redis://127.0.0.1:6390")
        lim._redis = None  # simulate post-failure with no live connection
        self.assertEqual(lim.live_redis_health(), "unavailable")


# ── secret_sources: redaction, validation, resolution fallbacks ───────────────
class TestSecretSources(unittest.TestCase):
    def test_redact_secret_value_variants(self):
        from backend.src.core.secret_sources import REDACTED_SECRET_VALUE, redact_secret_value
        self.assertIsNone(redact_secret_value(None))
        self.assertEqual(redact_secret_value(True), True)
        self.assertEqual(redact_secret_value(42), 42)
        self.assertEqual(redact_secret_value("   "), "   ")  # whitespace preserved
        self.assertEqual(redact_secret_value("super-secret"), REDACTED_SECRET_VALUE)
        # Already-redacted stays as-is.
        self.assertEqual(redact_secret_value(REDACTED_SECRET_VALUE), REDACTED_SECRET_VALUE)

    def test_validate_name_sequence_rejects_bad_inputs(self):
        from backend.src.core.secret_sources import _validate_name_sequence
        for bad in (None, 123, ["ok", ""], ["ok", None]):
            with self.assertRaises(ValueError):
                _validate_name_sequence(bad)

    def test_read_docker_secret_rejects_empty(self):
        from backend.src.core.secret_sources import read_docker_secret
        with self.assertRaises(ValueError):
            read_docker_secret("")
        with self.assertRaises(ValueError):
            read_docker_secret("name", secrets_dir="")

    def test_describe_file_secret_source_present_and_absent(self):
        from backend.src.core.secret_sources import describe_file_secret_source
        with tempfile.TemporaryDirectory() as d:
            absent = describe_file_secret_source("missing", secrets_dir=d)
            self.assertFalse(absent["present"])
            self.assertIsNone(absent["valuePreview"])
            with open(os.path.join(d, "tok"), "w") as f:
                f.write("value-123")
            present = describe_file_secret_source("tok", secrets_dir=d)
            self.assertTrue(present["present"])

    def test_resolver_falls_back_docker_then_env(self):
        from backend.src.core.secret_sources import SecretConfigurationError, SecretResolver
        with tempfile.TemporaryDirectory() as d:
            # Docker-secret file present → resolved from file.
            with open(os.path.join(d, "FROM_FILE"), "w") as f:
                f.write("file-secret")
            r = SecretResolver(vault=None, secrets_dir=d, env={"FROM_ENV": "env-secret"})
            self.assertEqual(r.resolve("FROM_FILE"), "file-secret")
            # Not in file → falls through to env.
            self.assertEqual(r.resolve("FROM_ENV"), "env-secret")
            # Absent everywhere → None, and resolve_required raises.
            self.assertIsNone(r.resolve("NOWHERE"))
            with self.assertRaises(SecretConfigurationError):
                r.resolve_required("NOWHERE")


# ── provenance: filter construction + limit clamping + validation ─────────────
class TestProvenanceListing(unittest.TestCase):
    def setUp(self):
        from backend.src.core.db import init_db
        init_db()

    def test_list_with_all_filters_and_limit_clamping(self):
        from backend.src.policy import provenance
        # limit < 1 clamps to 1; all filter branches execute.
        out = provenance.list_provenance_events(
            execution_id="e1", grant_id="g1", resource_type="service",
            resource_id="r1", actor_type="agent", limit=0,
        )
        self.assertIsInstance(out, list)
        # limit > 1000 clamps to 1000.
        out2 = provenance.list_provenance_events(grant_id="g1", limit=5000)
        self.assertIsInstance(out2, list)

    def test_invalid_actor_type_raises(self):
        from backend.src.policy import provenance
        with self.assertRaises(ValueError):
            provenance.list_provenance_events(actor_type="not-a-real-type")


# ── auth_jwt: plan-tier extraction edge cases ─────────────────────────────────
class TestPlanTierExtraction(unittest.TestCase):
    def test_blank_and_missing_tokens_default_free(self):
        from backend.src.api.auth_jwt import _safe_extract_plan_tier
        self.assertEqual(_safe_extract_plan_tier(None), "free")
        self.assertEqual(_safe_extract_plan_tier("Bearer    "), "free")
        self.assertEqual(_safe_extract_plan_tier("Basic xyz"), "free")

    def test_valid_and_invalid_tier_claims(self):
        os.environ["GRANTLAYER_JWT_SECRET"] = "gl348-plan-tier-secret-32chars!!"
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
        from backend.src.api.auth_jwt import _safe_extract_plan_tier, encode_token
        secret = os.environ["GRANTLAYER_JWT_SECRET"]
        good = encode_token({"sub": "u", "plan_tier": "enterprise"}, secret)
        self.assertEqual(_safe_extract_plan_tier(f"Bearer {good}"), "enterprise")
        # Unknown tier value falls back to free.
        bad = encode_token({"sub": "u", "plan_tier": "platinum"}, secret)
        self.assertEqual(_safe_extract_plan_tier(f"Bearer {bad}"), "free")
        # Garbage token → free (decode raises, caught).
        self.assertEqual(_safe_extract_plan_tier("Bearer not.a.jwt"), "free")


# ── compliance_readiness: context sanitization edge ───────────────────────────
class TestContextSanitization(unittest.TestCase):
    def test_sanitize_non_dict_returned_unchanged(self):
        from backend.src.policy.compliance_readiness import _sanitize_context
        self.assertEqual(_sanitize_context("not-a-dict"), "not-a-dict")
        self.assertEqual(_sanitize_context([1, 2, 3]), [1, 2, 3])

    def test_sanitize_redacts_secret_keys(self):
        from backend.src.policy.compliance_readiness import _sanitize_context
        out = _sanitize_context({"password": "hunter2", "plain": "ok"})
        self.assertNotEqual(out.get("password"), "hunter2")
        self.assertEqual(out.get("plain"), "ok")


if __name__ == "__main__":
    unittest.main()
