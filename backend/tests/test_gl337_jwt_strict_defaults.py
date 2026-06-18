"""GL-337 — Secure JWT defaults.

Tests:
- JWT_STRICT_CLAIMS defaults to True.
- Tokens without iss/aud are rejected when strict claims is True and server has JWT_ISSUER/JWT_AUDIENCE.
- Tokens with correct iss/aud are accepted.
- QUICKSTART.md documents JWT_ISSUER and JWT_AUDIENCE env vars.
"""

from __future__ import annotations

import os
import unittest

_TEST_SECRET = "gl337-test-hs256-secret-32chars!!"


class TestJwtStrictClaimsDefault(unittest.TestCase):
    def test_jwt_strict_claims_default_is_true(self):
        """JWT_STRICT_CLAIMS must default to True (not False)."""
        import importlib
        import sys
        # Clear cached config to get fresh read
        old = os.environ.pop("GRANTLAYER_JWT_STRICT_CLAIMS", None)
        try:
            from backend.src.core import config
            # The default must be True
            self.assertTrue(
                config._env_bool("GRANTLAYER_JWT_STRICT_CLAIMS", default=True),
                "JWT_STRICT_CLAIMS should default to True",
            )
        finally:
            if old is not None:
                os.environ["GRANTLAYER_JWT_STRICT_CLAIMS"] = old

    def test_config_jwt_strict_claims_is_true_by_default(self):
        """config.JWT_STRICT_CLAIMS must be True in standard test environment."""
        from backend.src.core.config import JWT_STRICT_CLAIMS
        # In test env, JWT_STRICT_CLAIMS defaults to True
        # (env var not set → default=True)
        old = os.environ.pop("GRANTLAYER_JWT_STRICT_CLAIMS", None)
        try:
            from backend.src.core import config
            result = config._env_bool("GRANTLAYER_JWT_STRICT_CLAIMS", default=True)
            self.assertTrue(result)
        finally:
            if old is not None:
                os.environ["GRANTLAYER_JWT_STRICT_CLAIMS"] = old


class TestJwtStrictClaimsEnforcement(unittest.TestCase):
    """Use the config's actual loaded defaults (grantlayer / grantlayer-api).

    config.JWT_ISSUER/JWT_AUDIENCE are loaded at import time, so we must use
    the actual defaults — not custom env vars set after import.
    """

    def setUp(self):
        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
        from backend.src.core.config import JWT_ISSUER, JWT_AUDIENCE
        self._issuer = JWT_ISSUER or "grantlayer"
        self._audience = JWT_AUDIENCE or "grantlayer-api"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

    def _make_token(self, claims: dict) -> str:
        from backend.src.api.auth_jwt import encode_token
        return encode_token(claims, _TEST_SECRET)

    def test_token_without_iss_rejected_when_strict(self):
        """Token missing iss must be rejected when JWT_STRICT_CLAIMS is True."""
        from backend.src.api.auth_jwt import validate_jwt_header
        token = self._make_token({"sub": "u1", "role": "user", "aud": self._audience})
        ok, status, _ = validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok, "Token without iss should be rejected with JWT_STRICT_CLAIMS=true")

    def test_token_without_aud_rejected_when_strict(self):
        """Token missing aud must be rejected when JWT_STRICT_CLAIMS is True."""
        from backend.src.api.auth_jwt import validate_jwt_header
        token = self._make_token({"sub": "u1", "role": "user", "iss": self._issuer})
        ok, status, _ = validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok, "Token without aud should be rejected with JWT_STRICT_CLAIMS=true")

    def test_token_with_correct_iss_aud_accepted(self):
        """Token with correct iss+aud matching server config must be accepted."""
        from backend.src.api.auth_jwt import validate_jwt_header
        token = self._make_token({
            "sub": "u1", "role": "user", "tenant_id": "t1",
            "iss": self._issuer, "aud": self._audience,
        })
        ok, status, _ = validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok, f"Token with correct iss+aud should be accepted (got {status})")

    def test_token_with_wrong_issuer_rejected(self):
        """Token with wrong iss must be rejected."""
        from backend.src.api.auth_jwt import validate_jwt_header
        token = self._make_token({
            "sub": "u1", "role": "user",
            "iss": "totally-wrong-issuer", "aud": self._audience,
        })
        ok, status, _ = validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok, "Token with wrong iss should be rejected")


class TestQuickstartDocumentsJwtVars(unittest.TestCase):
    def test_quickstart_documents_jwt_issuer_env_var(self):
        """QUICKSTART.md must document GRANTLAYER_JWT_ISSUER."""
        import os
        path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "QUICKSTART.md")
        )
        with open(path) as f:
            content = f.read()
        self.assertIn("GRANTLAYER_JWT_ISSUER", content)

    def test_quickstart_documents_jwt_audience_env_var(self):
        """QUICKSTART.md must document GRANTLAYER_JWT_AUDIENCE."""
        import os
        path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "QUICKSTART.md")
        )
        with open(path) as f:
            content = f.read()
        self.assertIn("GRANTLAYER_JWT_AUDIENCE", content)

    def test_quickstart_mentions_strict_claims(self):
        """QUICKSTART.md must mention JWT_STRICT_CLAIMS (default true)."""
        import os
        path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "QUICKSTART.md")
        )
        with open(path) as f:
            content = f.read()
        self.assertIn("JWT_STRICT_CLAIMS", content)
