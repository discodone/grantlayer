"""Add nullable constraint_violation column to audit_events

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-26 00:00:00.000000

STRICTLY ADDITIVE AND FORWARD-ONLY. Stores the pinned canonical JSON
{"type":...,"limit":...,"attempted":...} of a denied constraint check
(grant-policy witness) on decision events written from here on.

The column is nullable with no default, so existing rows keep NULL and are not
rewritten. The export/anchor canonical (audit_compliance._entry_canonical)
OMITS constraint_violation when None, so every event written before this
column existed serialises identically — every past on-chain anchor head still
recomputes to the same value. Idempotent: safe on a fresh Postgres DB and an
existing SQLite file (mirrors the frozen file-runner migration
0022_audit_constraint_violation).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("audit_events")}
    if "constraint_violation" not in columns:
        op.add_column(
            "audit_events",
            sa.Column("constraint_violation", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("audit_events")}
    if "constraint_violation" in columns:
        op.drop_column("audit_events", "constraint_violation")
