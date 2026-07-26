"""Signed typed constraints: the grant signature covers the constraints object.

Byte-identity contract (additive/optional/omit-when-None):
  * a grant WITHOUT constraints produces canonical_grant_payload bytes that are
    IDENTICAL to the pre-constraints implementation — pinned verbatim below, so
    every existing signature and payload_hash keeps verifying;
  * a grant WITH constraints signs OVER the canonical constraints JSON — a
    post-signing mutation of the stored limit is detected as hash_mismatch and
    the exercise path denies with grant_payload_hash_mismatch (fail-closed).

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import importlib
import os
import tempfile
import unittest

# The exact bytes canonical_grant_payload produced BEFORE the constraints field
# existed, for the fixed grant below. This pin must NEVER change: a
# constraint-free grant serializes byte-identically forever.
_PINNED_CONSTRAINT_FREE_PAYLOAD = (
    b"action=pg_dump\n"
    b"createdBy=ops\n"
    b"id=00000000-0000-0000-0000-000000000001\n"
    b"reason=nightly backup\n"
    b"resource=db/grantlayer-postgres\n"
    b"role=agent\n"
    b"subjectId=backup-agent\n"
    b"validFrom=2026-01-01T00:00:00Z\n"
    b"validUntil=2027-01-01T00:00:00Z"
)


def _grant_kwargs(**extra):
    kwargs = dict(
        subject_id="backup-agent",
        role="agent",
        action="pg_dump",
        resource="db/grantlayer-postgres",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2027-01-01T00:00:00Z",
        created_by="ops",
        reason="nightly backup",
        id="00000000-0000-0000-0000-000000000001",
    )
    kwargs.update(extra)
    return kwargs


class TestConstraintFreeByteIdentity(unittest.TestCase):
    """The additive guarantee: no constraints -> exactly today's bytes."""

    def test_constraint_free_canonical_bytes_are_pinned(self):
        from backend.src.core.crypto_signing import canonical_grant_payload
        from backend.src.core.models import Grant

        grant = Grant(**_grant_kwargs())
        self.assertEqual(
            canonical_grant_payload(grant),
            _PINNED_CONSTRAINT_FREE_PAYLOAD,
            "a grant without constraints must serialize byte-identically to "
            "the pre-constraints canonical — existing signatures depend on it",
        )


class TestConstraintsAreSigned(unittest.TestCase):
    """A grant WITH constraints signs over them; tampering is detected."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()
        self.crypto_mod = crypto_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

    def _make_constrained_grant(self, constraints_text):
        from backend.src.core.models import Grant

        g = Grant(**_grant_kwargs(constraints=constraints_text))
        self.grants_mod.create_grant(g, tenant_id="demo")
        return g

    def test_constraints_field_enters_the_signed_canonical(self):
        from backend.src.core.crypto_signing import canonical_grant_payload
        from backend.src.core.models import Grant

        plain = Grant(**_grant_kwargs())
        constrained = Grant(
            **_grant_kwargs(constraints='{"max_fee_lovelace":200000}')
        )
        self.assertNotEqual(
            canonical_grant_payload(plain),
            canonical_grant_payload(constrained),
            "constraints must be part of the signed bytes — an unsigned limit "
            "would not be a signed limit",
        )
        self.assertEqual(
            canonical_grant_payload(constrained),
            _PINNED_CONSTRAINT_FREE_PAYLOAD
            + b'\nconstraints={"max_fee_lovelace":200000}',
            "the constraints line is appended omit-when-None style; the "
            "prefix stays byte-identical to the constraint-free canonical",
        )

    def test_signed_constrained_grant_verifies_valid(self):
        g = self._make_constrained_grant('{"max_fee_lovelace":200000}')
        stored = self.grants_mod.get_grant(g.id, tenant_id="demo")
        self.assertEqual(stored.constraints, '{"max_fee_lovelace":200000}')
        self.assertEqual(self.crypto_mod.verify_grant_signature(stored), "valid")

    def test_tampered_limit_is_hash_mismatch(self):
        g = self._make_constrained_grant('{"max_fee_lovelace":200000}')

        from sqlalchemy import text

        from backend.src.core.db import get_engine
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE grants SET constraints = :c WHERE id = :i"),
                {"c": '{"max_fee_lovelace":999999999}', "i": g.id},
            )

        stored = self.grants_mod.get_grant(g.id, tenant_id="demo")
        self.assertEqual(
            self.crypto_mod.verify_grant_signature(stored),
            "hash_mismatch",
            "raising the stored limit after signing must break the signature",
        )

    def test_exercise_denies_tampered_constraints(self):
        g = self._make_constrained_grant('{"max_fee_lovelace":200000}')

        from sqlalchemy import text

        from backend.src.core.db import get_engine
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE grants SET constraints = :c WHERE id = :i"),
                {"c": '{"max_fee_lovelace":999999999}', "i": g.id},
            )

        # No declared attempt needed: the signature gate fires on the matched
        # grant before any constraint evaluation — tampering denies regardless.
        result = self.demo_mod.handle_demo_action(
            "backup-agent", "agent", "pg_dump", "db/grantlayer-postgres",
            tenant_id="demo",
            workspace_id="default",
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reasonCode"], "grant_payload_hash_mismatch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
