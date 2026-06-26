"""GL-350b — RED tests for CardanoConfig (backend/src/anchoring/config.py), not yet built.

Mirrors the existing OIDC opt-in / fail-closed config test:
    backend/tests/test_gl306_oidc_saml.py :: TestOIDCConfig  (lines 135-250)
so CardanoConfig is a faithful sibling of OIDCConfig (same frozen-dataclass +
from_env() + is_fully_configured() + startup_errors() shape), not a reinvention.

Secrets are read by the production design via _secret('NAME'), which resolves
through SecretResolver (Vault > /run/secrets file > os.environ, live at
resolution time — secret_sources.py:460). With no Vault and no secret files on
this VM, setting the env var is what the resolver falls back to, so these tests
configure secrets purely via os.environ — exactly as the OIDC test sets its
GRANTLAYER_OIDC_* vars.

Expected RED: backend.src.anchoring.config does not exist yet → ImportError in
each test (imports are inside the test methods, mirroring the OIDC test, so the
failures are per-test rather than a single collection error).
"""

from __future__ import annotations

import os
import unittest


class TestCardanoConfig(unittest.TestCase):

    _CARDANO_KEYS = [
        "GRANTLAYER_ENABLE_CARDANO_ANCHORING",
        "GRANTLAYER_BLOCKFROST_PROJECT_ID",
        "GRANTLAYER_CARDANO_SIGNING_KEY",
        "GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID",
        "GRANTLAYER_CARDANO_NETWORK",
        "GRANTLAYER_CARDANO_ANCHOR_LABEL",
        "GRANTLAYER_CARDANO_ANCHOR_INTERVAL_SECONDS",
    ]

    def setUp(self):
        # Snapshot + clear so a configured host env can't leak into the defaults.
        self._saved = {k: os.environ.get(k) for k in self._CARDANO_KEYS}
        for k in self._CARDANO_KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # 1 ──────────────────────────────────────────────────────────────────
    def test_disabled_by_default(self):
        from backend.src.anchoring.config import CardanoConfig
        cfg = CardanoConfig.from_env()
        assert cfg.enabled is False
        assert cfg.is_fully_configured() is False

    # 2 ──────────────────────────────────────────────────────────────────
    def test_enabled_but_missing_secrets_yields_startup_errors(self):
        # Mirror OIDC test_startup_errors_when_enabled_but_missing_fields:
        # enabled but required fields absent → hard, fail-closed startup errors.
        from backend.src.anchoring.config import CardanoConfig
        os.environ["GRANTLAYER_ENABLE_CARDANO_ANCHORING"] = "true"
        cfg = CardanoConfig.from_env()
        errs = cfg.startup_errors()
        assert errs, "fail-closed: enabled-but-misconfigured must produce startup errors"
        assert any("GRANTLAYER_BLOCKFROST_PROJECT_ID" in e for e in errs)
        assert any("GRANTLAYER_CARDANO_SIGNING_KEY" in e for e in errs)
        assert not cfg.is_fully_configured()

    # 3 ──────────────────────────────────────────────────────────────────
    def test_fully_configured_true_when_all_present(self):
        from backend.src.anchoring.config import CardanoConfig
        os.environ.update({
            "GRANTLAYER_ENABLE_CARDANO_ANCHORING": "true",
            "GRANTLAYER_BLOCKFROST_PROJECT_ID": "preprodABC123",
            "GRANTLAYER_CARDANO_SIGNING_KEY": "ed25519_sk_test_key_material",
            "GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID": "ws-anchor",
        })
        cfg = CardanoConfig.from_env()
        assert cfg.is_fully_configured() is True
        assert cfg.startup_errors() == []

    # 4 ──────────────────────────────────────────────────────────────────
    def test_anchor_label_default_is_923350(self):
        from backend.src.anchoring.config import CardanoConfig
        cfg = CardanoConfig.from_env()
        assert cfg.anchor_label == 923350


if __name__ == "__main__":
    unittest.main()
