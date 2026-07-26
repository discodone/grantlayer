"""Add nullable constraint_violation column to audit_events.

Stores the pinned canonical JSON {"type":...,"limit":...,"attempted":...} of a
denied constraint check (grant-policy witness) on decision events written from
here on. STRICTLY ADDITIVE AND FORWARD-ONLY:

  * the column is nullable with no default, so existing rows keep NULL and are
    not rewritten (no UPDATE — SQLite's audit-immutability triggers never fire);
  * the export/anchor canonical (audit_compliance._entry_canonical) OMITS
    constraint_violation when it is None, so every event written before this
    column existed serialises byte-for-byte as it did before — every past
    on-chain anchor head still recomputes to the same value. See
    test_constraint_violation_chain for the pinned invariant.
"""

version = "0022_audit_constraint_violation"


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _column_exists(conn, table: str, column: str) -> bool:
    if _backend(conn) == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column),
        ).fetchone()
        return row is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def apply(conn) -> None:
    if not _column_exists(conn, "audit_events", "constraint_violation"):
        conn.execute("ALTER TABLE audit_events ADD COLUMN constraint_violation TEXT")
    conn.commit()
