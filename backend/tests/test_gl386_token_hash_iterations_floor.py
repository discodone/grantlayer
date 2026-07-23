"""RED-first invariant guard: the PBKDF2 iteration count gets a mode-derived
reduction for the test suite, but the production floor must be unfalsifiable.

Motivation
----------
``TOKEN_HASH_ITERATIONS = 600_000`` (operator token hashing) costs ~0.24 s per
hash and is paid on every operator creation and every authenticated request in
the test suite — an estimated 35–50 % of total suite runtime. The planned
speedup derives a reduced count in local/test mode. Because this touches auth
code, the security invariant comes first and is encoded here BEFORE the
mechanism exists:

  1. In production-like modes the effective iteration count is ALWAYS at least
     the full production value (600_000). An environment variable attempting to
     lower it (``GRANTLAYER_TOKEN_HASH_ITERATIONS=1000``) must be ignored there
     — the floor cannot be falsified from the environment.
  2. The derived value must track RUNTIME_MODE reconciliation exactly like the
     flags fixed for the mode-derived-flag leak (the
     ``recompute_mode_derived_flags`` class): after a production→test
     transition applied WITHOUT a config reload (mode attr reconciled +
     recompute), the reduced test value must be in effect — no stale
     production value may leak forward, and vice versa no reduced value may
     survive into a production-mode derivation.

RED today for the right reason: ``config`` has no ``TOKEN_HASH_ITERATIONS``
attribute at all — the mode-derived mechanism does not exist yet, so every
assertion on ``config.TOKEN_HASH_ITERATIONS`` fails with AttributeError.

Hermetic: teardown restores the env exactly and reloads config, so this guard
can never itself leak the state it exercises. Registered in
SQLITE_ONLY_MODULES because it mutates global config via reload; it belongs to
the SQLite unit gate, not the PostgreSQL parity suite.
"""
import importlib
import os
import unittest

import backend.src.core.config as config

_PRODUCTION_COUNT = 600_000
_REDUCED_TEST_COUNT = 1_000


class TestTokenHashIterationsProductionFloor(unittest.TestCase):
    """Production PBKDF2 iteration floor is unfalsifiable; the reduced count is
    mode-derived and must re-derive on RUNTIME_MODE reconciliation."""

    _ENV_KEYS = (
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_TOKEN_HASH_ITERATIONS",
    )

    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in self._ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(config)

    # ── 1. The floor is unfalsifiable from the environment ──────────────────

    def test_production_ignores_lowering_env_at_import(self):
        """Env tries to lower the count while RUNTIME_MODE=production; a full
        config reload (import-time derivation path) must yield the floor."""
        os.environ["GRANTLAYER_TOKEN_HASH_ITERATIONS"] = str(_REDUCED_TEST_COUNT)
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        importlib.reload(config)
        self.assertEqual(config.RUNTIME_MODE, "production")
        self.assertEqual(
            config.TOKEN_HASH_ITERATIONS,
            _PRODUCTION_COUNT,
            "production-mode PBKDF2 iteration count was lowered via "
            "GRANTLAYER_TOKEN_HASH_ITERATIONS — the production floor must be "
            "unfalsifiable from the environment",
        )

    def test_production_ignores_lowering_env_via_recompute(self):
        """The recompute path (used by the runtime-mode reconciliation fixture)
        must hold the same floor — both derivation paths, one invariant."""
        os.environ["GRANTLAYER_TOKEN_HASH_ITERATIONS"] = str(_REDUCED_TEST_COUNT)
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        importlib.reload(config)
        config.recompute_mode_derived_flags()
        self.assertEqual(
            config.TOKEN_HASH_ITERATIONS,
            _PRODUCTION_COUNT,
            "recompute_mode_derived_flags() let the environment lower the "
            "production PBKDF2 iteration count below the floor",
        )

    def test_production_hash_embeds_full_count(self):
        """The concrete victim path: a hash created in production mode must
        embed the full count (verify_token derives its cost from this field)."""
        os.environ["GRANTLAYER_TOKEN_HASH_ITERATIONS"] = str(_REDUCED_TEST_COUNT)
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        importlib.reload(config)
        import backend.src.auth.operators as operators
        importlib.reload(operators)
        stored = operators.hash_token("probe-token")
        embedded_iterations = int(stored.split("$")[1])
        self.assertEqual(
            embedded_iterations,
            _PRODUCTION_COUNT,
            "a production-mode hash embedded a lowered iteration count",
        )
        self.assertTrue(operators.verify_token("probe-token", stored))

    # ── 2. Mode transitions re-derive (the mode-derived-flag leak class) ────

    def test_reduced_count_tracks_return_to_test_mode(self):
        """production→test applied exactly like the reconciliation fixture
        (mode attr + recompute, NO reload): the reduced count must be in
        effect afterwards — a stale 600_000 must not leak into the suite."""
        os.environ.pop("GRANTLAYER_TOKEN_HASH_ITERATIONS", None)
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        importlib.reload(config)
        self.assertEqual(
            config.TOKEN_HASH_ITERATIONS,
            _PRODUCTION_COUNT,
            "precondition: production mode must derive the full count",
        )

        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        config.RUNTIME_MODE = "test"
        config.recompute_mode_derived_flags()
        self.assertEqual(
            config.TOKEN_HASH_ITERATIONS,
            _REDUCED_TEST_COUNT,
            "TOKEN_HASH_ITERATIONS leaked a stale production value after "
            "RUNTIME_MODE was reconciled back to 'test' — the value is not "
            "part of the re-derived mode-keyed class",
        )

    def test_test_mode_default_is_reduced_and_hash_tracks_it(self):
        """In test mode with no explicit override the reduced default applies,
        and hash_token embeds it (round-trip must still verify)."""
        os.environ.pop("GRANTLAYER_TOKEN_HASH_ITERATIONS", None)
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        importlib.reload(config)
        self.assertEqual(config.TOKEN_HASH_ITERATIONS, _REDUCED_TEST_COUNT)
        import backend.src.auth.operators as operators
        importlib.reload(operators)
        stored = operators.hash_token("probe-token")
        self.assertEqual(int(stored.split("$")[1]), _REDUCED_TEST_COUNT)
        self.assertTrue(operators.verify_token("probe-token", stored))


if __name__ == "__main__":
    unittest.main()
