"""GL-230: Tests for JWT auth, Docker Compose, and Quickstart artifacts.

Covers:
- JWT encode / decode roundtrip
- Token expiry detection
- Invalid signature rejection
- validate_jwt_header() — JWT not configured (fallback path)
- validate_jwt_header() — valid token
- validate_jwt_header() — expired token
- validate_jwt_header() — bad signature
- validate_jwt_header() — missing Bearer header
- create_dev_token() — happy path
- create_dev_token() — no secret raises ValueError
- docker-compose.yml YAML validity
- backend/Dockerfile presence
- nginx/nginx.conf presence
- nginx/generate-certs.sh presence
- QUICKSTART.md presence
"""

from __future__ import annotations

import os
import time
import unittest
import yaml

# Paths are relative to the project root (where tests are run from).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _project(path: str) -> str:
    return os.path.join(_PROJECT_ROOT, path)


# Import the module under test.
from backend.src.api.auth_jwt import (
    encode_token,
    decode_token,
    create_dev_token,
    validate_jwt_header,
    is_jwt_enabled,
    JWTExpiredError,
    JWTInvalidError,
)


class TestEncodeDecodeRoundtrip(unittest.TestCase):
    """Basic encode → decode roundtrip."""

    _SECRET = "test-secret-gl230-xxxxxxxxxxxxxxxx"

    def test_roundtrip_claims_preserved(self):
        token = encode_token({"sub": "agent-001", "tenant_id": "acme"}, self._SECRET)
        payload = decode_token(token, self._SECRET)
        self.assertEqual(payload["sub"], "agent-001")
        self.assertEqual(payload["tenant_id"], "acme")

    def test_iat_and_exp_added(self):
        before = int(time.time())
        token = encode_token({"sub": "t"}, self._SECRET, ttl_hours=1)
        payload = decode_token(token, self._SECRET)
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertGreaterEqual(payload["iat"], before)
        self.assertAlmostEqual(payload["exp"] - payload["iat"], 3600, delta=2)

    def test_custom_ttl(self):
        token = encode_token({"sub": "t"}, self._SECRET, ttl_hours=2)
        payload = decode_token(token, self._SECRET)
        self.assertAlmostEqual(payload["exp"] - payload["iat"], 7200, delta=2)

    def test_arbitrary_claims_preserved(self):
        token = encode_token({"x": 42, "y": ["a", "b"]}, self._SECRET)
        payload = decode_token(token, self._SECRET)
        self.assertEqual(payload["x"], 42)
        self.assertEqual(payload["y"], ["a", "b"])


class TestTokenExpiry(unittest.TestCase):
    """Expiry detection."""

    _SECRET = "expiry-secret-gl230-xxxxxxxxxxxxxxxx"

    def test_expired_token_raises(self):
        # Build a token that expires immediately (ttl_hours=0 → exp = iat)
        # then wait 1 second — but that's slow.  Instead patch time via a
        # token built with a past exp directly.
        import base64, hmac, hashlib, json

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload_data = {"sub": "expired", "iat": 1000, "exp": 1001}
        body = b64url(json.dumps(payload_data, separators=(",", ":")).encode())
        signing_input = f"{header}.{body}"
        sig = b64url(hmac.digest(self._SECRET.encode(), signing_input.encode(), hashlib.sha256))
        expired_token = f"{signing_input}.{sig}"

        with self.assertRaises(JWTExpiredError):
            decode_token(expired_token, self._SECRET)

    def test_future_token_valid(self):
        # ttl_hours=1 → valid for an hour from now
        token = encode_token({"sub": "future"}, self._SECRET, ttl_hours=1)
        payload = decode_token(token, self._SECRET)
        self.assertEqual(payload["sub"], "future")


class TestInvalidToken(unittest.TestCase):
    """Rejection of tampered or malformed tokens."""

    _SECRET = "invalid-secret-gl230-xxxxxxxxxxxxxxxx"

    def test_wrong_secret_raises(self):
        token = encode_token({"sub": "t"}, self._SECRET)
        with self.assertRaises(JWTInvalidError):
            decode_token(token, "different-secret-xxxxxxxxxxxxx")

    def test_tampered_payload_raises(self):
        token = encode_token({"sub": "original"}, self._SECRET)
        # Replace middle part with a different base64 payload
        import base64, json
        parts = token.split(".")
        fake_payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "tampered"}).encode()
        ).rstrip(b"=").decode()
        tampered = f"{parts[0]}.{fake_payload}.{parts[2]}"
        with self.assertRaises(JWTInvalidError):
            decode_token(tampered, self._SECRET)

    def test_malformed_token_raises(self):
        with self.assertRaises(JWTInvalidError):
            decode_token("not.a.jwt.token.at.all", self._SECRET)

    def test_empty_string_raises(self):
        with self.assertRaises(JWTInvalidError):
            decode_token("", self._SECRET)

    def test_empty_secret_raises(self):
        with self.assertRaises((JWTInvalidError, ValueError)):
            encode_token({"sub": "t"}, "")


class TestValidateJwtHeader(unittest.TestCase):
    """validate_jwt_header() integration tests."""

    _SECRET = "validate-secret-gl230-xxxxxxxxxxxxxxxx"

    def _with_secret(self, secret: str | None = None):
        """Context manager: sets/unsets GRANTLAYER_JWT_SECRET."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            prev = os.environ.get("GRANTLAYER_JWT_SECRET")
            if secret is None:
                os.environ.pop("GRANTLAYER_JWT_SECRET", None)
            else:
                os.environ["GRANTLAYER_JWT_SECRET"] = secret
            try:
                yield
            finally:
                if prev is None:
                    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
                else:
                    os.environ["GRANTLAYER_JWT_SECRET"] = prev

        return _ctx()

    def test_no_secret_returns_none_tuple(self):
        with self._with_secret(None):
            ok, status, payload = validate_jwt_header("Bearer sometoken")
        self.assertIsNone(ok)
        self.assertIsNone(status)
        self.assertIsNone(payload)

    def test_valid_token_ok(self):
        with self._with_secret(self._SECRET):
            token = encode_token({"sub": "dev", "tenant_id": "demo"}, self._SECRET)
            ok, status, payload = validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload["sub"], "dev")
        self.assertEqual(payload["tenant_id"], "demo")

    def test_default_tenant_added_when_missing(self):
        with self._with_secret(self._SECRET):
            token = encode_token({"sub": "dev"}, self._SECRET)
            ok, status, payload = validate_jwt_header(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(payload["tenant_id"], "demo")

    def test_missing_header_returns_401(self):
        with self._with_secret(self._SECRET):
            ok, status, payload = validate_jwt_header(None)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_required")

    def test_expired_token_returns_401(self):
        import base64, hmac, hashlib, json

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        body = b64url(json.dumps({"sub": "x", "iat": 1, "exp": 2}, separators=(",", ":")).encode())
        signing_input = f"{header}.{body}"
        sig = b64url(hmac.digest(self._SECRET.encode(), signing_input.encode(), hashlib.sha256))
        expired_token = f"{signing_input}.{sig}"

        with self._with_secret(self._SECRET):
            ok, status, payload = validate_jwt_header(f"Bearer {expired_token}")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_expired")

    def test_bad_signature_returns_401(self):
        with self._with_secret(self._SECRET):
            token = encode_token({"sub": "t"}, "wrong-secret-xxxxxxxxxxxxxxxx")
            ok, status, payload = validate_jwt_header(f"Bearer {token}")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_non_bearer_scheme_returns_401(self):
        with self._with_secret(self._SECRET):
            ok, status, payload = validate_jwt_header("Basic sometoken")
        self.assertFalse(ok)
        self.assertEqual(status, 401)


class TestCreateDevToken(unittest.TestCase):
    """create_dev_token() helper."""

    _SECRET = "devtoken-secret-gl230-xxxxxxxxxxxxxxxx"

    def test_creates_valid_token(self):
        token = create_dev_token(secret=self._SECRET)
        payload = decode_token(token, self._SECRET)
        self.assertEqual(payload["sub"], "dev-operator")
        self.assertEqual(payload["tenant_id"], "demo")
        self.assertEqual(payload["role"], "owner")

    def test_no_secret_raises(self):
        prev = os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        try:
            with self.assertRaises(ValueError):
                create_dev_token(secret=None)
        finally:
            if prev is not None:
                os.environ["GRANTLAYER_JWT_SECRET"] = prev

    def test_env_secret_used_when_no_arg(self):
        prev = os.environ.get("GRANTLAYER_JWT_SECRET")
        os.environ["GRANTLAYER_JWT_SECRET"] = self._SECRET
        try:
            token = create_dev_token()
            payload = decode_token(token, self._SECRET)
            self.assertEqual(payload["sub"], "dev-operator")
        finally:
            if prev is None:
                os.environ.pop("GRANTLAYER_JWT_SECRET", None)
            else:
                os.environ["GRANTLAYER_JWT_SECRET"] = prev


class TestDockerComposeYaml(unittest.TestCase):
    """docker-compose.yml must be valid YAML with expected service definitions."""

    def _load(self) -> dict:
        path = _project("docker-compose.yml")
        with open(path) as f:
            return yaml.safe_load(f)

    def test_yaml_parses(self):
        data = self._load()
        self.assertIsInstance(data, dict)

    def test_services_key_present(self):
        data = self._load()
        self.assertIn("services", data)

    def test_api_service_present(self):
        data = self._load()
        self.assertIn("api", data["services"])

    def test_nginx_service_present(self):
        data = self._load()
        self.assertIn("nginx", data["services"])

    def test_db_service_present(self):
        data = self._load()
        self.assertIn("db", data["services"])

    def test_volumes_defined(self):
        data = self._load()
        self.assertIn("volumes", data)
        self.assertIn("grantlayer-data", data["volumes"])

    def test_networks_defined(self):
        data = self._load()
        self.assertIn("networks", data)

    def test_api_has_healthcheck(self):
        data = self._load()
        api = data["services"]["api"]
        self.assertIn("healthcheck", api)

    def test_jwt_secret_env_in_api(self):
        data = self._load()
        env_list = data["services"]["api"].get("environment", [])
        # environment can be a list or dict
        env_str = str(env_list)
        self.assertIn("GRANTLAYER_JWT_SECRET", env_str)


class TestDockerfilePresence(unittest.TestCase):
    """backend/Dockerfile must exist and contain minimum expected content."""

    _PATH = _project("backend/Dockerfile")

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._PATH), f"Missing: {self._PATH}")

    def test_has_from_instruction(self):
        content = open(self._PATH).read()
        self.assertIn("FROM", content)

    def test_non_root_user(self):
        content = open(self._PATH).read()
        self.assertIn("USER", content)
        self.assertIn("appuser", content)

    def test_exposes_port(self):
        content = open(self._PATH).read()
        self.assertIn("EXPOSE", content)

    def test_has_healthcheck(self):
        content = open(self._PATH).read()
        self.assertIn("HEALTHCHECK", content)

    def test_has_cmd(self):
        content = open(self._PATH).read()
        self.assertIn("CMD", content)

    def test_uvicorn_in_cmd(self):
        content = open(self._PATH).read()
        self.assertIn("uvicorn", content)


class TestNginxArtifacts(unittest.TestCase):
    """nginx/nginx.conf and nginx/generate-certs.sh must exist with expected content."""

    def test_nginx_conf_exists(self):
        self.assertTrue(os.path.isfile(_project("nginx/nginx.conf")))

    def test_nginx_conf_has_ssl(self):
        content = open(_project("nginx/nginx.conf")).read()
        self.assertIn("ssl", content)

    def test_nginx_conf_has_proxy_pass(self):
        content = open(_project("nginx/nginx.conf")).read()
        self.assertIn("proxy_pass", content)

    def test_generate_certs_script_exists(self):
        self.assertTrue(os.path.isfile(_project("nginx/generate-certs.sh")))

    def test_generate_certs_script_executable(self):
        path = _project("nginx/generate-certs.sh")
        self.assertTrue(os.access(path, os.X_OK))


class TestQuickstartMd(unittest.TestCase):
    """QUICKSTART.md must exist and contain key sections."""

    _PATH = _project("QUICKSTART.md")

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._PATH))

    def test_has_docker_compose_command(self):
        content = open(self._PATH).read()
        self.assertIn("docker compose up", content)

    def test_has_curl_examples(self):
        content = open(self._PATH).read()
        self.assertIn("curl", content)

    def test_has_jwt_section(self):
        content = open(self._PATH).read()
        self.assertIn("JWT", content)

    def test_has_troubleshooting(self):
        content = open(self._PATH).read()
        self.assertIn("Troubleshooting", content)

    def test_has_health_endpoint(self):
        content = open(self._PATH).read()
        self.assertIn("/health", content)

    def test_has_grant_creation_example(self):
        content = open(self._PATH).read()
        self.assertIn("/v1/grants", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
