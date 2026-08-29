"""add fileshare source settings

Revision ID: d8a6f2c4e901
Revises: c4f8e2a19b70
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8a6f2c4e901"
down_revision: str | None = "c4f8e2a19b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modern_trades",
        sa.Column("source_subfolder", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "modern_trades",
        sa.Column(
            "source_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE modern_trades
        SET source_subfolder = 'TWD', source_enabled = true
        WHERE code = 'TWD'
        """
    )


def downgrade() -> None:
    op.drop_column("modern_trades", "source_enabled")
    op.drop_column("modern_trades", "source_subfolder")
