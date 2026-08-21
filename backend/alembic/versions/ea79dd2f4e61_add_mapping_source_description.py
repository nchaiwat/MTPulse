"""add mapping source description

Revision ID: ea79dd2f4e61
Revises: c8c314ec6e8a
Create Date: 2026-08-20 15:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ea79dd2f4e61"
down_revision: str | None = "c8c314ec6e8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_mappings", sa.Column("source_description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("item_mappings", "source_description")
