"""Add nullable reason_code column to audit_events.

Stores the stable machine decision code (mirrors PolicyResult.reason_code) on
decision events written from here on. STRICTLY ADDITIVE AND FORWARD-ONLY:

  * the column is nullable with no default, so existing rows keep NULL and are
    not rewritten (no UPDATE — SQLite's audit-immutability triggers never fire);
  * the export/anchor canonical (audit_compliance._entry_canonical) OMITS
    reason_code when it is None, so every event written before this column
    existed serialises byte-for-byte as it did before — every past on-chain
    anchor head still recomputes to the same value. See
    test_audit_reason_code_chain for the pinned invariant.
"""

version = "0020_audit_reason_code"


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
    if not _column_exists(conn, "audit_events", "reason_code"):
        conn.execute("ALTER TABLE audit_events ADD COLUMN reason_code TEXT")
    conn.commit()
