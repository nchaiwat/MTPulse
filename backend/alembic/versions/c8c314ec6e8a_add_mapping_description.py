"""add mapping description

Revision ID: c8c314ec6e8a
Revises: 60c74273e8ee
Create Date: 2026-08-20 13:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8c314ec6e8a"
down_revision: str | None = "60c74273e8ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_mappings", sa.Column("wa_item_description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("item_mappings", "wa_item_description")
