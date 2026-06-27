"""Add anchor_records table (GL-350b Cardano audit-chain anchoring)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26 00:00:00.000000

PII-free: 9 columns, no foreign keys. Idempotent (create-if-not-exists) so it is
safe on both a fresh Postgres database and an existing SQLite file.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "anchor_records" not in existing_tables:
        op.create_table(
            "anchor_records",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("workspace_id", sa.Text, nullable=False),
            sa.Column("final_hash", sa.Text, nullable=False),
            sa.Column("entry_count", sa.Integer, nullable=False),
            sa.Column("anchored_at", sa.Text, nullable=False),
            sa.Column("tx_id", sa.Text),
            sa.Column("network", sa.Text, nullable=False),
            sa.Column("anchor_label", sa.Integer, nullable=False),
            sa.Column("status", sa.Text, nullable=False),
        )
        op.create_index("idx_anchor_records_workspace_id", "anchor_records", ["workspace_id"])
        op.create_index("idx_anchor_records_status", "anchor_records", ["workspace_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "anchor_records" in existing_tables:
        op.drop_index("idx_anchor_records_status", "anchor_records")
        op.drop_index("idx_anchor_records_workspace_id", "anchor_records")
        op.drop_table("anchor_records")
