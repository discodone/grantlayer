"""GL-307 — Docker Secrets + Vault support tests.

Covers:
- read_file_secret: reads value from file, returns None for missing/empty file
- read_file_secret: raises SecretConfigurationError on permission/OS errors
- read_docker_secret: reads from secrets_dir/<name> file
- read_docker_secret: returns None when file absent
- read_docker_secret: raises ValueError on invalid name/dir
- describe_file_secret_source: returns safe metadata (no values)
- VaultSecretReader.from_env: returns None when env vars not set
- VaultSecretReader.from_env: constructs reader when VAULT_ADDR + TOKEN present
- VaultSecretReader.__repr__: never includes token
- VaultSecretReader.read: parses KV v2 JSON response correctly
- VaultSecretReader.read: returns None on 404
- VaultSecretReader.read: raises SecretConfigurationError on 403
- VaultSecretReader.read: raises SecretConfigurationError on network error
- VaultSecretReader.read: raises SecretConfigurationError on malformed JSON
- VaultSecretReader.describe: safe metadata dict, no token
- SecretResolver.from_env: builds from environment
- SecretResolver.resolve: Vault wins over file wins over env
- SecretResolver.resolve: falls back to file when Vault returns None
- SecretResolver.resolve: falls back to env when file absent
- SecretResolver.resolve: returns None when all sources empty
- SecretResolver.resolve_required: returns value when found
- SecretResolver.resolve_required: raises SecretConfigurationError when missing
- SecretResolver.describe_sources: returns safe config (no tokens/values)
- config: _secret() helper resolves via resolver chain
- config: GRANTLAYER_ADMIN_TOKEN uses _secret() resolver
- config: GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN uses _secret() resolver
- config: GRANTLAYER_SIGNING_PRIVATE_KEY uses _secret() resolver
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.append("backend")

from backend.src.core.secret_sources import (
    DOCKER_SECRETS_DEFAULT_DIR,
    REDACTED_SECRET_VALUE,
    SECRET_SOURCE_ENVIRONMENT,
    SECRET_SOURCE_FILE,
    SECRET_SOURCE_VAULT,
    SecretConfigurationError,
    SecretResolver,
    VaultSecretReader,
    describe_file_secret_source,
    read_docker_secret,
    read_file_secret,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_secret_file(directory: str, name: str, value: str) -> str:
    """Write a secret file and return its path."""
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(value)
    return path


def _make_vault_response(key: str, value: str) -> bytes:
    """Return a minimal Vault KV v2 JSON response body."""
    payload = {"data": {"data": {key: value}}}
    return json.dumps(payload).encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# read_file_secret
# ─────────────────────────────────────────────────────────────────────────────

class TestReadFileSecret(unittest.TestCase):

    def test_reads_value_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = _write_secret_file(d, "mysecret", "hunter2")
            self.assertEqual(read_file_secret(path), "hunter2")

    def test_strips_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = _write_secret_file(d, "mysecret", "hunter2\n")
            self.assertEqual(read_file_secret(path), "hunter2")

    def test_returns_none_for_missing_file(self) -> None:
        self.assertIsNone(read_file_secret("/nonexistent/path/secret"))

    def test_returns_none_for_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = _write_secret_file(d, "empty", "")
            self.assertIsNone(read_file_secret(path))

    def test_returns_none_for_whitespace_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = _write_secret_file(d, "ws", "   \n")
            self.assertIsNone(read_file_secret(path))

    def test_raises_on_empty_path(self) -> None:
        with self.assertRaises(ValueError):
            read_file_secret("")

    def test_raises_on_non_string_path(self) -> None:
        with self.assertRaises((ValueError, TypeError)):
            read_file_secret(None)  # type: ignore[arg-type]

    def test_raises_secret_config_error_on_permission_denied(self) -> None:
        with patch("builtins.open", side_effect=PermissionError("raw_os_reason_XYZ")):
            with self.assertRaises(SecretConfigurationError) as ctx:
                read_file_secret("/some/path")
        self.assertIn("permission denied", str(ctx.exception))
        # Raw OS error reason must not be forwarded into the exception message
        self.assertNotIn("raw_os_reason_XYZ", str(ctx.exception))

    def test_raises_secret_config_error_on_os_error(self) -> None:
        with patch("builtins.open", side_effect=OSError("oops")):
            with self.assertRaises(SecretConfigurationError):
                read_file_secret("/some/path")

    def test_error_message_never_contains_raw_value(self) -> None:
        try:
            with patch("builtins.open", side_effect=PermissionError("supersecret_value")):
                read_file_secret("/path")
        except SecretConfigurationError as exc:
            self.assertNotIn("supersecret_value", str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# read_docker_secret
# ─────────────────────────────────────────────────────────────────────────────

class TestReadDockerSecret(unittest.TestCase):

    def test_reads_secret_from_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "GRANTLAYER_ADMIN_TOKEN", "mytoken123")
            result = read_docker_secret("GRANTLAYER_ADMIN_TOKEN", secrets_dir=d)
        self.assertEqual(result, "mytoken123")

    def test_returns_none_when_file_absent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result = read_docker_secret("GRANTLAYER_ADMIN_TOKEN", secrets_dir=d)
        self.assertIsNone(result)

    def test_default_dir_constant(self) -> None:
        self.assertEqual(DOCKER_SECRETS_DEFAULT_DIR, "/run/secrets")

    def test_raises_on_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            read_docker_secret("", secrets_dir="/run/secrets")

    def test_raises_on_empty_secrets_dir(self) -> None:
        with self.assertRaises(ValueError):
            read_docker_secret("GRANTLAYER_ADMIN_TOKEN", secrets_dir="")

    def test_constructs_correct_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "MY_SECRET", "abc123")
            result = read_docker_secret("MY_SECRET", secrets_dir=d)
        self.assertEqual(result, "abc123")


# ─────────────────────────────────────────────────────────────────────────────
# describe_file_secret_source
# ─────────────────────────────────────────────────────────────────────────────

class TestDescribeFileSecretSource(unittest.TestCase):

    def test_present_secret(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "MY_SECRET", "hunter2_secret_value_xyz")
            desc = describe_file_secret_source("MY_SECRET", secrets_dir=d)
        self.assertEqual(desc["name"], "MY_SECRET")
        self.assertEqual(desc["source"], SECRET_SOURCE_FILE)
        self.assertTrue(desc["present"])
        self.assertEqual(desc["valuePreview"], REDACTED_SECRET_VALUE)
        # Raw secret value must not appear in the safe descriptor
        self.assertNotIn("hunter2_secret_value_xyz", str(desc))

    def test_absent_secret(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            desc = describe_file_secret_source("MISSING", secrets_dir=d)
        self.assertFalse(desc["present"])
        self.assertIsNone(desc["valuePreview"])

    def test_path_in_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            desc = describe_file_secret_source("MY_SECRET", secrets_dir=d)
        self.assertIn("path", desc)
        self.assertIn("MY_SECRET", desc["path"])


# ─────────────────────────────────────────────────────────────────────────────
# VaultSecretReader
# ─────────────────────────────────────────────────────────────────────────────

class TestVaultSecretReaderFromEnv(unittest.TestCase):

    def test_returns_none_when_addr_missing(self) -> None:
        env = {"GRANTLAYER_VAULT_TOKEN": "tok"}
        self.assertIsNone(VaultSecretReader.from_env(env))

    def test_returns_none_when_token_missing(self) -> None:
        env = {"GRANTLAYER_VAULT_ADDR": "http://vault:8200"}
        self.assertIsNone(VaultSecretReader.from_env(env))

    def test_returns_none_when_both_missing(self) -> None:
        self.assertIsNone(VaultSecretReader.from_env({}))

    def test_constructs_reader_with_defaults(self) -> None:
        env = {
            "GRANTLAYER_VAULT_ADDR": "http://vault:8200",
            "GRANTLAYER_VAULT_TOKEN": "s.abc123",
        }
        reader = VaultSecretReader.from_env(env)
        self.assertIsNotNone(reader)
        assert reader is not None
        self.assertEqual(reader._addr, "http://vault:8200")
        self.assertEqual(reader._mount, "secret")
        self.assertEqual(reader._path_prefix, "")

    def test_constructs_reader_with_custom_mount_and_path(self) -> None:
        env = {
            "GRANTLAYER_VAULT_ADDR": "http://vault:8200",
            "GRANTLAYER_VAULT_TOKEN": "s.abc123",
            "GRANTLAYER_VAULT_MOUNT": "kv",
            "GRANTLAYER_VAULT_PATH": "grantlayer/prod",
        }
        reader = VaultSecretReader.from_env(env)
        assert reader is not None
        self.assertEqual(reader._mount, "kv")
        self.assertEqual(reader._path_prefix, "grantlayer/prod")

    def test_repr_never_contains_token(self) -> None:
        env = {
            "GRANTLAYER_VAULT_ADDR": "http://vault:8200",
            "GRANTLAYER_VAULT_TOKEN": "supersecret_vault_token",
        }
        reader = VaultSecretReader.from_env(env)
        assert reader is not None
        self.assertNotIn("supersecret_vault_token", repr(reader))

    def test_source_constant(self) -> None:
        self.assertEqual(SECRET_SOURCE_VAULT, "vault")


class TestVaultSecretReaderRead(unittest.TestCase):

    def _make_reader(self) -> VaultSecretReader:
        return VaultSecretReader(
            addr="http://vault:8200",
            token="s.test",
            mount="secret",
            path_prefix="grantlayer",
        )

    def _mock_urlopen(self, body: bytes):
        """Context manager mock for urllib.request.urlopen."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = body
        return patch("urllib.request.urlopen", return_value=mock_resp)

    def test_reads_value_from_kv_v2_response(self) -> None:
        reader = self._make_reader()
        body = _make_vault_response("GRANTLAYER_ADMIN_TOKEN", "secretval")
        with self._mock_urlopen(body):
            result = reader.read("GRANTLAYER_ADMIN_TOKEN")
        self.assertEqual(result, "secretval")

    def test_returns_none_on_404(self) -> None:
        reader = self._make_reader()
        http_err = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs=MagicMock(), fp=None)
        with patch("urllib.request.urlopen", side_effect=http_err):
            result = reader.read("NONEXISTENT")
        self.assertIsNone(result)

    def test_raises_on_403(self) -> None:
        reader = self._make_reader()
        http_err = urllib.error.HTTPError(url="", code=403, msg="Forbidden", hdrs=MagicMock(), fp=None)
        with patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(SecretConfigurationError) as ctx:
                reader.read("MY_SECRET")
        self.assertIn("403", str(ctx.exception))
        self.assertIn("permission denied", str(ctx.exception).lower())

    def test_raises_on_other_http_error(self) -> None:
        reader = self._make_reader()
        http_err = urllib.error.HTTPError(url="", code=500, msg="Server Error", hdrs=MagicMock(), fp=None)
        with patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(SecretConfigurationError) as ctx:
                reader.read("MY_SECRET")
        self.assertIn("500", str(ctx.exception))

    def test_raises_on_connection_error(self) -> None:
        reader = self._make_reader()
        url_err = urllib.error.URLError(reason=ConnectionRefusedError("refused"))
        with patch("urllib.request.urlopen", side_effect=url_err):
            with self.assertRaises(SecretConfigurationError) as ctx:
                reader.read("MY_SECRET")
        self.assertIn("connection error", str(ctx.exception).lower())

    def test_raises_on_malformed_json(self) -> None:
        reader = self._make_reader()
        with self._mock_urlopen(b"not json at all"):
            with self.assertRaises(SecretConfigurationError):
                reader.read("MY_SECRET")

    def test_raises_on_unexpected_response_structure(self) -> None:
        reader = self._make_reader()
        with self._mock_urlopen(b'{"unexpected": "structure"}'):
            with self.assertRaises(SecretConfigurationError):
                reader.read("MY_SECRET")

    def test_builds_url_with_path_prefix(self) -> None:
        reader = self._make_reader()
        url = reader._build_url("GRANTLAYER_ADMIN_TOKEN")
        self.assertIn("grantlayer/GRANTLAYER_ADMIN_TOKEN", url)
        self.assertIn("/v1/secret/data/", url)

    def test_builds_url_without_path_prefix(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="tok", mount="secret")
        url = reader._build_url("MY_SECRET")
        self.assertIn("/v1/secret/data/MY_SECRET", url)

    def test_error_messages_never_contain_token(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="SUPERSECRET_TOKEN_VALUE", mount="secret")
        http_err = urllib.error.HTTPError(url="", code=403, msg="Forbidden", hdrs=MagicMock(), fp=None)
        with patch("urllib.request.urlopen", side_effect=http_err):
            try:
                reader.read("MY_SECRET")
            except SecretConfigurationError as exc:
                self.assertNotIn("SUPERSECRET_TOKEN_VALUE", str(exc))


class TestVaultSecretReaderDescribe(unittest.TestCase):

    def test_describe_present_secret(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="tok", mount="secret")
        body = _make_vault_response("MY_SECRET", "value")
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = body
        with patch("urllib.request.urlopen", return_value=mock_resp):
            desc = reader.describe("MY_SECRET")
        self.assertEqual(desc["source"], SECRET_SOURCE_VAULT)
        self.assertTrue(desc["present"])
        self.assertEqual(desc["valuePreview"], REDACTED_SECRET_VALUE)
        self.assertNotIn("value", str(desc).replace("valuePreview", ""))

    def test_describe_never_includes_token(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="SUPER_SECRET_TOKEN", mount="secret")
        http_err = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs=MagicMock(), fp=None)
        with patch("urllib.request.urlopen", side_effect=http_err):
            desc = reader.describe("MY_SECRET")
        self.assertNotIn("SUPER_SECRET_TOKEN", str(desc))


# ─────────────────────────────────────────────────────────────────────────────
# SecretResolver
# ─────────────────────────────────────────────────────────────────────────────

class TestSecretResolverFromEnv(unittest.TestCase):

    def test_builds_without_vault(self) -> None:
        resolver = SecretResolver.from_env({})
        self.assertIsNone(resolver._vault)
        self.assertEqual(resolver._secrets_dir, DOCKER_SECRETS_DEFAULT_DIR)

    def test_builds_with_vault(self) -> None:
        env = {
            "GRANTLAYER_VAULT_ADDR": "http://vault:8200",
            "GRANTLAYER_VAULT_TOKEN": "s.tok",
        }
        resolver = SecretResolver.from_env(env)
        self.assertIsNotNone(resolver._vault)

    def test_custom_secrets_dir(self) -> None:
        env = {"GRANTLAYER_SECRETS_DIR": "/custom/secrets"}
        resolver = SecretResolver.from_env(env)
        self.assertEqual(resolver._secrets_dir, "/custom/secrets")

    def test_empty_secrets_dir_falls_back_to_default(self) -> None:
        env = {"GRANTLAYER_SECRETS_DIR": ""}
        resolver = SecretResolver.from_env(env)
        self.assertEqual(resolver._secrets_dir, DOCKER_SECRETS_DEFAULT_DIR)


class TestSecretResolverResolution(unittest.TestCase):

    def _make_env_resolver(self, env: dict) -> SecretResolver:
        return SecretResolver(vault=None, secrets_dir="/nonexistent/dir", env=env)

    def test_resolves_from_environment(self) -> None:
        env = {"MY_SECRET": "envval"}
        resolver = self._make_env_resolver(env)
        self.assertEqual(resolver.resolve("MY_SECRET"), "envval")

    def test_returns_none_when_all_absent(self) -> None:
        resolver = self._make_env_resolver({})
        self.assertIsNone(resolver.resolve("MY_SECRET"))

    def test_file_wins_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "MY_SECRET", "fileval")
            env = {"MY_SECRET": "envval"}
            resolver = SecretResolver(vault=None, secrets_dir=d, env=env)
            result = resolver.resolve("MY_SECRET")
        self.assertEqual(result, "fileval")

    def test_vault_wins_over_file_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "MY_SECRET", "fileval")
            env = {"MY_SECRET": "envval"}

            mock_vault = MagicMock(spec=VaultSecretReader)
            mock_vault.read.return_value = "vaultval"

            resolver = SecretResolver(vault=mock_vault, secrets_dir=d, env=env)
            result = resolver.resolve("MY_SECRET")
        self.assertEqual(result, "vaultval")
        mock_vault.read.assert_called_once_with("MY_SECRET")

    def test_falls_back_to_file_when_vault_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "MY_SECRET", "fileval")
            env = {"MY_SECRET": "envval"}

            mock_vault = MagicMock(spec=VaultSecretReader)
            mock_vault.read.return_value = None

            resolver = SecretResolver(vault=mock_vault, secrets_dir=d, env=env)
            result = resolver.resolve("MY_SECRET")
        self.assertEqual(result, "fileval")

    def test_falls_back_to_env_when_vault_none_and_file_absent(self) -> None:
        env = {"MY_SECRET": "envval"}
        mock_vault = MagicMock(spec=VaultSecretReader)
        mock_vault.read.return_value = None

        resolver = SecretResolver(vault=mock_vault, secrets_dir="/nonexistent", env=env)
        result = resolver.resolve("MY_SECRET")
        self.assertEqual(result, "envval")

    def test_resolve_required_returns_value(self) -> None:
        env = {"MY_SECRET": "envval"}
        resolver = self._make_env_resolver(env)
        self.assertEqual(resolver.resolve_required("MY_SECRET"), "envval")

    def test_resolve_required_raises_when_missing(self) -> None:
        resolver = self._make_env_resolver({})
        with self.assertRaises(SecretConfigurationError) as ctx:
            resolver.resolve_required("MY_MISSING_SECRET")
        self.assertIn("MY_MISSING_SECRET", str(ctx.exception))
        self.assertNotIn("envval", str(ctx.exception))

    def test_error_message_in_resolve_required_never_leaks_value(self) -> None:
        resolver = self._make_env_resolver({})
        try:
            resolver.resolve_required("SUPER_SECRET")
        except SecretConfigurationError as exc:
            self.assertNotIn("hunter2", str(exc))
            self.assertIn("SUPER_SECRET", str(exc))


class TestSecretResolverDescribeSources(unittest.TestCase):

    def test_describe_without_vault(self) -> None:
        resolver = SecretResolver(vault=None, secrets_dir="/run/secrets")
        desc = resolver.describe_sources()
        self.assertFalse(desc["vault"]["configured"])
        self.assertIsNone(desc["vault"]["addr"])
        self.assertTrue(desc["file"]["configured"])
        self.assertEqual(desc["file"]["secretsDir"], "/run/secrets")
        self.assertTrue(desc["environment"]["configured"])

    def test_describe_with_vault(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="tok", mount="secret")
        resolver = SecretResolver(vault=reader, secrets_dir="/run/secrets")
        desc = resolver.describe_sources()
        self.assertTrue(desc["vault"]["configured"])
        self.assertEqual(desc["vault"]["addr"], "http://vault:8200")

    def test_describe_never_includes_token(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="SUPER_SECRET_TOKEN", mount="secret")
        resolver = SecretResolver(vault=reader, secrets_dir="/run/secrets")
        desc = resolver.describe_sources()
        self.assertNotIn("SUPER_SECRET_TOKEN", str(desc))

    def test_sources_list_in_priority_order(self) -> None:
        resolver = SecretResolver(vault=None, secrets_dir="/run/secrets")
        desc = resolver.describe_sources()
        self.assertEqual(desc["sources"], [SECRET_SOURCE_VAULT, SECRET_SOURCE_FILE, SECRET_SOURCE_ENVIRONMENT])

    def test_repr_never_contains_token(self) -> None:
        reader = VaultSecretReader(addr="http://vault:8200", token="SUPER_SECRET_TOKEN", mount="secret")
        resolver = SecretResolver(vault=reader, secrets_dir="/run/secrets")
        self.assertNotIn("SUPER_SECRET_TOKEN", repr(resolver))


# ─────────────────────────────────────────────────────────────────────────────
# Config integration
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigSecretIntegration(unittest.TestCase):

    def test_admin_token_reads_from_env(self) -> None:
        with patch.dict(os.environ, {"GRANTLAYER_ADMIN_TOKEN": "test_tok_12345678"}):
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            self.assertEqual(cfg.GRANTLAYER_ADMIN_TOKEN, "test_tok_12345678")

    def test_admin_token_reads_from_docker_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _write_secret_file(d, "GRANTLAYER_ADMIN_TOKEN", "file_tok_12345678")
            env_patch = {
                "GRANTLAYER_SECRETS_DIR": d,
                "GRANTLAYER_RUNTIME_MODE": "local",
            }
            # Unset GRANTLAYER_ADMIN_TOKEN in env so file wins
            patched_env = {k: v for k, v in os.environ.items() if k != "GRANTLAYER_ADMIN_TOKEN"}
            patched_env.update(env_patch)
            with patch.dict(os.environ, patched_env, clear=True):
                importlib.reload(cfg_module := importlib.import_module("backend.src.core.config"))
                self.assertEqual(cfg_module.GRANTLAYER_ADMIN_TOKEN, "file_tok_12345678")

    def test_bootstrap_operator_token_reads_from_env(self) -> None:
        with patch.dict(os.environ, {"GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN": "boot_tok_12345678"}):
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            self.assertEqual(cfg.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN, "boot_tok_12345678")

    def test_signing_private_key_reads_from_env(self) -> None:
        pem_stub = "-----BEGIN RSA PRIVATE KEY-----\nstub\n-----END RSA PRIVATE KEY-----"
        import backend.src.core.config as cfg
        with patch.dict(os.environ, {"GRANTLAYER_SIGNING_PRIVATE_KEY": pem_stub}):
            importlib.reload(cfg)
            self.assertEqual(cfg.GRANTLAYER_SIGNING_PRIVATE_KEY, pem_stub)
        # Reload without stub so later tests see a clean config module.
        importlib.reload(cfg)

    def test_secret_resolver_exported(self) -> None:
        import backend.src.core.config as cfg
        importlib.reload(cfg)
        self.assertIsNotNone(cfg._SECRET_RESOLVER)
        self.assertIsInstance(cfg._SECRET_RESOLVER, SecretResolver)

    def test_secret_function_returns_empty_string_for_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            # _secret() should return "" default when key absent
            result = cfg._secret("DEFINITELY_NONEXISTENT_KEY_XYZ_789")
            self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
