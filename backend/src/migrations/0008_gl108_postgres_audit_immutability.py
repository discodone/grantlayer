"""GrantLayer MVP — GL-108 PostgreSQL Audit Immutability Trigger.

Adds PostgreSQL triggers to prevent UPDATE and DELETE on audit_events,
matching the SQLite protection from GL-102.

Compatible with SQLite and PostgreSQL backends.
"""

version = "0008_gl108_postgres_audit_immutability"


def apply(conn) -> None:
    """Create PostgreSQL audit_events immutability triggers."""
    backend = getattr(conn, "backend", "sqlite")

    if backend == "postgres":
        # Idempotent: CREATE OR REPLACE FUNCTION overwrites any previous definition.
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION audit_immutability_check()
            RETURNS TRIGGER AS $$
            BEGIN
              RAISE EXCEPTION 'audit_events are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )

        # Idempotent: drop before create avoids "already exists" errors.
        conn.execute(
            "DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events"
        )
        conn.execute(
            """
            CREATE TRIGGER audit_events_no_update
              BEFORE UPDATE ON audit_events
              FOR EACH ROW
              EXECUTE FUNCTION audit_immutability_check()
            """
        )

        conn.execute(
            "DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events"
        )
        conn.execute(
            """
            CREATE TRIGGER audit_events_no_delete
              BEFORE DELETE ON audit_events
              FOR EACH ROW
              EXECUTE FUNCTION audit_immutability_check()
            """
        )

    conn.commit()
