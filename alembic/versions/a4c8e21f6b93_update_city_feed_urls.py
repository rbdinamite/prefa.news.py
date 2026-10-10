"""update city feed URLs

Revision ID: a4c8e21f6b93
Revises: 7d2c1a4f8e90
Create Date: 2026-10-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c8e21f6b93"
down_revision: Union[str, Sequence[str], None] = "7d2c1a4f8e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CITY_UPDATES = (
    {"name": "PAULO LOPES", "url_path": "https://paulolopes.sc.gov.br/feed/", "active": 1},
    {"name": "IMARUÍ", "url_path": "https://www.imaruí.sc.gov.br/feed/", "active": 1},
)


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        "UPDATE city SET url_path = :url_path, active = :active WHERE name = :name"
    )
    connection.execute(statement, CITY_UPDATES)


def downgrade() -> None:
    pass