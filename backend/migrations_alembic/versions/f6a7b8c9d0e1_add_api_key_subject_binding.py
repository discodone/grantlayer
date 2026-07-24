"""Add nullable subject_id column to api_keys

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-24 00:00:00.000000

STRICTLY ADDITIVE AND FORWARD-ONLY. Binds an API key to the single subject
identity it may exercise as on /v1/exercise.

The column is nullable with no default, so existing rows keep NULL and are not
rewritten. A NULL binding does NOT grandfather the old permissive behaviour —
the exercise path refuses unbound keys (403 api_key_subject_unbound), so
existing keys fail CLOSED until an operator explicitly binds them. Idempotent:
safe on a fresh Postgres DB and an existing SQLite file (mirrors the frozen
file-runner migration 0021_api_key_subject).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("api_keys")}
    if "subject_id" not in columns:
        op.add_column("api_keys", sa.Column("subject_id", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("api_keys")}
    if "subject_id" in columns:
        op.drop_column("api_keys", "subject_id")
