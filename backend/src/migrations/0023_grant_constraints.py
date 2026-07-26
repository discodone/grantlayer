"""Add nullable constraints column to grants.

Stores the canonical JSON (sorted keys, compact separators) of the grant's
typed constraints object — this slice: {"max_fee_lovelace": <int>} only.
The stored text is part of the SIGNED grant canonical (omit-when-None), so a
post-signing edit of a limit is detected as hash_mismatch at exercise time.

STRICTLY ADDITIVE: nullable, no default, no row rewrites — every existing
grant keeps NULL, serialises byte-identically in canonical_grant_payload, and
its signature keeps verifying.
"""

version = "0023_grant_constraints"


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
    if not _column_exists(conn, "grants", "constraints"):
        conn.execute("ALTER TABLE grants ADD COLUMN constraints TEXT")
    conn.commit()
