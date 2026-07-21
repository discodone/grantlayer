"""Add nullable reason_code column to audit_events

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-21 00:00:00.000000

STRICTLY ADDITIVE AND FORWARD-ONLY. Stores the stable machine decision code
(mirrors PolicyResult.reason_code) on decision events written from here on.

The column is nullable with no default, so existing rows keep NULL and are not
rewritten. The export/anchor canonical (audit_compliance._entry_canonical)
OMITS reason_code when None, so every event written before this column existed
serialises identically — every past on-chain anchor head still recomputes to
the same value. Idempotent: safe on a fresh Postgres DB and an existing SQLite
file (mirrors the frozen file-runner migration 0020_audit_reason_code).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("audit_events")}
    if "reason_code" not in columns:
        op.add_column("audit_events", sa.Column("reason_code", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("audit_events")}
    if "reason_code" in columns:
        op.drop_column("audit_events", "reason_code")
