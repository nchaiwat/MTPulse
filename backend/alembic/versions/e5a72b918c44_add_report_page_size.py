"""add report page size

Revision ID: e5a72b918c44
Revises: d1f4a8c3b220
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5a72b918c44"
down_revision: str | None = "d1f4a8c3b220"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modern_trades",
        sa.Column("report_page_size", sa.Integer(), server_default="25", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("modern_trades", "report_page_size")
