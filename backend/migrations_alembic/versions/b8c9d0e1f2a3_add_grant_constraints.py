"""Add nullable constraints column to grants

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-26 00:00:00.000000

STRICTLY ADDITIVE. Stores the canonical JSON of the grant's typed constraints
object ({"max_fee_lovelace": <int>} in this slice). The stored text is part of
the SIGNED grant canonical (omit-when-None), so a post-signing edit of a limit
is detected as hash_mismatch at exercise time.

Nullable, no default, no row rewrites — every existing grant keeps NULL,
serialises byte-identically in canonical_grant_payload, and its signature
keeps verifying. Idempotent: safe on a fresh Postgres DB and an existing
SQLite file (mirrors the frozen file-runner migration 0023_grant_constraints).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("grants")}
    if "constraints" not in columns:
        op.add_column("grants", sa.Column("constraints", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("grants")}
    if "constraints" in columns:
        op.drop_column("grants", "constraints")
