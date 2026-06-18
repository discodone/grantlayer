"""GL-295: JWT iss/aud claims — injection and validation.

Covers:
- sign_token() injects iss/aud from config (HS256 and RS256)
- sign_token() skips iss/aud when config values are empty
- sign_token() respects caller-supplied iss/aud (setdefault semantics)
- validate_jwt_header() accepts tokens with correct iss/aud
- validate_jwt_header() rejects tokens with wrong iss (jwt_invalid)
- validate_jwt_header() rejects tokens with wrong aud (jwt_invalid)
- validate_jwt_header() accepts old tokens without iss/aud (backward compat)
- validate_jwt_header() skips iss validation when JWT_ISSUER is empty
- validate_jwt_header() skips aud validation when JWT_AUDIENCE is empty
- create_dev_token() includes iss/aud from config
- create_dev_token() omits iss/aud when config values are empty
"""

from __future__ import annotations

import base64
import contextlib
import importlib
import os
import unittest


_HS256_SECRET = "gl295-hs256-test-secret-32charsX"
_ISSUER = "grantlayer"
_AUDIENCE = "grantlayer-api"


@contextlib.contextmanager
def _env(**overrides: str):
    """Context manager: override env vars and restore on exit."""
    saved = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def _clear_jwt_env(**overrides: str):
    """Clear all JWT-related env vars, then apply overrides."""
    _jwt_keys = (
        "GRANTLAYER_JWT_ALGORITHM",
        "GRANTLAYER_JWT_SECRET",
        "GRANTLAYER_JWT_PRIVATE_KEY",
        "GRANTLAYER_JWT_PUBLIC_KEY",
        "GRANTLAYER_JWT_ISSUER",
        "GRANTLAYER_JWT_AUDIENCE",
        "GRANTLAYER_JWT_STRICT_CLAIMS",
    )
    saved = {k: os.environ.get(k) for k in _jwt_keys}
    for k in _jwt_keys:
        os.environ.pop(k, None)
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k in _jwt_keys:
            v = saved[k]
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _generate_rsa_key_pair() -> tuple[bytes, bytes]:
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


class TestSignTokenIssAudHS256(unittest.TestCase):
    """sign_token() injects iss/aud from config (HS256)."""

    def test_iss_and_aud_injected_by_default(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="HS256",
            GRANTLAYER_JWT_SECRET=_HS256_SECRET,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertEqual(payload.get("iss"), _ISSUER)
        self.assertEqual(payload.get("aud"), _AUDIENCE)

    def test_iss_aud_omitted_when_config_empty(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="HS256",
            GRANTLAYER_JWT_SECRET=_HS256_SECRET,
            GRANTLAYER_JWT_ISSUER="",
            GRANTLAYER_JWT_AUDIENCE="",
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertNotIn("iss", payload)
        self.assertNotIn("aud", payload)

    def test_caller_supplied_iss_not_overwritten(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="HS256",
            GRANTLAYER_JWT_SECRET=_HS256_SECRET,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token(
                {"sub": "op", "tenant_id": "acme", "iss": "custom-issuer"}
            )
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertEqual(payload.get("iss"), "custom-issuer")

    def test_caller_supplied_aud_not_overwritten(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="HS256",
            GRANTLAYER_JWT_SECRET=_HS256_SECRET,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token(
                {"sub": "op", "tenant_id": "acme", "aud": "custom-audience"}
            )
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertEqual(payload.get("aud"), "custom-audience")


class TestSignTokenIssAudRS256(unittest.TestCase):
    """sign_token() injects iss/aud from config (RS256)."""

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()
        cls._priv_b64 = base64.b64encode(cls._private_pem).decode()
        cls._pub_b64 = base64.b64encode(cls._public_pem).decode()

    def test_iss_and_aud_injected_rs256(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="RS256",
            GRANTLAYER_JWT_PRIVATE_KEY=self._priv_b64,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
            payload = auth_jwt.decode_token_rs256(token, self._public_pem)
        self.assertEqual(payload.get("iss"), _ISSUER)
        self.assertEqual(payload.get("aud"), _AUDIENCE)

    def test_iss_aud_omitted_when_config_empty_rs256(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="RS256",
            GRANTLAYER_JWT_PRIVATE_KEY=self._priv_b64,
            GRANTLAYER_JWT_ISSUER="",
            GRANTLAYER_JWT_AUDIENCE="",
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.sign_token({"sub": "op", "tenant_id": "acme"})
            payload = auth_jwt.decode_token_rs256(token, self._public_pem)
        self.assertNotIn("iss", payload)
        self.assertNotIn("aud", payload)


class TestValidateJwtHeaderIssAud(unittest.TestCase):
    """validate_jwt_header() validates iss and aud claims."""

    def _make_hs256_token(self, extra: dict | None = None) -> str:
        from backend.src.api.auth_jwt import encode_token
        payload = {"sub": "op", "tenant_id": "acme"}
        if extra:
            payload.update(extra)
        return encode_token(payload, _HS256_SECRET)

    def _call_validate(self, token: str, issuer: str = _ISSUER, audience: str = _AUDIENCE, strict: bool = True) -> tuple:
        overrides: dict = dict(
            GRANTLAYER_JWT_ALGORITHM="HS256",
            GRANTLAYER_JWT_SECRET=_HS256_SECRET,
            GRANTLAYER_JWT_ISSUER=issuer,
            GRANTLAYER_JWT_AUDIENCE=audience,
            GRANTLAYER_JWT_STRICT_CLAIMS="true" if strict else "false",
        )
        with _clear_jwt_env(**overrides):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            return auth_jwt.validate_jwt_header(f"Bearer {token}")

    def test_token_with_correct_iss_and_aud_accepted(self):
        token = self._make_hs256_token({"iss": _ISSUER, "aud": _AUDIENCE})
        ok, status, payload = self._call_validate(token)
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_token_with_wrong_iss_rejected(self):
        token = self._make_hs256_token({"iss": "evil-issuer", "aud": _AUDIENCE})
        ok, status, payload = self._call_validate(token)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_token_with_wrong_aud_rejected(self):
        token = self._make_hs256_token({"iss": _ISSUER, "aud": "wrong-audience"})
        ok, status, payload = self._call_validate(token)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_old_token_without_iss_aud_accepted(self):
        """Backward compat: tokens without iss/aud accepted when strict=false."""
        token = self._make_hs256_token()  # no iss, no aud
        ok, status, payload = self._call_validate(token, strict=False)
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_iss_validation_skipped_when_not_configured(self):
        """With JWT_ISSUER='', token with any iss is accepted."""
        token = self._make_hs256_token({"iss": "any-issuer", "aud": _AUDIENCE})
        ok, status, payload = self._call_validate(token, issuer="", audience=_AUDIENCE)
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_aud_validation_skipped_when_not_configured(self):
        """With JWT_AUDIENCE='', token with any aud is accepted."""
        token = self._make_hs256_token({"iss": _ISSUER, "aud": "any-audience"})
        ok, status, payload = self._call_validate(token, issuer=_ISSUER, audience="")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_aud_as_list_accepted_when_audience_present(self):
        """aud claim as a list is accepted when expected_aud is a member."""
        token = self._make_hs256_token({"iss": _ISSUER, "aud": [_AUDIENCE, "other-service"]})
        ok, status, payload = self._call_validate(token)
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_aud_as_list_rejected_when_audience_not_member(self):
        """aud claim as a list is rejected when expected_aud is not a member."""
        token = self._make_hs256_token({"iss": _ISSUER, "aud": ["other-service", "another-one"]})
        ok, status, payload = self._call_validate(token)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")


class TestValidateJwtHeaderIssAudRS256(unittest.TestCase):
    """validate_jwt_header() validates iss/aud for RS256 tokens."""

    @classmethod
    def setUpClass(cls):
        cls._private_pem, cls._public_pem = _generate_rsa_key_pair()
        cls._priv_b64 = base64.b64encode(cls._private_pem).decode()
        cls._pub_b64 = base64.b64encode(cls._public_pem).decode()

    def _make_rs256_token(self, extra: dict | None = None) -> str:
        from backend.src.api.auth_jwt import encode_token_rs256
        payload = {"sub": "op", "tenant_id": "acme"}
        if extra:
            payload.update(extra)
        return encode_token_rs256(payload, self._private_pem)

    def test_rs256_token_with_correct_iss_aud_accepted(self):
        token = self._make_rs256_token({"iss": _ISSUER, "aud": _AUDIENCE})
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="RS256",
            GRANTLAYER_JWT_PUBLIC_KEY=self._pub_b64,
            GRANTLAYER_JWT_ISSUER=_ISSUER,
            GRANTLAYER_JWT_AUDIENCE=_AUDIENCE,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_rs256_token_with_wrong_iss_rejected(self):
        token = self._make_rs256_token({"iss": "attacker", "aud": _AUDIENCE})
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="RS256",
            GRANTLAYER_JWT_PUBLIC_KEY=self._pub_b64,
            GRANTLAYER_JWT_ISSUER=_ISSUER,
            GRANTLAYER_JWT_AUDIENCE=_AUDIENCE,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_rs256_old_token_without_iss_aud_accepted(self):
        """Backward compat: RS256 tokens without iss/aud accepted when strict=false."""
        token = self._make_rs256_token()
        with _clear_jwt_env(
            GRANTLAYER_JWT_ALGORITHM="RS256",
            GRANTLAYER_JWT_PUBLIC_KEY=self._pub_b64,
            GRANTLAYER_JWT_ISSUER=_ISSUER,
            GRANTLAYER_JWT_AUDIENCE=_AUDIENCE,
            GRANTLAYER_JWT_STRICT_CLAIMS="false",
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            ok, status, payload = auth_jwt.validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(status, 200)


class TestCreateDevTokenIssAud(unittest.TestCase):
    """create_dev_token() includes iss/aud from config."""

    def test_dev_token_includes_iss_and_aud(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ISSUER=_ISSUER,
            GRANTLAYER_JWT_AUDIENCE=_AUDIENCE,
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.create_dev_token(secret=_HS256_SECRET)
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertEqual(payload.get("iss"), _ISSUER)
        self.assertEqual(payload.get("aud"), _AUDIENCE)

    def test_dev_token_omits_iss_aud_when_not_configured(self):
        with _clear_jwt_env(
            GRANTLAYER_JWT_ISSUER="",
            GRANTLAYER_JWT_AUDIENCE="",
        ):
            from backend.src.api import auth_jwt
            importlib.reload(auth_jwt)
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            token = auth_jwt.create_dev_token(secret=_HS256_SECRET)
            payload = auth_jwt.decode_token(token, _HS256_SECRET)
        self.assertNotIn("iss", payload)
        self.assertNotIn("aud", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
