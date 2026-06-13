"""set_default_workspace_for_legacy_grants

Revision ID: d807a977adfb
Revises: 1073cc9e6514
Create Date: 2026-06-13 19:14:39.525141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd807a977adfb'
down_revision: Union[str, Sequence[str], None] = '1073cc9e6514'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = ("grants", "grant_requests", "grant_executions", "audit_events")


def upgrade() -> None:
    """Backfill workspace_id='default' for legacy rows that have NULL.

    After this migration the IS NULL fallback in query filters can be removed
    because all rows are guaranteed to have an explicit workspace_id.
    """
    for table in _TABLES:
        op.execute(
            f"UPDATE {table} SET workspace_id = 'default' WHERE workspace_id IS NULL"  # noqa: S608
        )


def downgrade() -> None:
    """Downgrade is intentionally a no-op: setting workspace_id back to NULL
    would re-open the isolation gap this migration closes."""
    pass
