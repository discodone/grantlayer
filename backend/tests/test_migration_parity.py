"""Migration parity: the custom runner and Alembic must provision the same schema.

Two migration systems own this database over its history: the file-based runner
(backend/src/migrations/) that provisions local/SQLite dev and test databases,
and Alembic (backend/migrations_alembic/) that is the authoritative production
path (``make migrate``). The runner is frozen dev/test-only; Alembic is the
source of truth and may move ahead of it.

This test provisions two throwaway SQLite databases side by side — one via
``alembic upgrade head``, one via the runner from empty — introspects both with
a single shared function, and enforces DIRECTIONAL parity: every object the
runner produces (table, column, trigger, index) MUST exist in Alembic, so a real
production deploy is never missing something the application expects. Alembic is
allowed to be ahead (objects the frozen runner never received). It is expected to
be RED until Alembic reaches parity with the runner.

The allow-list below suppresses cross-backend / formatting cosmetics ONLY; see
its comments. No structural gap (a table, column, trigger, or index one system
has and the other lacks) is or may be suppressed.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ALEMBIC_INI = os.path.join(_ROOT, "backend", "alembic.ini")


def _alembic_importable() -> bool:
    import importlib.util

    return importlib.util.find_spec("alembic") is not None


# ══════════════════════════════════════════════════════════════════════════
# COSMETIC ALLOW-LIST — cross-backend / formatting spellings ONLY.
# Nothing structural may be added here. Each entry says why it is cosmetic.
# ══════════════════════════════════════════════════════════════════════════

# (1) Bookkeeping tables — each migration system carries its OWN version
#     tracker; their presence is expected, not drift.
_BOOKKEEPING_TABLES = frozenset({"alembic_version", "schema_migrations"})


# (2) Primary-key nullability quirk — SQLite permits a ``TEXT PRIMARY KEY`` to be
#     NULL unless it is spelled ``NOT NULL``; Alembic emits NOT NULL, the runner
#     relies on the PK. A primary key is non-null by definition, so the flag is a
#     spelling difference, not a real nullability gap.
def _effective_notnull(col: dict) -> int:
    return 1 if col["pk"] else int(col["notnull"])


# (3) Default-literal formatting — ``DEFAULT NULL`` and "no default" are the same
#     thing; quote/int spelling (``'0'`` vs ``0``) and Postgres ``::type`` casts
#     are formatting. This normalises FORMAT only: a real value such as ``'free'``
#     never collapses to None, so a default present on one side and absent on the
#     other IS reported as drift.
def _norm_default(d):
    if d is None:
        return None
    s = str(d).strip()
    if s.upper() == "NULL":
        return None
    s = s.split("::", 1)[0].strip()  # drop Postgres ::type cast
    s = s.strip("'").strip('"').strip()  # unify quote style
    return s.lower() or None


# (4) ``sqlite_autoindex_*`` — auto-created PK/UNIQUE backing indexes are engine
#     bookkeeping, not declared schema; excluded from the index comparison.
def _is_declared_index(name: str) -> bool:
    return not name.startswith("sqlite_autoindex")


# (5) Column TYPE names are intentionally NOT compared: INTEGER/BIGINT and
#     TEXT/VARCHAR differ across backends. Parity runs on SQLite, so existence,
#     nullability, and (normalised) default carry the structural signal.
# ══════════════════════════════════════════════════════════════════════════


def _provision_alembic(db_path: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env.pop("GRANTLAYER_DATABASE_URL", None)
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI, "upgrade", "head"],
        cwd=_ROOT, env=env, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed:\n{r.stdout}\n{r.stderr}")


def _provision_runner(db_path: str) -> None:
    env = dict(os.environ)
    env["GRANTLAYER_DB"] = db_path
    env.pop("GRANTLAYER_DATABASE_URL", None)
    env["GRANTLAYER_RUNTIME_MODE"] = "test"
    code = (
        "import sqlite3;"
        "from backend.src.migrations import runner;"
        "from backend.src.core.db import _ConnectionWrapper;"
        f"c=sqlite3.connect({db_path!r});"
        "runner.run_migrations(_ConnectionWrapper(c,'sqlite'));"
        "c.commit();c.close()"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=_ROOT, env=env, capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"runner provisioning failed:\n{r.stdout}\n{r.stderr}")


def _introspect(db_path: str) -> dict:
    """Normalised schema: tables->cols, triggers (table, norm-name), indexes (table, cols)."""
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    tables: dict[str, dict] = {}
    names = [
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    for t in names:
        cols = {}
        for row in c.execute(f"PRAGMA table_info('{t}')"):
            cols[row["name"]] = {
                "notnull": int(row["notnull"]),
                "default": row["dflt_value"],
                "pk": int(row["pk"]),
            }
        tables[t] = cols
    triggers = set()
    for row in c.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='trigger'"):
        norm = row["name"][4:] if row["name"].startswith("trg_") else row["name"]
        triggers.add((row["tbl_name"], norm))
    indexes = set()
    for t in names:
        for il in c.execute(f"PRAGMA index_list('{t}')"):
            iname = il["name"]
            if not _is_declared_index(iname):
                continue
            cols = tuple(r["name"] for r in c.execute(f"PRAGMA index_info('{iname}')"))
            indexes.add((t, frozenset(cols)))
    c.close()
    return {"tables": tables, "triggers": triggers, "indexes": indexes}


def _diff(alembic: dict, runner: dict) -> tuple[list[str], list[str]]:
    """Directional parity: runner ⊆ Alembic.

    Returns ``(failures, ahead)``.

    ``failures`` — objects the RUNNER produces that Alembic LACKS. This is the
    dangerous drift: Alembic is the authoritative production provisioner, so an
    object present in the runner but missing in Alembic means a real production
    deploy would be missing something the application expects. These fail the test.

    ``ahead`` — objects only Alembic has. The runner is frozen dev/test-only and
    Alembic is authoritative AND moving forward (e.g. anchoring tables the frozen
    runner never received). Alembic being ahead is intended, not drift. Reported
    for visibility, never a failure. This is a global directional rule, not a
    per-object allow-list: no specific object is named or excused here.
    """
    failures: list[str] = []
    ahead: list[str] = []
    at = set(alembic["tables"]) - _BOOKKEEPING_TABLES
    rt = set(runner["tables"]) - _BOOKKEEPING_TABLES

    for t in sorted(rt - at):
        failures.append(f"TABLE missing in alembic (runner has it): {t}")
    for t in sorted(at - rt):
        ahead.append(f"TABLE only in alembic (ahead): {t}")

    for t in sorted(at & rt):
        ac, rc = alembic["tables"][t], runner["tables"][t]
        for col in sorted(set(rc) - set(ac)):
            failures.append(f"COLUMN missing in alembic (runner has it): {t}.{col}")
        for col in sorted(set(ac) - set(rc)):
            ahead.append(f"COLUMN only in alembic (ahead): {t}.{col}")
        for col in sorted(set(ac) & set(rc)):
            if _effective_notnull(ac[col]) != _effective_notnull(rc[col]):
                failures.append(
                    f"COLUMN notnull differs: {t}.{col} "
                    f"(alembic={_effective_notnull(ac[col])} runner={_effective_notnull(rc[col])})"
                )
            ad, rd = _norm_default(ac[col]["default"]), _norm_default(rc[col]["default"])
            if ad != rd:
                failures.append(
                    f"COLUMN default differs: {t}.{col} (alembic={ad!r} runner={rd!r})"
                )

    for x in sorted(runner["triggers"] - alembic["triggers"]):
        failures.append(f"TRIGGER missing in alembic (runner has it): {x[0]}:{x[1]}")
    for x in sorted(alembic["triggers"] - runner["triggers"]):
        ahead.append(f"TRIGGER only in alembic (ahead): {x[0]}:{x[1]}")

    for x in sorted(runner["indexes"] - alembic["indexes"]):
        failures.append(f"INDEX missing in alembic (runner has it): {x[0]}({sorted(x[1])})")
    for x in sorted(alembic["indexes"] - runner["indexes"]):
        ahead.append(f"INDEX only in alembic (ahead): {x[0]}({sorted(x[1])})")

    return failures, ahead


@unittest.skipUnless(_alembic_importable(), "alembic not importable")
class TestMigrationParitySqlite(unittest.TestCase):
    """Full-schema parity between Alembic and the runner, on SQLite."""

    def test_alembic_contains_everything_the_runner_provisions(self):
        with tempfile.TemporaryDirectory() as d:
            a_db = os.path.join(d, "alembic.db")
            r_db = os.path.join(d, "runner.db")
            _provision_alembic(a_db)
            _provision_runner(r_db)
            failures, ahead = _diff(_introspect(a_db), _introspect(r_db))
        msg = "Alembic is missing objects the runner provisions:\n  - " + "\n  - ".join(
            failures
        )
        if ahead:
            msg += "\n(Alembic ahead, allowed: " + ", ".join(ahead) + ")"
        self.assertEqual(failures, [], msg)


# A SQLAlchemy URL (postgresql://user:pass@host:port/db) for an EMPTY, disposable
# PostgreSQL database this test may run `alembic upgrade head` against. The URL
# form is required: it is handed to both Alembic (DATABASE_URL) and psycopg2.
# Unset -> skipped (local / SQLite CI).
_PG_DSN = os.environ.get("GRANTLAYER_PARITY_PG_DSN", "")


@unittest.skipUnless(_PG_DSN and _alembic_importable(), "no disposable PG DSN provided")
class TestMigrationParityPostgresSmoke(unittest.TestCase):
    """Looser PG guard: the authoritative (Alembic) PG schema must carry the
    security-critical objects — the two audit immutability triggers and the
    audit sequence column. Avoids a full cross-backend schema comparison."""

    def test_alembic_pg_has_immutability_triggers_and_seq(self):
        import psycopg2

        env = dict(os.environ)
        env["DATABASE_URL"] = _PG_DSN
        env.pop("GRANTLAYER_DATABASE_URL", None)
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI, "upgrade", "head"],
            cwd=_ROOT, env=env, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"alembic upgrade failed:\n{r.stdout}\n{r.stderr}")

        conn = psycopg2.connect(_PG_DSN)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='audit_events' AND column_name='seq'"
            )
            self.assertIsNotNone(cur.fetchone(), "audit_events.seq missing on Alembic PG schema")
            cur.execute(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgrelid='audit_events'::regclass AND NOT tgisinternal"
            )
            trigs = {row[0] for row in cur.fetchall()}
            for expected in ("audit_events_no_update", "audit_events_no_delete"):
                self.assertIn(
                    expected, trigs, f"immutability trigger {expected} missing on Alembic PG schema"
                )
        finally:
            conn.close()


def _pg_point_app_layer_at(dsn: str):
    """Point the application DB layer (core.db + audit_log) at ``dsn``.

    ``audit_log`` snapshots ``DB_BACKEND`` at import and ``core.db`` caches its
    engine on module globals, so both are patched in place — a module reload
    would rebind audit_log's imported helpers to a stale module object. Returns a
    zero-arg ``restore()`` that reverts every patched global.
    """
    from backend.src.audit import audit_log
    from backend.src.core import db

    saved = (
        db.DB_BACKEND,
        db.DB_PATH_OR_URL,
        db._sa_engine,
        db._engine_url,
        audit_log.DB_BACKEND,
    )
    db.DB_BACKEND = "postgres"
    db.DB_PATH_OR_URL = dsn
    db._sa_engine = None
    db._engine_url = None
    audit_log.DB_BACKEND = "postgres"

    def restore() -> None:
        (
            db.DB_BACKEND,
            db.DB_PATH_OR_URL,
            db._sa_engine,
            db._engine_url,
            audit_log.DB_BACKEND,
        ) = saved

    return restore


@unittest.skipUnless(_PG_DSN and _alembic_importable(), "no disposable PG DSN provided")
class TestMigrationParityPostgresFunctional(unittest.TestCase):
    """The AUTHORITATIVE (Alembic) PostgreSQL schema must not merely CONTAIN the
    audit_events append-only objects — it must ENFORCE them and support the
    seq-dependent features the application depends on.

    Structural presence is verified by the smoke test above; this drives the real
    write / verify / paginate code paths against a pure ``alembic upgrade head``
    schema, so a future revision that drops the seq column, drops an immutability
    trigger, or otherwise regresses their behaviour fails this test loudly:

      (a) seq is populated on insert and strictly increasing
      (b) UPDATE on an audit_events row is rejected by the DB
      (c) DELETE on an audit_events row is rejected by the DB
      (d) verify_audit_hash_chain validates against this schema
      (e) cursor pagination over seq pages the full set with no overlap or gap
    """

    N = 5

    def setUp(self):
        # Provision the authoritative schema at head on the disposable PG.
        env = dict(os.environ)
        env["DATABASE_URL"] = _PG_DSN
        env.pop("GRANTLAYER_DATABASE_URL", None)
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI, "upgrade", "head"],
            cwd=_ROOT, env=env, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"alembic upgrade failed:\n{r.stdout}\n{r.stderr}")

        # Start from an empty audit_events so the chain and seq assertions are
        # deterministic. TRUNCATE bypasses the row-level immutability triggers
        # (they fire BEFORE UPDATE/DELETE, not on TRUNCATE).
        import psycopg2

        conn = psycopg2.connect(_PG_DSN)
        conn.autocommit = True
        conn.cursor().execute("TRUNCATE audit_events")
        conn.close()

        self._restore = _pg_point_app_layer_at(_PG_DSN)

    def tearDown(self):
        from backend.src.core import db

        try:
            if db._sa_engine is not None:
                db._sa_engine.dispose()
        finally:
            self._restore()

    def _expect_rejected(self, sql: str, params: tuple) -> None:
        import psycopg2

        conn = psycopg2.connect(_PG_DSN)
        conn.autocommit = True
        try:
            with self.assertRaises(psycopg2.Error) as ctx:
                conn.cursor().execute(sql, params)
            self.assertIn("immutable", str(ctx.exception).lower())
        finally:
            conn.close()

    def test_alembic_pg_audit_events_functional_parity(self):
        import psycopg2

        from backend.src.audit import audit_log
        from backend.src.core.models import AuditEvent

        # Write a real hash-chained run through the production append path. On the
        # PostgreSQL path seq is assigned by the column DEFAULT (nextval), so it
        # exercises the schema's own sequence, not a Python-computed value.
        events = []
        for i in range(self.N):
            ev = AuditEvent(
                subject_id=f"s{i}", role="operator", action="read", resource=f"file:{i}",
                approved=True, reason="parity-func",
                timestamp=f"2026-05-0{i + 1}T00:00:00.000000Z",
                tenant_id="demo", workspace_id="ws-parity",
            )
            audit_log.append_event(ev)
            events.append(ev)

        conn = psycopg2.connect(_PG_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT id, seq FROM audit_events ORDER BY seq ASC")
        rows = cur.fetchall()
        conn.close()
        seqs = [r[1] for r in rows]

        # (a) seq populated on insert and strictly increasing (unique + ordered).
        with self.subTest("seq populated and strictly increasing"):
            self.assertEqual(len(rows), self.N)
            self.assertTrue(all(s is not None for s in seqs), f"NULL seq present: {seqs}")
            self.assertEqual(seqs, sorted(seqs), f"seq not ordered: {seqs}")
            self.assertEqual(len(set(seqs)), len(seqs), f"seq not unique: {seqs}")

        # (b) UPDATE rejected by the DB immutability trigger.
        with self.subTest("UPDATE rejected"):
            self._expect_rejected(
                "UPDATE audit_events SET reason='tampered' WHERE id=%s", (events[0].id,)
            )

        # (c) DELETE rejected by the DB immutability trigger.
        with self.subTest("DELETE rejected"):
            self._expect_rejected(
                "DELETE FROM audit_events WHERE id=%s", (events[0].id,)
            )

        # (d) hash-chain verification passes against the Alembic PG schema.
        with self.subTest("verify_audit_hash_chain valid"):
            report = audit_log.verify_audit_hash_chain()
            self.assertTrue(report["valid"], f"chain invalid: {report}")
            self.assertEqual(report["checked"], self.N)

        # (e) cursor pagination over seq returns the full set, newest-first, with
        #     no overlap and no gap. list_events orders DESC and treats the cursor
        #     as "seq < after_seq".
        with self.subTest("cursor pagination pages correctly"):
            collected = []
            after_seq = None
            for _ in range(self.N + 1):  # +1 guards against a non-terminating cursor
                page = audit_log.list_events(
                    limit=2, tenant_id="demo", workspace_id="ws-parity", after_seq=after_seq
                )
                if not page:
                    break
                collected.extend(page)
                after_seq = page[-1].seq
            paged_seqs = [e.seq for e in collected]
            self.assertEqual(
                paged_seqs, sorted(seqs, reverse=True), f"pagination order wrong: {paged_seqs}"
            )
            self.assertEqual(len(set(paged_seqs)), self.N, "pagination produced overlap/gap")


if __name__ == "__main__":
    unittest.main()
