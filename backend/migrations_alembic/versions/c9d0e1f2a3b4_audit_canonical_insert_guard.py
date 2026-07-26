"""Audit canonical-insert guard triggers

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-26 00:00:00.000000

DDL-ONLY, ZERO ROW CHANGES. Both hash layers (row_hash scheme and the anchor
fold) hash NORMALIZED values, so a raw INSERT storing a non-canonical form
(approved=5, challenge_result='') is invisible to both. The app write path is
already canonical and UPDATE/DELETE are trigger-blocked; this adds the
BEFORE-INSERT guard so a new row must store exactly the hashed form.
Existing rows untouched — no anchored bytes move. Mirrors the frozen
file-runner migration 0024_audit_canonical_insert_guard.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CANONICAL_VIOLATION = (
    "NEW.approved IS NULL OR NEW.approved NOT IN (0, 1) "
    "OR NEW.challenge_present IS NULL OR NEW.challenge_present NOT IN (0, 1) "
    "OR NEW.challenge_result IS NULL OR NEW.challenge_result = '' "
    "OR NEW.grant_signature_result IS NULL OR NEW.grant_signature_result = ''"
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
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
        op.execute(
            "DROP TRIGGER IF EXISTS audit_events_canonical_insert ON audit_events"
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_canonical_insert
              BEFORE INSERT ON audit_events
              FOR EACH ROW
              EXECUTE FUNCTION audit_canonical_insert_check()
            """
        )
    else:  # sqlite — mirrors runner 0024
        op.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_canonical_insert
            BEFORE INSERT ON audit_events
            WHEN {_CANONICAL_VIOLATION}
            BEGIN
                SELECT RAISE(ABORT,
                    'audit_events insert must store the canonical hashed form');
            END
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS audit_events_canonical_insert ON audit_events"
        )
        op.execute("DROP FUNCTION IF EXISTS audit_canonical_insert_check()")
    else:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_canonical_insert")
