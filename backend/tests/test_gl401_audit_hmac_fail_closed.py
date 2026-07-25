"""GL-401 — audit-export manifest HMAC key fail-closed (Decision 5, spec §11.5).

The manifest signer falls back to a hardcoded default key when
GRANTLAYER_AUDIT_HMAC_KEY is unset (`audit_compliance.py:25-26`). The default
is a PUBLIC constant (it ships in the repo), so in production-like modes the
"signature" it produces authenticates nothing. Decision 5 (2026-07-25):
require the env var fail-closed in production-like modes; local/test keep the
fallback.

Two gates, RED before implementation:

  1. STARTUP — `config.startup_errors()` must name GRANTLAYER_AUDIT_HMAC_KEY
     in production-like modes when it is unset (same startup-gate family as
     the Redis / unsubscribe-secret / admin-token refusals; the app lifespan
     refuses to boot on any error). RED reason: no such error exists.
  2. SIGNER — `_get_hmac_key()` itself must refuse (RuntimeError) in
     production-like modes when the env var is unset, so the default key can
     never sign a production manifest even if a caller bypasses the startup
     gate. Mode is read at CALL time (the gl-386 mode-derivation lesson: a
     cached mode-keyed value goes stale on RUNTIME_MODE reconciliation; a
     call-time read cannot). RED reason: the fallback is returned instead.

Hermetic: teardown restores the env exactly and reloads config (gl-386
pattern). Registered in SQLITE_ONLY_MODULES: it mutates global config via
reload, so it belongs to the SQLite unit gate, not the PostgreSQL parity
suite.
"""

from __future__ import annotations

import importlib
import os
import unittest

import backend.src.core.config as config

_ENV_KEYS = ("GRANTLAYER_RUNTIME_MODE", "GRANTLAYER_AUDIT_HMAC_KEY")
_KEY_ENV = "GRANTLAYER_AUDIT_HMAC_KEY"


class _HmacEnvBase(unittest.TestCase):
    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in _ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(config)

    def _set_mode(self, mode: str):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = mode
        importlib.reload(config)
        self.assertEqual(config.RUNTIME_MODE, mode)

    @staticmethod
    def _hmac_errors() -> list[str]:
        return [e for e in config.startup_errors() if _KEY_ENV in e]


class TestStartupGate(_HmacEnvBase):
    """Gate 1: startup_errors() refuses production-like modes without the key."""

    def test_production_unset_is_a_startup_error(self):
        os.environ.pop(_KEY_ENV, None)
        self._set_mode("production")
        self.assertTrue(
            self._hmac_errors(),
            "startup_errors() does not flag a missing GRANTLAYER_AUDIT_HMAC_KEY "
            "in production mode — the manifest would be signed with the "
            "public default key",
        )

    def test_staging_unset_is_a_startup_error(self):
        os.environ.pop(_KEY_ENV, None)
        self._set_mode("staging")
        self.assertTrue(self._hmac_errors())

    def test_production_with_key_has_no_hmac_error(self):
        os.environ[_KEY_ENV] = "gl401-explicit-production-hmac-key"
        self._set_mode("production")
        self.assertEqual(self._hmac_errors(), [])

    def test_test_mode_unset_is_not_an_error(self):
        """local/test keep the fallback: no startup error there."""
        os.environ.pop(_KEY_ENV, None)
        self._set_mode("test")
        self.assertEqual(self._hmac_errors(), [])


class TestSignerFailClosed(_HmacEnvBase):
    """Gate 2: _get_hmac_key() refuses at the signer in production-like modes."""

    def test_production_unset_raises(self):
        from backend.src.api.routers.audit_compliance import _get_hmac_key

        os.environ.pop(_KEY_ENV, None)
        self._set_mode("production")
        with self.assertRaises(
            RuntimeError,
            msg="_get_hmac_key() fell back to the public default key in "
            "production mode — the signer must fail closed",
        ):
            _get_hmac_key()

    def test_staging_unset_raises(self):
        from backend.src.api.routers.audit_compliance import _get_hmac_key

        os.environ.pop(_KEY_ENV, None)
        self._set_mode("staging")
        with self.assertRaises(RuntimeError):
            _get_hmac_key()

    def test_production_with_key_returns_it(self):
        from backend.src.api.routers.audit_compliance import _get_hmac_key

        os.environ[_KEY_ENV] = "gl401-explicit-production-hmac-key"
        self._set_mode("production")
        self.assertEqual(_get_hmac_key(), b"gl401-explicit-production-hmac-key")

    def test_test_mode_unset_returns_default(self):
        from backend.src.api.routers.audit_compliance import (
            _DEFAULT_HMAC_KEY,
            _get_hmac_key,
        )

        os.environ.pop(_KEY_ENV, None)
        self._set_mode("test")
        self.assertEqual(_get_hmac_key(), _DEFAULT_HMAC_KEY.encode())

    def test_mode_reconciliation_without_reload(self):
        """gl-386 lesson: after a production→test reconciliation applied
        WITHOUT a config reload, the signer must follow the CURRENT mode —
        a call-time mode read cannot go stale."""
        from backend.src.api.routers.audit_compliance import (
            _DEFAULT_HMAC_KEY,
            _get_hmac_key,
        )

        os.environ.pop(_KEY_ENV, None)
        self._set_mode("production")
        # Reconcile the mode attribute directly (no reload), as the leaked-mode
        # test fixture does, then recompute the mode-derived flag class.
        config.RUNTIME_MODE = "test"
        config.recompute_mode_derived_flags()
        self.assertEqual(_get_hmac_key(), _DEFAULT_HMAC_KEY.encode())


if __name__ == "__main__":
    unittest.main()
