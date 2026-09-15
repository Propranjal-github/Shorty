"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-14 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("short_code", sa.String(length=16), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("ix_urls_created_at", "urls", ["created_at"])

    op.create_table(
        "click_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=16), nullable=False),
        sa.Column("clicked_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("referrer", sa.String(length=2048), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["short_code"], ["urls.short_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_click_events_short_code", "click_events", ["short_code"])
    op.create_index("ix_click_events_clicked_at", "click_events", ["clicked_at"])

    op.create_table(
        "machine_id_leases",
        sa.Column("machine_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("acquired_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("machine_id"),
    )


def downgrade() -> None:
    op.drop_table("machine_id_leases")
    op.drop_index("ix_click_events_clicked_at", table_name="click_events")
    op.drop_index("ix_click_events_short_code", table_name="click_events")
    op.drop_table("click_events")
    op.drop_index("ix_urls_created_at", table_name="urls")
    op.drop_index("ix_urls_short_code", table_name="urls")
    op.drop_table("urls")
