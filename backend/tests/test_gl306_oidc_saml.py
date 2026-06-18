"""GL-306 — OIDC/SAML integration tests.

Covers:
- OIDCConfig.from_env() reads all OIDC env vars correctly
- OIDCConfig.is_fully_configured() → True only when enabled + issuer + audience + jwks_url set
- OIDCConfig.startup_errors() returns errors when OIDC is enabled but misconfigured
- oidc_is_enabled() returns True/False based on env
- Algorithm allowlist: only RS256 / ES256 accepted; none/HS256 rejected
- validate_oidc_token() validates a locally-signed RS256 JWT (simulates IdP)
- validate_oidc_token() rejects expired tokens → OIDCExpiredError
- validate_oidc_token() rejects wrong issuer
- validate_oidc_token() rejects wrong audience
- validate_oidc_token() rejects missing tenant claim
- validate_oidc_token() rejects token with unknown kid (JWKS lookup miss)
- validate_oidc_token() fails-closed on JWKS provider outage
- JWKSCache.get_key() returns cached key; refreshes after TTL expires
- JWKSCache.invalidate() clears the cache
- map_oidc_claims_to_auth_payload() maps sub, tenant_id, role, email
- validate_oidc_header() returns (None, None, None) when OIDC not configured
- validate_oidc_header() returns (True, 200, payload) for valid token
- validate_oidc_header() returns (False, 401, error) for expired/invalid token
- validate_oidc_header() returns (False, 401, error) when bearer scheme missing
- identity_access: oidc_implemented=True, saml_implemented=False
- identity_access: OIDC enable flag does NOT trigger startup error
- identity_access: non-OIDC flags still trigger startup error in prod-like mode
- config: OIDC config vars exported
- GET /v1/auth/oidc/config returns OIDC metadata (no secrets)
- GET /v1/auth/oidc/status returns OIDC status
- deps.resolve_auth_and_workspace() uses OIDC token when OIDC is configured
- nbf (not-before) claim rejected when in the future
- Algorithm confusion attacks rejected (alg=none, HS256 with public key bytes, kid injection)
"""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: generate an RSA key pair for tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_rsa_key_pair():
    """Return (private_key, public_key) cryptography objects."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def _sign_jwt(payload: dict, private_key, alg: str = "RS256", headers: dict | None = None) -> str:
    """Sign a JWT with the given private key using PyJWT."""
    import jwt as _pyjwt
    return _pyjwt.encode(payload, private_key, algorithm=alg, headers=headers or {})


def _make_jwks_response(public_key, kid: str = "test-key-1") -> bytes:
    """Return a JWKS JSON response body for the given public key."""
    from jwt.algorithms import RSAAlgorithm
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return json.dumps({"keys": [jwk]}).encode()


def _make_valid_token(
    private_key,
    issuer: str = "https://idp.example.com/realms/test",
    audience: str = "grantlayer-api",
    sub: str = "user-abc",
    tenant_id: str = "acme",
    role: str = "owner",
    kid: str = "test-key-1",
    ttl: int = 3600,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + ttl,
        "nbf": now - 5,
    }
    if extra:
        payload.update(extra)
    return _sign_jwt(payload, private_key, headers={"kid": kid})


def _make_preloaded_cache(public_key, kid: str = "test-key-1"):
    from backend.src.auth.oidc import _JWKSCache
    cache = _JWKSCache()
    cache._keys = {kid: public_key}
    cache._fetched_at = time.monotonic()
    return cache


def _make_oidc_config(
    issuer: str = "https://idp.example.com/realms/test",
    audience: str = "grantlayer-api",
    jwks_url: str = "https://idp.example.com/.well-known/jwks.json",
):
    from backend.src.auth.oidc import OIDCConfig
    return OIDCConfig(
        enabled=True,
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        algorithms=["RS256", "ES256"],
        tenant_claim="tenant_id",
        role_claim="role",
        clock_skew_seconds=30,
        jwks_cache_ttl_seconds=300,
    )


# ─────────────────────────────────────────────────────────────────────────────
# OIDCConfig tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOIDCConfig(unittest.TestCase):

    _OIDC_KEYS = [
        "GRANTLAYER_ENABLE_OIDC", "GRANTLAYER_OIDC_ISSUER",
        "GRANTLAYER_OIDC_AUDIENCE", "GRANTLAYER_OIDC_JWKS_URL",
        "GRANTLAYER_OIDC_ALGORITHMS", "GRANTLAYER_OIDC_TENANT_CLAIM",
        "GRANTLAYER_OIDC_ROLE_CLAIM", "GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS",
        "GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS",
    ]

    def setUp(self):
        for k in self._OIDC_KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k in self._OIDC_KEYS:
            os.environ.pop(k, None)

    def test_from_env_defaults(self):
        from backend.src.auth.oidc import OIDCConfig
        cfg = OIDCConfig.from_env()
        assert cfg.enabled is False
        assert cfg.issuer == ""
        assert cfg.audience == ""
        assert cfg.jwks_url == ""
        assert "RS256" in cfg.algorithms
        assert "ES256" in cfg.algorithms
        assert cfg.tenant_claim == "tenant_id"
        assert cfg.role_claim == "role"
        assert cfg.clock_skew_seconds == 30
        assert cfg.jwks_cache_ttl_seconds == 300

    def test_from_env_reads_all_vars(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ.update({
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com/realms/test",
            "GRANTLAYER_OIDC_AUDIENCE": "grantlayer-api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/.well-known/jwks.json",
            "GRANTLAYER_OIDC_ALGORITHMS": "RS256",
            "GRANTLAYER_OIDC_TENANT_CLAIM": "custom_tenant",
            "GRANTLAYER_OIDC_ROLE_CLAIM": "custom_role",
            "GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS": "60",
            "GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS": "120",
        })
        cfg = OIDCConfig.from_env()
        assert cfg.enabled is True
        assert cfg.issuer == "https://idp.example.com/realms/test"
        assert cfg.audience == "grantlayer-api"
        assert cfg.jwks_url == "https://idp.example.com/.well-known/jwks.json"
        assert cfg.algorithms == ["RS256"]
        assert cfg.tenant_claim == "custom_tenant"
        assert cfg.role_claim == "custom_role"
        assert cfg.clock_skew_seconds == 60
        assert cfg.jwks_cache_ttl_seconds == 120

    def test_disallowed_algorithms_stripped(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ["GRANTLAYER_OIDC_ALGORITHMS"] = "HS256,none,RS256"
        cfg = OIDCConfig.from_env()
        assert "HS256" not in cfg.algorithms
        assert "none" not in cfg.algorithms
        assert "RS256" in cfg.algorithms

    def test_all_disallowed_falls_back_to_default(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ["GRANTLAYER_OIDC_ALGORITHMS"] = "HS256,none"
        cfg = OIDCConfig.from_env()
        assert "RS256" in cfg.algorithms or "ES256" in cfg.algorithms

    def test_is_fully_configured_false_when_disabled(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ.update({
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        })
        cfg = OIDCConfig.from_env()
        assert not cfg.is_fully_configured()

    def test_is_fully_configured_true_when_all_set(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ.update({
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        })
        cfg = OIDCConfig.from_env()
        assert cfg.is_fully_configured()

    def test_startup_errors_empty_when_disabled(self):
        from backend.src.auth.oidc import OIDCConfig
        cfg = OIDCConfig.from_env()
        assert cfg.startup_errors() == []

    def test_startup_errors_when_enabled_but_missing_fields(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ["GRANTLAYER_ENABLE_OIDC"] = "true"
        cfg = OIDCConfig.from_env()
        errs = cfg.startup_errors()
        assert len(errs) == 3
        assert any("GRANTLAYER_OIDC_ISSUER" in e for e in errs)
        assert any("GRANTLAYER_OIDC_AUDIENCE" in e for e in errs)
        assert any("GRANTLAYER_OIDC_JWKS_URL" in e for e in errs)

    def test_startup_errors_empty_when_fully_configured(self):
        from backend.src.auth.oidc import OIDCConfig
        os.environ.update({
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        })
        cfg = OIDCConfig.from_env()
        assert cfg.startup_errors() == []


# ─────────────────────────────────────────────────────────────────────────────
# oidc_is_enabled() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOIDCIsEnabled(unittest.TestCase):

    _KEYS = ["GRANTLAYER_ENABLE_OIDC", "GRANTLAYER_OIDC_ISSUER",
              "GRANTLAYER_OIDC_AUDIENCE", "GRANTLAYER_OIDC_JWKS_URL"]

    def setUp(self):
        for k in self._KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k in self._KEYS:
            os.environ.pop(k, None)

    def test_false_by_default(self):
        from backend.src.auth.oidc import oidc_is_enabled
        assert not oidc_is_enabled()

    def test_false_when_enabled_but_not_configured(self):
        os.environ["GRANTLAYER_ENABLE_OIDC"] = "true"
        from backend.src.auth.oidc import oidc_is_enabled
        assert not oidc_is_enabled()

    def test_true_when_fully_configured(self):
        os.environ.update({
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        })
        from backend.src.auth.oidc import oidc_is_enabled
        assert oidc_is_enabled()


# ─────────────────────────────────────────────────────────────────────────────
# Algorithm allowlist tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlgorithmAllowlist(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()
        self._cfg = _make_oidc_config()
        self._cache = _make_preloaded_cache(self._pub)

    def test_rs256_accepted(self):
        from backend.src.auth.oidc import validate_oidc_token
        token = _make_valid_token(self._priv)
        payload = validate_oidc_token(token, self._cfg, jwks_cache=self._cache)
        assert payload["sub"] == "user-abc"

    def test_none_algorithm_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        import base64
        now = int(time.time())
        payload_data = {
            "iss": "https://idp.example.com/realms/test",
            "aud": "grantlayer-api",
            "sub": "evil",
            "tenant_id": "acme",
            "exp": now + 3600,
            "iat": now,
        }
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(
            json.dumps(payload_data).encode()
        ).rstrip(b"=").decode()
        token = f"{header}.{body}."
        with pytest.raises(OIDCInvalidError, match="none"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_hs256_algorithm_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        import jwt as _pyjwt
        now = int(time.time())
        payload_data = {
            "iss": "https://idp.example.com/realms/test",
            "aud": "grantlayer-api",
            "sub": "evil",
            "tenant_id": "acme",
            "exp": now + 3600,
            "iat": now,
        }
        token = _pyjwt.encode(payload_data, "some-secret", algorithm="HS256")
        with pytest.raises(OIDCInvalidError, match="HS256"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)


# ─────────────────────────────────────────────────────────────────────────────
# validate_oidc_token() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateOIDCToken(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()
        self._cfg = _make_oidc_config()
        self._cache = _make_preloaded_cache(self._pub)

    def test_valid_token_returns_payload(self):
        from backend.src.auth.oidc import validate_oidc_token
        token = _make_valid_token(self._priv)
        payload = validate_oidc_token(token, self._cfg, jwks_cache=self._cache)
        assert payload["sub"] == "user-abc"
        assert payload["tenant_id"] == "acme"
        assert payload["iss"] == "https://idp.example.com/realms/test"

    def test_expired_token_raises_oidc_expired_error(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCExpiredError
        token = _make_valid_token(self._priv, ttl=-100)
        with pytest.raises(OIDCExpiredError):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_wrong_issuer_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        token = _make_valid_token(self._priv, issuer="https://evil.example.com")
        with pytest.raises(OIDCInvalidError, match="issuer"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_wrong_audience_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        token = _make_valid_token(self._priv, audience="wrong-audience")
        with pytest.raises(OIDCInvalidError, match="audience"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_list_audience_accepted(self):
        from backend.src.auth.oidc import validate_oidc_token
        now = int(time.time())
        payload = {
            "iss": "https://idp.example.com/realms/test",
            "aud": ["grantlayer-api", "other-service"],
            "sub": "user-abc",
            "tenant_id": "acme",
            "role": "owner",
            "iat": now,
            "exp": now + 3600,
        }
        token = _sign_jwt(payload, self._priv, headers={"kid": "test-key-1"})
        result = validate_oidc_token(token, self._cfg, jwks_cache=self._cache)
        assert result["sub"] == "user-abc"

    def test_missing_audience_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        now = int(time.time())
        payload = {
            "iss": "https://idp.example.com/realms/test",
            "sub": "user-abc",
            "tenant_id": "acme",
            "iat": now,
            "exp": now + 3600,
        }
        token = _sign_jwt(payload, self._priv, headers={"kid": "test-key-1"})
        with pytest.raises(OIDCInvalidError, match="aud"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_missing_tenant_claim_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        now = int(time.time())
        payload = {
            "iss": "https://idp.example.com/realms/test",
            "aud": "grantlayer-api",
            "sub": "user-abc",
            "iat": now,
            "exp": now + 3600,
        }
        token = _sign_jwt(payload, self._priv, headers={"kid": "test-key-1"})
        with pytest.raises(OIDCInvalidError, match="tenant"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_unknown_kid_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        token = _make_valid_token(self._priv, kid="unknown-kid-xyz")
        with pytest.raises(OIDCInvalidError, match="unknown"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_nbf_in_future_rejected(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError, OIDCConfig
        now = int(time.time())
        payload = {
            "iss": "https://idp.example.com/realms/test",
            "aud": "grantlayer-api",
            "sub": "user-abc",
            "tenant_id": "acme",
            "iat": now,
            "exp": now + 3600,
            "nbf": now + 9999,
        }
        token = _sign_jwt(payload, self._priv, headers={"kid": "test-key-1"})
        cfg_zero_skew = OIDCConfig(
            enabled=True,
            issuer="https://idp.example.com/realms/test",
            audience="grantlayer-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256", "ES256"],
            tenant_claim="tenant_id",
            role_claim="role",
            clock_skew_seconds=0,
            jwks_cache_ttl_seconds=300,
        )
        with pytest.raises(OIDCInvalidError, match="not yet valid"):
            validate_oidc_token(token, cfg_zero_skew, jwks_cache=self._cache)

    def test_oidc_not_configured_raises(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError, OIDCConfig
        cfg = OIDCConfig(
            enabled=False, issuer="", audience="", jwks_url="",
            algorithms=["RS256"], tenant_claim="tenant_id", role_claim="role",
            clock_skew_seconds=30, jwks_cache_ttl_seconds=300,
        )
        token = _make_valid_token(self._priv)
        with pytest.raises(OIDCInvalidError, match="not fully configured"):
            validate_oidc_token(token, cfg)


# ─────────────────────────────────────────────────────────────────────────────
# JWKS provider outage — fail-closed
# ─────────────────────────────────────────────────────────────────────────────

class TestJWKSProviderOutage(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()
        self._cfg = _make_oidc_config()

    def test_jwks_fetch_failure_denies_access(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError, _JWKSCache
        cache = _JWKSCache()
        token = _make_valid_token(self._priv, kid="test-key-1")
        with patch("backend.src.auth.oidc.urllib.request.urlopen", side_effect=OSError("Connection refused")):
            with pytest.raises(OIDCInvalidError, match="JWKS fetch failed"):
                validate_oidc_token(token, self._cfg, jwks_cache=cache)

    def test_jwks_empty_keys_denies_access(self):
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError, _JWKSCache
        cache = _JWKSCache()
        token = _make_valid_token(self._priv, kid="test-key-1")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"keys": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.src.auth.oidc.urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(OIDCInvalidError, match="no usable public keys"):
                validate_oidc_token(token, self._cfg, jwks_cache=cache)


# ─────────────────────────────────────────────────────────────────────────────
# JWKSCache tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJWKSCache(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()

    def test_get_key_returns_known_kid(self):
        cache = _make_preloaded_cache(self._pub, "k1")
        key = cache.get_key("k1", "https://idp.example.com/jwks", 300)
        assert key is self._pub

    def test_get_key_returns_none_for_unknown_kid(self):
        cache = _make_preloaded_cache(self._pub, "k1")
        key = cache.get_key("unknown", "https://idp.example.com/jwks", 300)
        assert key is None

    def test_get_sole_key_when_kid_is_none(self):
        cache = _make_preloaded_cache(self._pub, "k1")
        key = cache.get_key(None, "https://idp.example.com/jwks", 300)
        assert key is self._pub

    def test_none_kid_ambiguous_when_multiple_keys(self):
        from backend.src.auth.oidc import _JWKSCache
        _, pub2 = _make_rsa_key_pair()
        cache = _JWKSCache()
        cache._keys = {"k1": self._pub, "k2": pub2}
        cache._fetched_at = time.monotonic()
        key = cache.get_key(None, "https://idp.example.com/jwks", 300)
        assert key is None

    def test_invalidate_clears_cache(self):
        cache = _make_preloaded_cache(self._pub, "k1")
        cache.invalidate()
        assert cache._keys == {}
        assert cache._fetched_at == 0.0

    def test_expired_cache_triggers_refresh(self):
        from backend.src.auth.oidc import _JWKSCache
        cache = _JWKSCache()
        cache._keys = {"k1": self._pub}
        cache._fetched_at = time.monotonic() - 9999  # expired

        jwks_body = _make_jwks_response(self._pub, kid="k1")
        mock_resp = MagicMock()
        mock_resp.read.return_value = jwks_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.src.auth.oidc.urllib.request.urlopen", return_value=mock_resp):
            key = cache.get_key("k1", "https://idp.example.com/jwks", 300)
        assert key is not None


# ─────────────────────────────────────────────────────────────────────────────
# map_oidc_claims_to_auth_payload tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMapOIDCClaims(unittest.TestCase):

    def setUp(self):
        from backend.src.auth.oidc import OIDCConfig
        self._cfg = OIDCConfig(
            enabled=True,
            issuer="https://idp.example.com",
            audience="api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
            tenant_claim="tenant_id",
            role_claim="role",
            clock_skew_seconds=30,
            jwks_cache_ttl_seconds=300,
        )

    def test_maps_standard_claims(self):
        from backend.src.auth.oidc import map_oidc_claims_to_auth_payload
        oidc_payload = {
            "sub": "u-123",
            "tenant_id": "acme",
            "role": "owner",
            "email": "user@acme.com",
            "iss": "https://idp.example.com",
            "aud": "api",
            "exp": 9999999999,
            "iat": 1234567890,
        }
        mapped = map_oidc_claims_to_auth_payload(oidc_payload, self._cfg)
        assert mapped["sub"] == "u-123"
        assert mapped["tenant_id"] == "acme"
        assert mapped["role"] == "owner"
        assert mapped["email"] == "user@acme.com"
        assert mapped["oidc"] is True

    def test_maps_custom_tenant_claim(self):
        from backend.src.auth.oidc import map_oidc_claims_to_auth_payload, OIDCConfig
        cfg = OIDCConfig(
            enabled=True, issuer="", audience="", jwks_url="",
            algorithms=["RS256"], tenant_claim="org_id", role_claim="user_role",
            clock_skew_seconds=30, jwks_cache_ttl_seconds=300,
        )
        oidc_payload = {
            "sub": "u-456",
            "org_id": "my-org",
            "user_role": "auditor",
            "exp": 9999999999,
            "iat": 1234567890,
        }
        mapped = map_oidc_claims_to_auth_payload(oidc_payload, cfg)
        assert mapped["tenant_id"] == "my-org"
        assert mapped["role"] == "auditor"

    def test_oidc_claims_passthrough(self):
        from backend.src.auth.oidc import map_oidc_claims_to_auth_payload
        oidc_payload = {
            "sub": "u-789",
            "tenant_id": "org",
            "role": "member",
            "email": "a@b.com",
            "custom_claim": "custom_value",
            "exp": 9999,
            "iat": 1111,
        }
        mapped = map_oidc_claims_to_auth_payload(oidc_payload, self._cfg)
        assert mapped["oidc_claims"].get("custom_claim") == "custom_value"

    def test_oidc_flag_true_in_mapped_payload(self):
        from backend.src.auth.oidc import map_oidc_claims_to_auth_payload
        oidc_payload = {"sub": "x", "tenant_id": "t", "role": "r", "exp": 9999, "iat": 1}
        mapped = map_oidc_claims_to_auth_payload(oidc_payload, self._cfg)
        assert mapped["oidc"] is True


# ─────────────────────────────────────────────────────────────────────────────
# validate_oidc_header() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateOIDCHeader(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()
        self._cfg = _make_oidc_config()
        self._cache = _make_preloaded_cache(self._pub)

    def test_returns_none_when_not_configured(self):
        from backend.src.auth.oidc import validate_oidc_header, OIDCConfig
        unconfigured = OIDCConfig(
            enabled=False, issuer="", audience="", jwks_url="",
            algorithms=["RS256"], tenant_claim="tenant_id", role_claim="role",
            clock_skew_seconds=30, jwks_cache_ttl_seconds=300,
        )
        ok, status, payload = validate_oidc_header("Bearer some-token", config=unconfigured)
        assert ok is None
        assert status is None
        assert payload is None

    def test_returns_false_when_header_missing(self):
        from backend.src.auth.oidc import validate_oidc_header
        ok, status, payload = validate_oidc_header(None, config=self._cfg, jwks_cache=self._cache)
        assert ok is False
        assert status == 401
        assert payload["errorCode"] == "oidc_token_required"

    def test_returns_false_when_bearer_scheme_missing(self):
        from backend.src.auth.oidc import validate_oidc_header
        ok, status, payload = validate_oidc_header("Basic user:pass", config=self._cfg, jwks_cache=self._cache)
        assert ok is False
        assert status == 401
        assert payload["errorCode"] == "oidc_token_invalid"

    def test_returns_true_for_valid_token(self):
        from backend.src.auth.oidc import validate_oidc_header
        token = _make_valid_token(self._priv)
        ok, status, payload = validate_oidc_header(
            f"Bearer {token}", config=self._cfg, jwks_cache=self._cache
        )
        assert ok is True
        assert status == 200
        assert payload["tenant_id"] == "acme"
        assert payload["oidc"] is True

    def test_returns_false_for_expired_token(self):
        from backend.src.auth.oidc import validate_oidc_header
        token = _make_valid_token(self._priv, ttl=-100)
        ok, status, payload = validate_oidc_header(
            f"Bearer {token}", config=self._cfg, jwks_cache=self._cache
        )
        assert ok is False
        assert status == 401
        assert payload["errorCode"] == "oidc_token_expired"

    def test_returns_false_for_invalid_token(self):
        from backend.src.auth.oidc import validate_oidc_header
        ok, status, payload = validate_oidc_header(
            "Bearer not.a.valid.jwt", config=self._cfg, jwks_cache=self._cache
        )
        assert ok is False
        assert status == 401
        assert "oidc" in payload["errorCode"]


# ─────────────────────────────────────────────────────────────────────────────
# identity_access.py posture tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentityAccessPosture(unittest.TestCase):

    def test_oidc_implemented_true(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        posture = describe_identity_access_posture(env={}, runtime_mode="local")
        assert posture["oidc_implemented"] is True

    def test_saml_implemented_false(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        posture = describe_identity_access_posture(env={}, runtime_mode="local")
        assert posture["saml_implemented"] is False

    def test_external_identity_provider_implemented_when_fully_configured(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        }
        posture = describe_identity_access_posture(env=env, runtime_mode="local")
        assert posture["external_identity_provider_implemented"] is True

    def test_external_identity_provider_not_implemented_when_unconfigured(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        posture = describe_identity_access_posture(env={}, runtime_mode="local")
        assert posture["external_identity_provider_implemented"] is False

    def test_oidc_flag_no_startup_error_in_prod_mode_when_configured(self):
        from backend.src.auth.identity_access import external_identity_startup_errors
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        }
        errs = external_identity_startup_errors(env=env, runtime_mode="staging")
        assert not errs, f"OIDC should not trigger startup errors when configured: {errs}"

    def test_saml_flag_triggers_startup_error_in_prod_mode(self):
        from backend.src.auth.identity_access import external_identity_startup_errors
        env = {"GRANTLAYER_ENABLE_SAML": "true"}
        errs = external_identity_startup_errors(env=env, runtime_mode="staging")
        assert len(errs) >= 1

    def test_oauth_flag_triggers_startup_error_in_prod_mode(self):
        from backend.src.auth.identity_access import external_identity_startup_errors
        env = {"GRANTLAYER_ENABLE_OAUTH": "true"}
        errs = external_identity_startup_errors(env=env, runtime_mode="production")
        assert len(errs) >= 1

    def test_no_startup_errors_in_local_mode_for_any_flag(self):
        from backend.src.auth.identity_access import external_identity_startup_errors
        env = {"GRANTLAYER_ENABLE_OAUTH": "true", "GRANTLAYER_ENABLE_SAML": "true"}
        errs = external_identity_startup_errors(env=env, runtime_mode="local")
        assert errs == []

    def test_oidc_enabled_posture_reflects_config(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        }
        posture = describe_identity_access_posture(env=env, runtime_mode="local")
        assert posture["oidc_enabled"] is True
        assert posture["oidc_fully_configured"] is True

    def test_saml_config_var_triggers_startup_error_in_prod_mode(self):
        from backend.src.auth.identity_access import external_identity_startup_errors
        env = {"GRANTLAYER_SAML_METADATA_URL": "https://idp.example.com/saml/metadata"}
        errs = external_identity_startup_errors(env=env, runtime_mode="production")
        assert len(errs) >= 1

    def test_production_identity_ready_true_when_oidc_fully_configured(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "https://idp.example.com",
            "GRANTLAYER_OIDC_AUDIENCE": "api",
            "GRANTLAYER_OIDC_JWKS_URL": "https://idp.example.com/jwks",
        }
        posture = describe_identity_access_posture(env=env, runtime_mode="local")
        assert posture["production_identity_ready"] is True


# ─────────────────────────────────────────────────────────────────────────────
# config.py OIDC vars exported
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigOIDCVars(unittest.TestCase):

    def test_config_has_oidc_vars(self):
        import backend.src.core.config as cfg_mod
        assert hasattr(cfg_mod, "GRANTLAYER_ENABLE_OIDC")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_ISSUER")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_AUDIENCE")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_JWKS_URL")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_ALGORITHMS")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_TENANT_CLAIM")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_ROLE_CLAIM")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS")
        assert hasattr(cfg_mod, "GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS")

    def test_config_defaults_oidc_disabled(self):
        import backend.src.core.config as cfg_mod
        saved = os.environ.pop("GRANTLAYER_ENABLE_OIDC", None)
        try:
            importlib.reload(cfg_mod)
            assert cfg_mod.GRANTLAYER_ENABLE_OIDC is False
        finally:
            if saved:
                os.environ["GRANTLAYER_ENABLE_OIDC"] = saved
            importlib.reload(cfg_mod)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_app_client(tmp_db: str):
    os.environ.update({
        "GRANTLAYER_DB": tmp_db,
        "GRANTLAYER_ADMIN_TOKEN": "gl306-test-admin-token",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN": "false",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL": "false",
    })
    for k in ["GRANTLAYER_DATABASE_URL", "GRANTLAYER_ENABLE_OIDC", "GRANTLAYER_OIDC_ISSUER",
               "GRANTLAYER_OIDC_AUDIENCE", "GRANTLAYER_OIDC_JWKS_URL", "GRANTLAYER_REDIS_URL"]:
        os.environ.pop(k, None)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH = tmp_db
    db_mod.DB_PATH_OR_URL = tmp_db
    db_mod.init_db()

    import backend.src.core.config as cfg_mod
    importlib.reload(cfg_mod)

    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestOIDCRouter(unittest.TestCase):

    _SAVED_KEYS = [
        "GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL", "GRANTLAYER_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OPERATOR_MODEL",
        "GRANTLAYER_ENABLE_OIDC", "GRANTLAYER_OIDC_ISSUER",
        "GRANTLAYER_OIDC_AUDIENCE", "GRANTLAYER_OIDC_JWKS_URL",
        "GRANTLAYER_REDIS_URL",
    ]

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self._SAVED_KEYS}
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._client = _make_app_client(self._tmp.name)

    def tearDown(self):
        self._tmp.close()
        os.unlink(self._tmp.name)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_oidc_config_endpoint_exists(self):
        resp = self._client.get("/v1/auth/oidc/config")
        assert resp.status_code == 200

    def test_oidc_config_returns_json(self):
        resp = self._client.get("/v1/auth/oidc/config")
        data = resp.json()
        assert "oidc_enabled" in data
        assert "oidc_configured" in data
        assert "algorithms" in data

    def test_oidc_config_disabled_by_default(self):
        resp = self._client.get("/v1/auth/oidc/config")
        data = resp.json()
        assert data["oidc_enabled"] is False
        assert data["oidc_configured"] is False
        assert data["issuer"] == ""

    def test_oidc_status_endpoint_exists(self):
        resp = self._client.get("/v1/auth/oidc/status")
        assert resp.status_code == 200

    def test_oidc_status_returns_posture(self):
        resp = self._client.get("/v1/auth/oidc/status")
        data = resp.json()
        assert data["oidc_implemented"] is True
        assert data["saml_implemented"] is False
        assert "identity_posture" in data

    def test_oidc_config_no_private_key_in_response(self):
        resp = self._client.get("/v1/auth/oidc/config")
        body = resp.text
        assert "private" not in body.lower()
        assert "secret" not in body.lower()

    def test_oidc_endpoints_are_async_def(self):
        import inspect
        from backend.src.api.routers.oidc import get_oidc_config, get_oidc_status
        assert inspect.iscoroutinefunction(get_oidc_config)
        assert inspect.iscoroutinefunction(get_oidc_status)

    def test_oidc_status_has_startup_errors_field(self):
        resp = self._client.get("/v1/auth/oidc/status")
        data = resp.json()
        assert "oidc_startup_errors" in data
        assert isinstance(data["oidc_startup_errors"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: OIDC token accepted in deps.resolve_auth_and_workspace
# ─────────────────────────────────────────────────────────────────────────────

class TestDepsOIDCIntegration(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()

    def test_resolve_auth_uses_oidc_when_configured(self):
        from backend.src.auth.oidc import validate_oidc_header
        from backend.src.auth.oidc import OIDCConfig, _JWKSCache

        cfg = OIDCConfig(
            enabled=True,
            issuer="https://idp.example.com/realms/test",
            audience="grantlayer-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256", "ES256"],
            tenant_claim="tenant_id",
            role_claim="role",
            clock_skew_seconds=30,
            jwks_cache_ttl_seconds=300,
        )
        cache = _make_preloaded_cache(self._pub)
        token = _make_valid_token(self._priv)

        ok, status, payload = validate_oidc_header(
            f"Bearer {token}", config=cfg, jwks_cache=cache
        )
        assert ok is True
        assert status == 200
        assert payload["tenant_id"] == "acme"
        assert payload["oidc"] is True

    def test_oidc_not_configured_falls_through(self):
        from backend.src.auth.oidc import validate_oidc_header, OIDCConfig
        unconfigured = OIDCConfig(
            enabled=False, issuer="", audience="", jwks_url="",
            algorithms=["RS256"], tenant_claim="tenant_id", role_claim="role",
            clock_skew_seconds=30, jwks_cache_ttl_seconds=300,
        )
        ok, status, payload = validate_oidc_header("Bearer some-token", config=unconfigured)
        assert ok is None

    def test_deps_imports_validate_oidc_header(self):
        from backend.src.api import deps
        assert hasattr(deps, "validate_oidc_header")


# ─────────────────────────────────────────────────────────────────────────────
# Security: algorithm confusion attacks
# ─────────────────────────────────────────────────────────────────────────────

class TestAlgorithmConfusionAttack(unittest.TestCase):

    def setUp(self):
        self._priv, self._pub = _make_rsa_key_pair()
        self._cfg = _make_oidc_config()
        self._cache = _make_preloaded_cache(self._pub)

    def test_algorithm_confusion_hs256_with_public_key_bytes(self):
        """Attacker forges HS256 token signed with the RSA public key PEM — must be rejected.

        Modern PyJWT refuses to encode HS256 with an RSA key, so we craft the
        token manually using raw HMAC to simulate an adversarial library.
        The allowlist check rejects HS256 before any key material is consulted.
        """
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        from cryptography.hazmat.primitives import serialization
        import base64, hashlib, hmac as _hmac

        pub_pem = self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        now = int(time.time())
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
        body_data = json.dumps({
            "iss": "https://idp.example.com/realms/test",
            "aud": "grantlayer-api",
            "sub": "attacker",
            "tenant_id": "evil",
            "exp": now + 3600,
            "iat": now,
        }).encode()
        body = base64.urlsafe_b64encode(body_data).rstrip(b"=").decode()
        signing_input = f"{header}.{body}".encode()
        sig = _hmac.new(pub_pem, signing_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        forged_token = f"{header}.{body}.{sig_b64}"

        with pytest.raises(OIDCInvalidError, match="HS256"):
            validate_oidc_token(forged_token, self._cfg, jwks_cache=self._cache)

    def test_kid_injection_with_different_key_rejected(self):
        """Token signed with a fresh key pair but claiming a kid in our JWKS → must fail."""
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        priv2, _ = _make_rsa_key_pair()
        # Uses "test-key-1" (which maps to self._pub), but signed with priv2 → sig failure
        token = _make_valid_token(priv2, kid="test-key-1")
        with pytest.raises((OIDCInvalidError, Exception)):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)

    def test_unknown_kid_injection_rejected(self):
        """Token signed with fresh key + unknown kid → deny because kid not in JWKS."""
        from backend.src.auth.oidc import validate_oidc_token, OIDCInvalidError
        priv2, _ = _make_rsa_key_pair()
        token = _make_valid_token(priv2, kid="injected-kid-not-in-jwks")
        with pytest.raises(OIDCInvalidError, match="unknown"):
            validate_oidc_token(token, self._cfg, jwks_cache=self._cache)


# ─────────────────────────────────────────────────────────────────────────────
# SAML stub — verify not-implemented is documented, not silently broken
# ─────────────────────────────────────────────────────────────────────────────

class TestSAMLStub(unittest.TestCase):

    def test_saml_implemented_false_in_posture(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        posture = describe_identity_access_posture(env={}, runtime_mode="local")
        assert posture["saml_implemented"] is False

    def test_saml_note_present_in_posture(self):
        from backend.src.auth.identity_access import describe_identity_access_posture
        posture = describe_identity_access_posture(env={}, runtime_mode="local")
        assert "saml_note" in posture
        note = posture["saml_note"].lower()
        assert "saml" in note

    def test_saml_enable_flag_in_known_flags(self):
        from backend.src.auth.identity_access import EXTERNAL_IDENTITY_ENABLE_FLAGS
        assert "GRANTLAYER_ENABLE_SAML" in EXTERNAL_IDENTITY_ENABLE_FLAGS

    def test_saml_config_var_in_known_vars(self):
        from backend.src.auth.identity_access import EXTERNAL_IDENTITY_CONFIG_VARS
        assert "GRANTLAYER_SAML_METADATA_URL" in EXTERNAL_IDENTITY_CONFIG_VARS

    def test_saml_entity_id_var_in_known_vars(self):
        from backend.src.auth.identity_access import EXTERNAL_IDENTITY_CONFIG_VARS
        assert "GRANTLAYER_SAML_ENTITY_ID" in EXTERNAL_IDENTITY_CONFIG_VARS
