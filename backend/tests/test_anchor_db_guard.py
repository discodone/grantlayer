"""The anchor job must fail loud on a non-production database — BEFORE any chain
read — instead of silently falling back to dev SQLite and later emitting a
misleading downstream tenant error.

Class of bug: a mainnet-configured anchor run invoked WITHOUT
GRANTLAYER_DATABASE_URL (the run_anchor.sh footgun) resolves to the default dev
SQLite (data/grantlayer.db), passes the idempotency check against an empty DB,
and then refuses at the anchor-writer grant exercise with
'refused_grant_exercise_unavailable' / "workspace has no row" — hiding the real
cause. The guard must refuse first, naming the real cause, on:
  (a) GRANTLAYER_DATABASE_URL unset, or
  (b) the resolved engine being SQLite while network == mainnet.

RED-first: today (no guard) both cases REACH the chain logic — proven by the
run returning 'refused_grant_exercise_unavailable' (the exercise ran) rather
than the guard's 'refused_no_production_database'.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

_CFG_KEYS = [
    "GRANTLAYER_DATABASE_URL", "GRANTLAYER_DB", "GRANTLAYER_ENABLE_CARDANO_ANCHORING",
    "GRANTLAYER_CARDANO_NETWORK", "GRANTLAYER_BLOCKFROST_PROJECT_ID",
    "GRANTLAYER_CARDANO_SIGNING_KEY", "GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID",
    "GRANTLAYER_RUNTIME_MODE",
]


class TestAnchorDbGuard(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _CFG_KEYS}
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        # A mainnet-configured run that passes is_fully_configured(). The
        # blockfrost id / signing key are dummies and are NEVER used: the guard
        # (or, pre-fix, the exercise refusal) fires long before any chain call.
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ["GRANTLAYER_ENABLE_CARDANO_ANCHORING"] = "1"
        os.environ["GRANTLAYER_CARDANO_NETWORK"] = "mainnet"
        os.environ["GRANTLAYER_BLOCKFROST_PROJECT_ID"] = "dummy-blockfrost"
        os.environ["GRANTLAYER_CARDANO_SIGNING_KEY"] = "dummy-signing-key"
        os.environ["GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID"] = "ws-guard-test"

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _reload_and_run(self):
        # Re-resolve DB_BACKEND/DB_PATH_OR_URL from the env set above, and give
        # the SQLite DB real tables so the pre-fix run reaches the exercise
        # rather than erroring on a missing table.
        import backend.src.core.config as cfg
        importlib.reload(cfg)
        import backend.src.core.db as db
        importlib.reload(db)
        db.init_db()
        # No need to reload jobs: _anchor_audit_chain_sync resolves get_engine /
        # get_session_maker / CardanoConfig at call time, picking up the reloaded
        # db module and current env.
        import backend.src.workers.jobs as jobs
        return jobs._anchor_audit_chain_sync(None)

    def test_unset_database_url_refuses_before_chain(self):
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_DB"] = self.tmp.name  # sqlite fallback, URL unset
        result = self._reload_and_run()
        self.assertEqual(
            result["status"], "refused_no_production_database",
            f"expected the DB guard to fire before any chain read; got {result!r}",
        )

    def test_sqlite_url_on_mainnet_refuses(self):
        os.environ.pop("GRANTLAYER_DB", None)
        os.environ["GRANTLAYER_DATABASE_URL"] = f"sqlite:///{self.tmp.name}"  # set, but SQLite
        result = self._reload_and_run()
        self.assertEqual(
            result["status"], "refused_no_production_database",
            f"expected the DB guard to fire on SQLite+mainnet; got {result!r}",
        )


if __name__ == "__main__":
    unittest.main()
