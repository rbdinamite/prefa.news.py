"""add title_pt to news

Revision ID: 52eb3694b220
Revises: 
Create Date: 2026-08-21 10:49:09.424407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52eb3694b220'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('news', sa.Column('title_pt', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('news', 'title_pt')
