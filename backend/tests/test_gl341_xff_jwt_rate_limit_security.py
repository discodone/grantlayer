"""GL-341 — Security regression: XFF rate-limit bypass and unverified JWT decode.

These tests FAIL against the unpatched code and PASS after the GL-341 fix.

Exploit surface covered:
  (a) Spoofed X-Forwarded-For from untrusted peer bypasses rate limiting by
      creating a fresh bucket per spoofed IP.
  (b) Base64-decoded (unsigned) JWT claim allows attacker to self-assign
      elevated plan_tier and raise their own rate-limit ceiling.
  (c) GRANTLAYER_RUNTIME_MODE unset defaults to 'local', silently skipping the
      startup gate and its production-config safety checks.
"""

from __future__ import annotations

import base64
import json
import os
import time
import unittest

_TEST_SECRET = "gl341-test-hs256-secret-32chars!!"


def _make_client():
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _make_client_with_jwt():
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestXffUntrustedPeer(unittest.TestCase):
    """(a) XFF from an untrusted peer must not override rate-limit keying."""

    def test_spoofed_xff_from_untrusted_peer_uses_direct_ip(self):
        """Rate-limit key must be the real peer IP, not a spoofed X-Forwarded-For value.

        A peer that is NOT in TRUSTED_PROXY_CIDRS (default: empty) must never
        influence which rate-limit bucket is used by sending a fake XFF header.
        """
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app

        app = create_app()
        captured_ips: list[str] = []
        original_check = app.state.auth_rate_limiter.check

        def spy(client_ip: str, *args, **kwargs):
            captured_ips.append(client_ip)
            return original_check(client_ip, *args, **kwargs)

        app.state.auth_rate_limiter.check = spy
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/v1/grants", headers={"X-Forwarded-For": "203.0.113.42"})
        self.assertNotIn(
            "203.0.113.42",
            captured_ips,
            "spoofed X-Forwarded-For must not be used as the rate-limit key "
            "from an untrusted peer",
        )

    def test_xff_rotation_cannot_bypass_rate_limit(self):
        """Rotating X-Forwarded-For values must not bypass the rate limit.

        An attacker sending a different spoofed IP on each request must still
        be keyed by the real peer address and hit the 429 threshold.
        """
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        from backend.src.core.rate_limiter import RateLimiter

        app = create_app()
        # Replace with a very tight in-process limiter: 1 req/min for the api group
        app.state.auth_rate_limiter = RateLimiter(api_limit=1, window_seconds=60)
        client = TestClient(app, raise_server_exceptions=False)

        # First request: exhausts the quota for the real peer IP ("testclient")
        client.get("/v1/grants")
        # Second request with a different spoofed XFF IP must still be blocked
        r2 = client.get("/v1/grants", headers={"X-Forwarded-For": "203.0.113.99"})
        self.assertEqual(
            r2.status_code,
            429,
            "rotating X-Forwarded-For must not bypass the rate limit — "
            f"expected 429, got {r2.status_code}",
        )


class TestJwtPlanTierVerification(unittest.TestCase):
    """(b) plan_tier must only be set from a signature-verified JWT."""

    def setUp(self):
        self._orig_secret = os.environ.get("GRANTLAYER_JWT_SECRET")

    def tearDown(self):
        if self._orig_secret is None:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        else:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_secret

    def test_forged_jwt_does_not_grant_elevated_tier(self):
        """JWT with a forged signature claiming plan_tier=enterprise must yield 'free' tier.

        An attacker who constructs a JWT with a valid-looking payload but an
        invalid signature must not be able to elevate their rate-limit tier.
        """
        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
        raw_header = b'{"alg":"HS256","typ":"JWT"}'
        raw_payload = json.dumps({
            "sub": "attacker",
            "tenant_id": "t1",
            "plan_tier": "enterprise",
            "iss": "grantlayer",
            "aud": "grantlayer-api",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }).encode()
        enc_header = base64.urlsafe_b64encode(raw_header).rstrip(b"=").decode()
        enc_payload = base64.urlsafe_b64encode(raw_payload).rstrip(b"=").decode()
        forged_token = f"{enc_header}.{enc_payload}.forged-invalid-signature"

        client = _make_client_with_jwt()
        resp = client.get(
            "/v1/grants",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        self.assertEqual(
            resp.headers.get("x-plan-tier", ""),
            "free",
            "forged JWT must not grant elevated plan tier — signature must be verified",
        )

    def test_expired_jwt_does_not_grant_elevated_tier(self):
        """An expired JWT claiming plan_tier=enterprise must yield 'free' tier.

        An attacker replaying an expired token must not retain the elevated
        rate-limit tier the token once carried.
        """
        import jwt as _pyjwt

        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
        now = int(time.time())
        expired_token = _pyjwt.encode(
            {
                "sub": "user",
                "tenant_id": "t1",
                "plan_tier": "enterprise",
                "iss": "grantlayer",
                "aud": "grantlayer-api",
                "exp": now - 3600,
                "iat": now - 7200,
            },
            _TEST_SECRET,
            algorithm="HS256",
        )
        client = _make_client_with_jwt()
        resp = client.get(
            "/v1/grants",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        self.assertEqual(
            resp.headers.get("x-plan-tier", ""),
            "free",
            "expired JWT must not grant elevated plan tier",
        )


class TestStartupGateDefault(unittest.TestCase):
    """(c) Unset GRANTLAYER_RUNTIME_MODE must default fail-closed (run the gate)."""

    def test_get_runtime_mode_defaults_to_production_when_unset(self):
        """Unset GRANTLAYER_RUNTIME_MODE must resolve to a production-like mode.

        Without this, an operator who forgets to set the env var boots in
        insecure local mode and the startup gate never runs.
        """
        from backend.src.core.runtime_config import get_runtime_mode, PRODUCTION_LIKE_MODES

        mode = get_runtime_mode({})  # empty dict = GRANTLAYER_RUNTIME_MODE not set
        self.assertIn(
            mode,
            PRODUCTION_LIKE_MODES,
            f"Unset GRANTLAYER_RUNTIME_MODE should default to a production-like mode, "
            f"got {mode!r}. Current DEFAULT_MODE must be changed from 'local' to 'production'.",
        )
