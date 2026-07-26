"""GrantLayer MVP — Audit canonical-insert guard.

Hash hygiene: both hash layers (row_hash scheme and the anchor-export fold)
hash NORMALIZED values — approved -> bool, challenge_present -> bool,
challenge_result NULL/'' -> "legacy_mode", grant_signature_result NULL/'' ->
"not_checked" — so a raw stored value whose normalized form is unchanged
(approved 5, challenge_result '') is not bound one-to-one to its hashed form.
The application write path already stores exactly the canonical form
(audit_log._build_insert_params) and UPDATE/DELETE are trigger-blocked
(0005 SQLite / 0008 PostgreSQL); the remaining flank is a direct raw INSERT.

This migration closes that flank with BEFORE-INSERT canonical-guard triggers
(same pattern as 0005/0008): a NEW row must store exactly the form the hash
layers bind. EXISTING rows are untouched — no stored value, canonical, or
hash changes anywhere, so anchored bytes cannot move. Dump/restore stays
safe: both pg_dump and sqlite .dump emit data before recreating triggers.

Compatible with SQLite and PostgreSQL backends.
"""

version = "0024_audit_canonical_insert_guard"

_CANONICAL_VIOLATION = (
    "NEW.approved IS NULL OR NEW.approved NOT IN (0, 1) "
    "OR NEW.challenge_present IS NULL OR NEW.challenge_present NOT IN (0, 1) "
    "OR NEW.challenge_result IS NULL OR NEW.challenge_result = '' "
    "OR NEW.grant_signature_result IS NULL OR NEW.grant_signature_result = ''"
)


def apply(conn) -> None:
    """Create audit_events canonical-insert guard triggers."""
    backend = getattr(conn, "backend", "sqlite")

    if backend == "sqlite":
        conn.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_canonical_insert
            BEFORE INSERT ON audit_events
            WHEN {_CANONICAL_VIOLATION}
            BEGIN
                SELECT RAISE(ABORT,
                    'audit_events insert must store the canonical hashed form');
            END;
            """
        )

    if backend == "postgres":
        # Idempotent: CREATE OR REPLACE FUNCTION + drop-before-create trigger,
        # mirroring 0008_gl108_postgres_audit_immutability.
        conn.execute(
            f"""
            CREATE OR REPLACE FUNCTION audit_canonical_insert_check()
            RETURNS TRIGGER AS $$
            BEGIN
              IF {_CANONICAL_VIOLATION} THEN
                RAISE EXCEPTION
                  'audit_events insert must store the canonical hashed form';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        conn.execute(
            "DROP TRIGGER IF EXISTS audit_events_canonical_insert ON audit_events"
        )
        conn.execute(
            """
            CREATE TRIGGER audit_events_canonical_insert
              BEFORE INSERT ON audit_events
              FOR EACH ROW
              EXECUTE FUNCTION audit_canonical_insert_check()
            """
        )

    conn.commit()
