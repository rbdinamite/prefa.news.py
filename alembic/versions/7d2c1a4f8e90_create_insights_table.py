"""create insights table

Revision ID: 7d2c1a4f8e90
Revises: 52eb3694b220
Create Date: 2026-08-21 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d2c1a4f8e90"
down_revision: Union[str, Sequence[str], None] = "52eb3694b220"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("cities", sa.JSON(), nullable=False),
        sa.Column("news_ids", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_insights_generated_at"), "insights", ["generated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_insights_generated_at"), table_name="insights")
    op.drop_table("insights")
