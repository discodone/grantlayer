"""Add webhook_subscriptions and webhook_deliveries tables

Revision ID: a1b2c3d4e5f6
Revises: f3b047b5c9bb
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f3b047b5c9bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "webhook_subscriptions" not in existing_tables:
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("tenant_id", sa.Text, nullable=False),
            sa.Column("workspace_id", sa.Text),
            sa.Column("url", sa.Text, nullable=False),
            sa.Column("events", sa.Text, nullable=False),
            sa.Column("secret", sa.Text, nullable=False),
            sa.Column("active", sa.Integer, nullable=False, server_default="1"),
            sa.Column("created_at", sa.Text, nullable=False),
            sa.Column("created_by", sa.Text, nullable=False),
        )
        op.create_index("idx_webhook_subscriptions_tenant_id", "webhook_subscriptions", ["tenant_id"])
        op.create_index("idx_webhook_subscriptions_active", "webhook_subscriptions", ["tenant_id", "active"])

    if "webhook_deliveries" not in existing_tables:
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("webhook_id", sa.Text, nullable=False),
            sa.Column("tenant_id", sa.Text, nullable=False),
            sa.Column("event_type", sa.Text, nullable=False),
            sa.Column("payload", sa.Text, nullable=False),
            sa.Column("status", sa.Text, nullable=False),
            sa.Column("http_status", sa.Integer),
            sa.Column("error", sa.Text),
            sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
            sa.Column("created_at", sa.Text, nullable=False),
            sa.Column("delivered_at", sa.Text),
        )
        op.create_index("idx_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
        op.create_index("idx_webhook_deliveries_tenant_id", "webhook_deliveries", ["tenant_id"])
        op.create_index("idx_webhook_deliveries_created_at", "webhook_deliveries", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "webhook_deliveries" in existing_tables:
        op.drop_index("idx_webhook_deliveries_created_at", "webhook_deliveries")
        op.drop_index("idx_webhook_deliveries_tenant_id", "webhook_deliveries")
        op.drop_index("idx_webhook_deliveries_webhook_id", "webhook_deliveries")
        op.drop_table("webhook_deliveries")

    if "webhook_subscriptions" in existing_tables:
        op.drop_index("idx_webhook_subscriptions_active", "webhook_subscriptions")
        op.drop_index("idx_webhook_subscriptions_tenant_id", "webhook_subscriptions")
        op.drop_table("webhook_subscriptions")
