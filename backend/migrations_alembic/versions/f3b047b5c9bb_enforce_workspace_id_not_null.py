"""enforce_workspace_id_not_null

Revision ID: f3b047b5c9bb
Revises: d807a977adfb
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f3b047b5c9bb"
down_revision: Union[str, Sequence[str], None] = "d807a977adfb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("grants", "grant_requests", "challenges", "grant_executions", "evidence_archives")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    for table in _TABLES:
        op.execute(f"UPDATE {table} SET workspace_id = 'default' WHERE workspace_id IS NULL")
        if dialect == "postgresql":
            op.execute(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")


def downgrade() -> None:
    pass
