"""RED regression guard for the config-state leak that blocks lifting the
single-process test constraint.

Proven diagnosis
----------------
``config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE`` is DERIVED from
``RUNTIME_MODE`` at import/reload:

    GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = _env_bool(
        "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE",
        default=RUNTIME_MODE in ("local", "test"),
    )

so when the explicit env override is unset the flag simply follows the mode
(True in test/local, False in production).

Two sibling tests conspire to leak it:
  * ``test_gl200c_tenant_workspace_api_audit_regression`` pops
    ``GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE`` from the environment in
    teardown (so the flag falls back to the mode-derived default), and
  * ``test_gl201_production_auth_secrets_config_hardening`` sets
    ``GRANTLAYER_RUNTIME_MODE=production`` and reloads config; its teardown
    restores the env vars but never reloads config, so the config *module attrs*
    stay at production values (``RUNTIME_MODE="production"`` AND the derived flag
    ``False``).

The existing ``_reset_leaked_runtime_mode`` autouse fixture reconciles ONLY
``config.RUNTIME_MODE`` back to test/local -- it does NOT re-derive the dependent
security flag. So the flag stays a stale ``False`` and the next grant-signing
test (``test_grant_executions.py::TestGrantExecutionModel``) hits
``crypto_signing._check_plaintext_production`` -> ``PermissionError``. Under
``-n auto`` this roams by scheduler nondeterminism (observed run 3, worker gw2).

This test encodes the invariant deterministically, in-process, without xdist and
without depending on test ordering: after a production->test ``RUNTIME_MODE``
transition applied exactly the way the leaky path applies it (env restored +
``RUNTIME_MODE`` attr reconciled, NO config reload), the derived security flag
must track the current mode. It FAILS today because the flag stays stale.

Hermetic: teardown restores the env AND reloads config, so this guard can never
itself become the leaker it describes. Registered in SQLITE_ONLY_MODULES because
it mutates global config via reload and must stay out of the PostgreSQL parity
suite; it belongs to the SQLite unit gate.
"""
import importlib
import os
import unittest

import backend.src.core.config as config
import backend.src.core.crypto_signing as crypto_signing

# A plaintext (unencrypted) PEM: _is_encrypted_pem keys on b"ENCRYPTED PRIVATE
# KEY", which this lacks, so _check_plaintext_production falls through to the flag
# check -- the exact code path the real victim hit.
_PLAINTEXT_PEM = (
    b"-----BEGIN PRIVATE KEY-----\n"
    b"MC4CAQAwBQYDK2VwBCIEIEjyeqDtpex6dmEVG2Cp+sHyQPqQMY4GcCD2H7NcfKoD\n"
    b"-----END PRIVATE KEY-----\n"
)


class TestPlaintextFlagTracksRuntimeMode(unittest.TestCase):
    """The RUNTIME_MODE-derived cached flags (GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
    and REQUIRE_ADMIN_TOKEN) must not leak stale production values once RUNTIME_MODE
    is reconciled back to test -- the reconciliation must re-derive the whole class."""

    _ENV_KEYS = (
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
    )

    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in self._ENV_KEYS}

    def tearDown(self):
        # Restore the environment exactly, then reload config so no stale module
        # attribute survives this test -- it must never leak the state it exercises.
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(config)

    def test_mode_derived_flags_restored_when_runtime_mode_returns_to_test(self):
        # (1) test_gl200c's teardown: drop the explicit overrides so BOTH flags
        #     follow their RUNTIME_MODE-derived defaults on the next reload.
        os.environ.pop("GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        # (2) test_gl201: enter production and reload config. The two mode-derived
        #     flags now hold their production values (they are inverses):
        #       GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE -> False
        #       REQUIRE_ADMIN_TOKEN                         -> True
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        importlib.reload(config)
        self.assertEqual(config.RUNTIME_MODE, "production")
        self.assertFalse(
            config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE,
            "precondition: production mode should derive the plaintext flag False",
        )
        self.assertTrue(
            config.REQUIRE_ADMIN_TOKEN,
            "precondition: production mode should derive REQUIRE_ADMIN_TOKEN True",
        )

        # (3) The leaky teardown restores the env to test, and the
        #     _reset_leaked_runtime_mode fixture reconciles the mode. Reproduce
        #     exactly that (fixed) reconciliation in-process: reset the RUNTIME_MODE
        #     attr AND recompute the mode-derived flags. Before the recompute helper
        #     existed the flags were left stale (both assertions below were RED);
        #     the helper is what re-derives them from the reconciled mode.
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        config.RUNTIME_MODE = "test"
        config.recompute_mode_derived_flags()

        # INVARIANT (RED today): with RUNTIME_MODE reconciled back to "test" and no
        # explicit overrides set, BOTH derived flags must track the current mode:
        #   plaintext flag -> True   (currently stale False)
        #   REQUIRE_ADMIN_TOKEN -> False  (currently stale True)
        # subTest so BOTH invariants are evaluated and reported independently
        # instead of short-circuiting on the first failure.
        with self.subTest(flag="GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"):
            self.assertTrue(
                config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE,
                "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE leaked a stale False "
                "after RUNTIME_MODE was reconciled back to 'test'; the derived flag "
                "is not re-derived, so grant signing is wrongly refused in test mode",
            )
        with self.subTest(flag="REQUIRE_ADMIN_TOKEN"):
            self.assertFalse(
                config.REQUIRE_ADMIN_TOKEN,
                "REQUIRE_ADMIN_TOKEN leaked a stale True after RUNTIME_MODE was "
                "reconciled back to 'test'; the derived flag is not re-derived, so a "
                "later test is wrongly forced to present an admin token",
            )

        # The concrete victim path must therefore stay open: loading a plaintext
        # key must not be refused in test mode.
        try:
            crypto_signing._check_plaintext_production(_PLAINTEXT_PEM)
        except PermissionError as exc:  # pragma: no cover - RED today
            self.fail(
                f"plaintext key refused in test mode due to the stale flag: {exc}"
            )


if __name__ == "__main__":
    unittest.main()
