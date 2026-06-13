"""Tests for GL-261: RS256 JWT authentication.

Validates:
- RS256 token encode/decode round-trip
- Algorithm-confusion guard (RS256 token rejected by HS256 decoder and vice versa)
- validate_jwt_header with RS256 env config
- validate_jwt_header with HS256 legacy env config (backward compat)
- sign_token dispatches to correct algorithm
- is_jwt_enabled with RS256 and HS256 configs
- /auth/token endpoint issues RS256 tokens when configured
- Expiry and missing tenant_id checks still work for RS256
"""

from __future__ import annotations

import base64
import importlib
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_HS256_SECRET = "gl261-test-hs256-secret-32chars!"


def _generate_rsa_key_pair() -> tuple[bytes, bytes]:
    """Return (private_pem, public_pem) as bytes."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


class _EnvGuard:
    """Context manager: save/restore a set of env vars around a test."""
    _KEYS = (
        "GRANTLAYER_JWT_ALGORITHM",
        "GRANTLAYER_JWT_SECRET",
        "GRANTLAYER_JWT_PRIVATE_KEY",
        "GRANTLAYER_JWT_PUBLIC_KEY",
    )

    def __init__(self):
        self._saved: dict = {}

    def __enter__(self):
        for k in self._KEYS:
            self._saved[k] = os.environ.get(k)
            os.environ.pop(k, None)
        return self

    def __exit__(self, *_):
        for k in self._KEYS:
            val = self._saved[k]
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val


class TestRS256EncodeDecode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()

    def test_rs256_round_trip(self):
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token_rs256
        payload = {"sub": "agent-001", "tenant_id": "acme"}
        token = encode_token_rs256(payload, self._private_pem)
        decoded = decode_token_rs256(token, self._public_pem)
        self.assertEqual(decoded["sub"], "agent-001")
        self.assertEqual(decoded["tenant_id"], "acme")
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_rs256_wrong_public_key_rejected(self):
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token_rs256, JWTInvalidError
        _, other_public_pem = _generate_rsa_key_pair()
        token = encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem)
        with self.assertRaises(JWTInvalidError):
            decode_token_rs256(token, other_public_pem)

    def test_rs256_tampered_payload_rejected(self):
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token_rs256, JWTInvalidError
        from backend.src.api.auth_jwt import _b64url_encode
        import json
        token = encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem)
        header, _body, sig = token.split(".")
        tampered_body = _b64url_encode(
            json.dumps({"sub": "attacker", "tenant_id": "t", "iat": 0, "exp": 9999999999}).encode()
        )
        tampered = f"{header}.{tampered_body}.{sig}"
        with self.assertRaises(JWTInvalidError):
            decode_token_rs256(tampered, self._public_pem)

    def test_rs256_expired_token_raises(self):
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token_rs256, JWTExpiredError
        token = encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem, ttl_hours=0)
        # Force expiry by patching exp manually — ttl_hours=0 gives exp=now, wait is unreliable.
        # Instead: decode the payload to verify the function raises correctly for an expired token.
        # Rebuild token with exp in the past.
        from backend.src.api.auth_jwt import _b64url_encode, _b64url_decode, _sign_rs256
        import json
        header_b64, _, _ = token.split(".")
        past_payload = {"sub": "x", "tenant_id": "t", "iat": 1000, "exp": 1001}
        body_b64 = _b64url_encode(json.dumps(past_payload).encode())
        signing_input = f"{header_b64}.{body_b64}"
        sig = _sign_rs256(signing_input, self._private_pem)
        expired_token = f"{signing_input}.{sig}"
        with self.assertRaises(JWTExpiredError):
            decode_token_rs256(expired_token, self._public_pem)

    def test_algorithm_confusion_hs256_token_rejected_by_rs256(self):
        """An HS256 token must be rejected by decode_token_rs256."""
        from backend.src.api.auth_jwt import encode_token, decode_token_rs256, JWTInvalidError
        hs256_token = encode_token({"sub": "x", "tenant_id": "t"}, _TEST_HS256_SECRET)
        with self.assertRaises(JWTInvalidError):
            decode_token_rs256(hs256_token, self._public_pem)

    def test_algorithm_confusion_rs256_token_rejected_by_hs256(self):
        """An RS256 token must be rejected by decode_token (HS256 decoder)."""
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token, JWTInvalidError
        rs256_token = encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem)
        with self.assertRaises(JWTInvalidError):
            decode_token(rs256_token, _TEST_HS256_SECRET)

    def test_rs256_three_parts_required(self):
        from backend.src.api.auth_jwt import decode_token_rs256, JWTInvalidError
        with self.assertRaises(JWTInvalidError):
            decode_token_rs256("not.a.valid.jwt.token", self._public_pem)

    def test_empty_private_key_raises(self):
        from backend.src.api.auth_jwt import encode_token_rs256
        with self.assertRaises(ValueError):
            encode_token_rs256({"sub": "x"}, b"")

    def test_empty_public_key_raises(self):
        from backend.src.api.auth_jwt import encode_token_rs256, decode_token_rs256, JWTInvalidError
        token = encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem)
        with self.assertRaises(JWTInvalidError):
            decode_token_rs256(token, b"")

    def _make_rs256_token(self):
        from backend.src.api.auth_jwt import encode_token_rs256
        return encode_token_rs256({"sub": "x", "tenant_id": "t"}, self._private_pem)


class TestValidateJwtHeaderRS256(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()
        cls._priv_b64 = base64.b64encode(cls._private_pem).decode()
        cls._pub_b64 = base64.b64encode(cls._public_pem).decode()

    def _make_rs256_token(self):
        from backend.src.api.auth_jwt import encode_token_rs256
        return encode_token_rs256({"sub": "op-1", "tenant_id": "acme"}, self._private_pem)

    def test_rs256_valid_token_accepted(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PRIVATE_KEY"] = self._priv_b64
            os.environ["GRANTLAYER_JWT_PUBLIC_KEY"] = self._pub_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = self._make_rs256_token()
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload["tenant_id"], "acme")

    def test_rs256_verify_only_with_private_key(self):
        """When only PRIVATE key is set, validate_jwt_header derives public key."""
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PRIVATE_KEY"] = self._priv_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = self._make_rs256_token()
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(payload["tenant_id"], "acme")

    def test_rs256_wrong_key_rejected(self):
        _, other_pub_pem = _generate_rsa_key_pair()
        other_pub_b64 = base64.b64encode(other_pub_pem).decode()
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PUBLIC_KEY"] = other_pub_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = self._make_rs256_token()
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok)
        self.assertEqual(status, 401)

    def test_rs256_no_key_configured_falls_back(self):
        """No keys → jwt not enabled → (None, None, None)."""
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            result = auth_jwt.validate_jwt_header("Bearer sometoken")
        self.assertIsNone(result[0])

    def test_rs256_missing_tenant_id_rejected(self):
        from backend.src.api.auth_jwt import encode_token_rs256
        token = encode_token_rs256({"sub": "op-1"}, self._private_pem)  # no tenant_id
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PUBLIC_KEY"] = self._pub_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok)
        self.assertEqual(status, 400)
        self.assertEqual(payload["errorCode"], "jwt_missing_tenant")


class TestValidateJwtHeaderHS256Legacy(unittest.TestCase):
    """Ensure HS256 legacy path is fully preserved after GL-261."""

    def test_hs256_valid_token_accepted(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_HS256_SECRET
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = auth_jwt.encode_token({"sub": "op", "tenant_id": "t"}, _TEST_HS256_SECRET)
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload["tenant_id"], "t")

    def test_hs256_no_secret_falls_back(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            result = auth_jwt.validate_jwt_header("Bearer token")
        self.assertIsNone(result[0])

    def test_default_algorithm_is_rs256(self):
        with _EnvGuard():
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            self.assertEqual(auth_jwt._get_algorithm(), "RS256")


class TestSignToken(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()
        cls._priv_b64 = base64.b64encode(cls._private_pem).decode()
        cls._pub_b64 = base64.b64encode(cls._public_pem).decode()

    def test_sign_token_rs256(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PRIVATE_KEY"] = self._priv_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
        # Decode with public key to verify
        from backend.src.api.auth_jwt import decode_token_rs256
        payload = decode_token_rs256(token, self._public_pem)
        self.assertEqual(payload["tenant_id"], "acme")

    def test_sign_token_hs256(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_HS256_SECRET
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
        from backend.src.api.auth_jwt import decode_token
        payload = decode_token(token, _TEST_HS256_SECRET)
        self.assertEqual(payload["tenant_id"], "acme")

    def test_sign_token_rs256_no_private_key_raises(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            with self.assertRaises(ValueError, msg="should raise when no private key"):
                auth_jwt.sign_token({"sub": "x", "tenant_id": "t"})

    def test_sign_token_hs256_no_secret_raises(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            with self.assertRaises(ValueError):
                auth_jwt.sign_token({"sub": "x", "tenant_id": "t"})


class TestIsJwtEnabled(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _, public_pem = _generate_rsa_key_pair()
        cls._pub_b64 = base64.b64encode(public_pem).decode()

    def test_rs256_enabled_when_public_key_set(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            os.environ["GRANTLAYER_JWT_PUBLIC_KEY"] = self._pub_b64
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            self.assertTrue(auth_jwt.is_jwt_enabled())

    def test_rs256_disabled_when_no_keys(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "RS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            self.assertFalse(auth_jwt.is_jwt_enabled())

    def test_hs256_enabled_when_secret_set(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_HS256_SECRET
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            self.assertTrue(auth_jwt.is_jwt_enabled())

    def test_hs256_disabled_when_no_secret(self):
        with _EnvGuard():
            os.environ["GRANTLAYER_JWT_ALGORITHM"] = "HS256"
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            self.assertFalse(auth_jwt.is_jwt_enabled())


class TestAuthTokenEndpointRS256(unittest.TestCase):
    """End-to-end: /auth/token endpoint issues RS256 tokens when configured."""

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()
        cls._priv_b64 = base64.b64encode(cls._private_pem).decode()
        cls._pub_b64 = base64.b64encode(cls._public_pem).decode()

    def _make_app(self, admin_token: str, priv_b64: str, pub_b64: str):
        import tempfile
        tmp = tempfile.mktemp(suffix=".db")
        env_patch = {
            "GRANTLAYER_DB": tmp,
            "GRANTLAYER_ADMIN_TOKEN": admin_token,
            "GRANTLAYER_JWT_ALGORITHM": "RS256",
            "GRANTLAYER_JWT_PRIVATE_KEY": priv_b64,
            "GRANTLAYER_JWT_PUBLIC_KEY": pub_b64,
        }
        saved = {k: os.environ.get(k) for k in env_patch}
        os.environ.update(env_patch)
        # Remove HS256 secret so RS256 path is exercised
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = tmp
        db_mod.DB_PATH = tmp
        db_mod.init_db()

        import backend.src.api.app as app_mod
        importlib.reload(app_mod)

        return app_mod.app, saved

    def _restore_env(self, saved: dict):
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_token_endpoint_returns_rs256_jwt(self):
        from fastapi.testclient import TestClient
        admin_token = "gl261-admin-token-rs256-test"
        app, saved = self._make_app(admin_token, self._priv_b64, self._pub_b64)
        try:
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.post("/v1/auth/token", json={
                "operator_id": "test-op",
                "secret": admin_token,
            })
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertIn("access_token", data)
            token = data["access_token"]
            # Verify it's an RS256 token
            from backend.src.api.auth_jwt import decode_token_rs256
            payload = decode_token_rs256(token, self._public_pem)
            self.assertEqual(payload["sub"], "test-op")
        finally:
            self._restore_env(saved)

    def test_token_endpoint_501_when_no_keys(self):
        from fastapi.testclient import TestClient
        import tempfile
        tmp = tempfile.mktemp(suffix=".db")
        env_patch = {
            "GRANTLAYER_DB": tmp,
            "GRANTLAYER_ADMIN_TOKEN": "admin-gl261-no-keys",
            "GRANTLAYER_JWT_ALGORITHM": "RS256",
        }
        saved = {k: os.environ.get(k) for k in [*env_patch.keys(), "GRANTLAYER_JWT_SECRET",
                                                  "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_PUBLIC_KEY"]}
        os.environ.update(env_patch)
        for k in ("GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_PUBLIC_KEY"):
            os.environ.pop(k, None)
        try:
            import backend.src.core.db as db_mod
            importlib.reload(db_mod)
            db_mod.DB_PATH_OR_URL = tmp
            db_mod.DB_PATH = tmp
            db_mod.init_db()
            import backend.src.api.app as app_mod
            importlib.reload(app_mod)
            client = TestClient(app_mod.app, raise_server_exceptions=False)
            resp = client.post("/v1/auth/token", json={
                "operator_id": "x",
                "secret": "admin-gl261-no-keys",
            })
            self.assertEqual(resp.status_code, 501, resp.text)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
