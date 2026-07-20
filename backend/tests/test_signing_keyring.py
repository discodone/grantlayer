"""Grant signing key rotation via a key_id -> public_key keyring.

Deciding constraint (ADR, accepted): grants signed with an old key must stay
verifiable after rotation. This pins the keyring contract:

  * key_id is derived deterministically from the public key
    (ed25519-<first-16-hex-of-sha256(raw pubkey)>);
  * sign_grant stamps that fingerprint id and REFUSES to sign a key whose id
    is not registered in the keyring (fail-closed — never mint a grant that
    cannot verify);
  * verify_grant_signature resolves key_id -> keyring/<key_id>.pem; a
    missing or unreadable entry is 'unknown_key' (fail-closed deny), distinct
    from 'invalid';
  * the legacy alias demo-ed25519-v1 resolves for already-stamped rows, and a
    production key registered under that alias verifies the prod-signed legacy
    rows (the transition step);
  * the exercise decision surface maps unknown_key -> grant_signature_unknown_key.

Keyring dir is isolated per test via GRANTLAYER_SIGNING_KEYRING_DIR so the
tests never touch the real backend/data/keyring.

Self-provisions SQLite in the exercise-surface class (listed in
_sqlite_only_modules.py).
"""

import hashlib
import os
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

import backend.src.core.config as _cfg
from backend.src.core import crypto_signing as cs
from backend.src.core.models import Grant

_ALIAS = "demo-ed25519-v1"


def _make_grant(**kw) -> Grant:
    d = dict(
        subject_id="anchor-writer", role="agent", action="submit_anchor",
        resource="cardano/mainnet", valid_from="2026-01-01T00:00:00Z",
        valid_until="2099-12-31T23:59:59Z", created_by="op",
        reason="keyring test grant",
    )
    d.update(kw)
    return Grant(**d)


def _pem(priv: Ed25519PrivateKey) -> str:
    return priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()


class _KeyringBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(suffix="-keyring")
        self._orig_dir = _cfg.GRANTLAYER_SIGNING_KEYRING_DIR
        self._orig_envkey = _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        _cfg.GRANTLAYER_SIGNING_KEYRING_DIR = self._tmp
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

    def tearDown(self):
        _cfg.GRANTLAYER_SIGNING_KEYRING_DIR = self._orig_dir
        _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = self._orig_envkey
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestFingerprintDerivation(_KeyringBase):
    def test_deterministic_and_formatted(self):
        pub = Ed25519PrivateKey.generate().public_key()
        kid1 = cs.derive_key_id(pub)
        kid2 = cs.derive_key_id(pub)
        self.assertEqual(kid1, kid2, "derivation must be deterministic")
        self.assertTrue(kid1.startswith("ed25519-"))
        self.assertEqual(len(kid1), len("ed25519-") + 16)

    def test_distinct_keys_distinct_ids(self):
        a = cs.derive_key_id(Ed25519PrivateKey.generate().public_key())
        b = cs.derive_key_id(Ed25519PrivateKey.generate().public_key())
        self.assertNotEqual(a, b)


class TestSignStampsRegisteredFingerprint(_KeyringBase):
    def test_sign_stamps_fingerprint_and_verifies(self):
        g = _make_grant()
        sig, phash, kid = cs.sign_grant(g)
        self.assertTrue(kid.startswith("ed25519-"),
                        "sign must stamp the fingerprint id, not a static label")
        self.assertIsNotNone(cs.load_public_key_by_id(kid),
                             "the stamped key must be registered in the keyring")
        g.signature, g.payload_hash, g.signing_key_id = sig, phash, kid
        self.assertEqual(cs.verify_grant_signature(g), "valid")


class TestSignRefusesUnregisteredKey(_KeyringBase):
    def test_sign_refuses_when_key_not_registered(self):
        fresh = Ed25519PrivateKey.generate()
        _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = _pem(fresh)  # not registered
        with self.assertRaises(cs.SigningKeyNotRegisteredError):
            cs.sign_grant(_make_grant())

    def test_sign_succeeds_once_registered(self):
        fresh = Ed25519PrivateKey.generate()
        _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = _pem(fresh)
        cs.register_public_key(cs.derive_key_id(fresh.public_key()), fresh.public_key())
        g = _make_grant()
        sig, phash, kid = cs.sign_grant(g)
        g.signature, g.payload_hash, g.signing_key_id = sig, phash, kid
        self.assertEqual(cs.verify_grant_signature(g), "valid")


class TestVerifyUnknownKey(_KeyringBase):
    def test_never_registered_id_is_unknown_key(self):
        g = _make_grant()
        sig, phash, _ = cs.sign_grant(g)
        g.signature, g.payload_hash = sig, phash
        g.signing_key_id = "ed25519-0123456789abcdef"  # never registered
        self.assertEqual(cs.verify_grant_signature(g), "unknown_key")

    def test_missing_entry_is_unknown_key(self):
        # A rogue (non-demo) key: sign, then delete its keyring entry — the
        # baseline only re-registers the demo key, so this id stays missing.
        rogue = Ed25519PrivateKey.generate()
        _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = _pem(rogue)
        rogue_id = cs.derive_key_id(rogue.public_key())
        cs.register_public_key(rogue_id, rogue.public_key())
        g = _make_grant()
        sig, phash, kid = cs.sign_grant(g)
        g.signature, g.payload_hash, g.signing_key_id = sig, phash, kid
        os.unlink(os.path.join(self._tmp, f"{rogue_id}.pem"))
        self.assertEqual(cs.verify_grant_signature(g), "unknown_key")

    def test_unreadable_entry_is_unknown_key(self):
        g = _make_grant()
        sig, phash, _ = cs.sign_grant(g)
        bogus_id = "ed25519-fedcba9876543210"
        with open(os.path.join(self._tmp, f"{bogus_id}.pem"), "w") as f:
            f.write("not a valid pem")
        g.signature, g.payload_hash, g.signing_key_id = sig, phash, bogus_id
        self.assertEqual(cs.verify_grant_signature(g), "unknown_key")


class TestLegacyAndProdAliasResolution(_KeyringBase):
    def _sign_with(self, priv, grant, key_id):
        raw = cs.canonical_grant_payload(grant)
        grant.signature = priv.sign(raw).hex()
        grant.payload_hash = hashlib.sha256(raw).hexdigest()
        grant.signing_key_id = key_id

    def test_legacy_demo_alias_resolves(self):
        cs._ensure_keyring_baseline()  # registers demo pubkey under the alias
        demo_priv = cs.load_private_key()
        g = _make_grant()
        self._sign_with(demo_priv, g, _ALIAS)
        self.assertEqual(cs.verify_grant_signature(g), "valid",
                         "a demo-signed row stamped with the legacy alias must verify")

    def test_production_key_registered_under_alias_verifies_legacy_row(self):
        # Transition: existing rows say demo-ed25519-v1 but were signed by the
        # PROD key. Point the alias at the prod pubkey (overwrite) and a
        # prod-signed legacy row verifies.
        cs._ensure_keyring_baseline()
        prod = Ed25519PrivateKey.generate()
        cs.register_public_key(_ALIAS, prod.public_key(), overwrite=True)
        g = _make_grant()
        self._sign_with(prod, g, _ALIAS)
        self.assertEqual(cs.verify_grant_signature(g), "valid",
                         "a prod-signed legacy row must verify via the prod alias entry")

    def test_baseline_does_not_clobber_a_provisioned_alias(self):
        cs._ensure_keyring_baseline()
        prod = Ed25519PrivateKey.generate()
        cs.register_public_key(_ALIAS, prod.public_key(), overwrite=True)
        # a later verify re-runs the baseline — it must NOT overwrite the prod alias
        g = _make_grant()
        self._sign_with(prod, g, _ALIAS)
        cs.verify_grant_signature(g)  # triggers baseline again
        self.assertEqual(cs.verify_grant_signature(g), "valid")


class TestExerciseSurfacesUnknownKey(unittest.TestCase):
    """The decision path maps unknown_key -> grant_signature_unknown_key."""

    def setUp(self):
        import backend.src.core.db as _db
        self._db = _db
        self._tmp = tempfile.mkdtemp(suffix="-keyring")
        self._orig_dir = _cfg.GRANTLAYER_SIGNING_KEYRING_DIR
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_dbpath = _db.DB_PATH_OR_URL
        _cfg.GRANTLAYER_SIGNING_KEYRING_DIR = self._tmp
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

    def tearDown(self):
        _cfg.GRANTLAYER_SIGNING_KEYRING_DIR = self._orig_dir
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        self._db.DB_PATH_OR_URL = self._orig_dbpath
        self._db.DB_PATH = self._orig_dbpath
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_exercise_denies_unknown_key(self):
        from backend.src.core.db import get_session_maker
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from backend.src.demo.demo_action import handle_demo_action

        # Rogue-key-signed grant whose keyring entry is then removed.
        rogue = Ed25519PrivateKey.generate()
        _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = _pem(rogue)
        try:
            rogue_id = cs.derive_key_id(rogue.public_key())
            cs.register_public_key(rogue_id, rogue.public_key())
            g = _make_grant()
            sig, phash, kid = cs.sign_grant(g)
            g.signature, g.payload_hash, g.signing_key_id = sig, phash, kid
            with get_session_maker()() as session:
                SqlAlchemyGrantRepository(session).create(g, "hofer", "ws-keyring")
                session.commit()
            os.unlink(os.path.join(self._tmp, f"{rogue_id}.pem"))
        finally:
            _cfg.GRANTLAYER_SIGNING_PRIVATE_KEY = ""

        result = handle_demo_action(
            subject_id="anchor-writer", role="agent", action="submit_anchor",
            resource="cardano/mainnet", tenant_id="hofer", workspace_id="ws-keyring",
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reasonCode"], "grant_signature_unknown_key")


if __name__ == "__main__":
    unittest.main()
