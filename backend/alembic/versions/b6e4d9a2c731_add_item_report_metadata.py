"""add item report metadata

Revision ID: b6e4d9a2c731
Revises: f8c1d2e3a4b5
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b6e4d9a2c731"
down_revision: str | None = "f8c1d2e3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "item_mappings",
        sa.Column("item_type", sa.String(20), server_default="normal", nullable=False),
    )
    op.add_column(
        "item_mappings",
        sa.Column("report_status", sa.String(20), server_default="active", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("item_mappings", "report_status")
    op.drop_column("item_mappings", "item_type")