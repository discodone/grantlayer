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


if __name__ == "__main__":
    unittest.main()
