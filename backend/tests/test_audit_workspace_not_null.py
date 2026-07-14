"""GL-353 — Enforce workspace_id NOT NULL on audit_events at the SCHEMA level.

Context
-------
GL-352 made ``AuditEvent.workspace_id`` a required field in Python (mypy enforces
it at every construction site). But the DATABASE still permits NULL:
``audit_events.workspace_id`` is nullable on both SQLite and PostgreSQL, and no
migration ever constrained it. The defect can silently return via any path that
bypasses the dataclass — a raw INSERT, a new client, or future code. GL-353
closes it at the schema level with a backfill + NOT NULL migration.

CRITICAL TRAP (why this is non-trivial)
---------------------------------------
SQLite cannot ``ALTER COLUMN ... SET NOT NULL`` at all. Migration 0012's pattern
(``SET NOT NULL`` only when backend == postgres) is a silent no-op on SQLite —
a migration that "passes" while enforcing nothing is worse than none. Real
enforcement on SQLite requires a table rebuild (create ``audit_events_new`` with
``workspace_id TEXT NOT NULL``, copy rows, drop, rename) inside a transaction —
and ``audit_events`` carries the hash-chain columns (row_hash/prev_hash), the
``seq`` tiebreak, and append-only immutability triggers, so the rebuild must
preserve every row byte-for-byte or the chain breaks.

These tests run against SQLite (the hard case). They are RED now:
  1. a raw NULL insert currently SUCCEEDS (no constraint) — must be rejected.
  2. the live schema does NOT declare workspace_id NOT NULL — must.
  3. legacy NULL rows are NOT backfilled by the migration chain — must be.
  4. (guards the rebuild) after backfill, zero NULLs remain AND the hash chain
     still verifies — the rebuild must not recompute/reorder/drop chain rows.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

import sqlalchemy.exc

# The migration that closes GL-353 will be numbered 0019 (current head is 0018).
# Staged backfill tests apply the chain up to — but not including — this version,
# seed legacy NULL rows while the column is still nullable, then run the rest.
_ENFORCING_VERSION_PREFIX = "0019"


class _TempDbBase(unittest.TestCase):
    """Isolated temp SQLite DB wired into the app's db + audit_log + migration runner."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

        self._env = {k: os.environ.get(k) for k in ("GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL")}
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        # Force the SQLite path deterministically — this is the backend the trap lives on.
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db
        importlib.reload(db)
        db.DB_PATH_OR_URL = self.tmp.name
        db.DB_PATH = self.tmp.name
        self.db = db

        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al

        from backend.src.migrations import runner
        self.runner = runner

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ── helpers ──────────────────────────────────────────────────────────

    def _apply_through(self, conn, stop_prefix=_ENFORCING_VERSION_PREFIX):
        """Apply every migration whose 4-digit prefix is < stop_prefix, in order.

        Leaves the enforcing migration (and anything after it) PENDING so legacy
        NULL rows can be seeded before it runs.
        """
        self.runner._ensure_migrations_table(conn)
        for version, filepath in self.runner._discovery():
            if version[:4] >= stop_prefix:
                break
            self.runner._load_module(filepath).apply(conn)
            self.runner._mark_applied(conn, version)

    def _null_count(self) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS c FROM audit_events WHERE workspace_id IS NULL"
        )
        return int(row["c"]) if row else -1

    def _insert_null_row(self, conn, row_id: str, ts: str):
        conn.execute(
            "INSERT INTO audit_events "
            "(id, timestamp, subject_id, role, action, resource, approved, reason, workspace_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row_id, ts, "sub", "operator", "act", "res", 1, "reason", None),
        )

    def _insert_chain_row(self, conn, ev, row_hash, prev_hash, seq):
        """Raw insert of a hash-chained row with a NULL workspace_id (legacy shape)."""
        conn.execute(
            "INSERT INTO audit_events "
            "(id, timestamp, subject_id, role, action, resource, approved, reason, "
            " matched_grant_id, challenge_id, challenge_present, challenge_result, "
            " grant_signature_result, row_hash, prev_hash, tenant_id, workspace_id, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ev.id, ev.timestamp, ev.subject_id, ev.role, ev.action, ev.resource,
                1 if ev.approved else 0, ev.reason,
                ev.matched_grant_id, ev.challenge_id, int(ev.challenge_present),
                ev.challenge_result, ev.grant_signature_result,
                row_hash, prev_hash, None, None, seq,
            ),
        )


# ══════════════════════════════════════════════════════════════════════════
# 1 + 2. Enforcement on the fully-migrated (live) schema
# ══════════════════════════════════════════════════════════════════════════


class TestSchemaEnforcement(_TempDbBase):
    def setUp(self):
        super().setUp()
        # Build the full forward chain (in GREEN this includes the GL-353 migration).
        self.db.init_db()

    def test_null_workspace_insert_rejected_on_current_backend(self):
        """A RAW insert with workspace_id = NULL — bypassing the ORM/dataclass —
        must be rejected by the database itself."""
        with self.assertRaises(sqlalchemy.exc.IntegrityError):
            self.db.execute(
                "INSERT INTO audit_events "
                "(id, timestamp, subject_id, role, action, resource, approved, reason, workspace_id) "
                "VALUES (:id, :ts, :s, :r, :a, :res, :ap, :rea, :ws)",
                {
                    "id": "evt-null-1", "ts": "2026-01-01T00:00:00Z", "s": "sub",
                    "r": "operator", "a": "act", "res": "res", "ap": 1,
                    "rea": "reason", "ws": None,
                },
            )

    def test_schema_declares_not_null(self):
        """The live schema must declare audit_events.workspace_id NOT NULL."""
        if self.db.DB_BACKEND == "postgres":
            row = self.db.query_one(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'audit_events' AND column_name = 'workspace_id'"
            )
            self.assertIsNotNone(row, "workspace_id column not found in information_schema")
            self.assertEqual(row["is_nullable"], "NO")
        else:
            conn = self.db.get_conn()
            try:
                rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            finally:
                conn.close()
            ws = [r for r in rows if r[1] == "workspace_id"]
            self.assertTrue(ws, "workspace_id column not found in audit_events")
            # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
            self.assertEqual(int(ws[0][3]), 1, "audit_events.workspace_id is not declared NOT NULL")


# ══════════════════════════════════════════════════════════════════════════
# 3 + 4. Backfill of legacy NULL rows via the migration chain (SQLite rebuild)
# ══════════════════════════════════════════════════════════════════════════


class TestLegacyBackfill(_TempDbBase):
    def test_legacy_null_rows_backfilled(self):
        """Legacy rows written with a NULL workspace_id must be backfilled to zero
        by the migration chain."""
        conn = self.db.get_conn()
        self._apply_through(conn)
        for i in range(5):
            self._insert_null_row(conn, f"legacy-{i}", f"2026-01-01T00:00:0{i}Z")
        conn.commit()

        pre = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE workspace_id IS NULL"
        ).fetchone()[0]
        self.assertEqual(pre, 5, "sanity: 5 legacy NULL rows must exist pre-migration")

        # Apply the remaining (enforcing + backfilling) migrations.
        self.runner.run_migrations(conn)
        conn.commit()
        conn.close()

        self.assertEqual(self._null_count(), 0, "legacy NULL workspace_id rows were not backfilled")

    def test_hash_chain_survives_backfill(self):
        """After the backfill/rebuild: no NULLs remain AND the audit hash chain
        still verifies. Guards a rebuild that recomputes, reorders, or drops rows."""
        from backend.src.core.models import AuditEvent

        conn = self.db.get_conn()
        self._apply_through(conn)

        # Seed a valid hash chain of legacy rows (workspace_id NULL). The hash
        # payload excludes workspace_id, so a correct backfill leaves hashes intact.
        prev = None
        n = 4
        for i in range(n):
            ev = AuditEvent(
                id=f"chain-{i}",
                timestamp=f"2026-02-01T00:00:0{i}Z",
                subject_id="sub",
                role="operator",
                action="act",
                resource="res",
                approved=True,
                reason="r",
                workspace_id="ignored-by-hash",  # not part of the hash payload
            )
            row_hash = self.al._compute_row_hash(ev, prev)
            self._insert_chain_row(conn, ev, row_hash, prev, i + 1)
            prev = row_hash
        conn.commit()

        # Chain must verify BEFORE the migration (rows were seeded correctly).
        pre_report = self.al.verify_audit_hash_chain()
        self.assertTrue(pre_report["valid"], f"seeded chain invalid: {pre_report}")
        self.assertEqual(pre_report["checked"], n)

        self.runner.run_migrations(conn)
        conn.commit()
        conn.close()

        # No NULLs left, and the chain still verifies (rebuild preserved every row).
        self.assertEqual(self._null_count(), 0, "chain rows were not backfilled")
        post_report = self.al.verify_audit_hash_chain()
        self.assertTrue(post_report["valid"], f"hash chain broken by backfill: {post_report}")
        self.assertEqual(post_report["checked"], n, "backfill lost or duplicated chain rows")


if __name__ == "__main__":
    unittest.main(verbosity=2)
