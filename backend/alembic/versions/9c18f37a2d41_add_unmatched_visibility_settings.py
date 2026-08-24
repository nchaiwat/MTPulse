"""add unmatched visibility settings

Revision ID: 9c18f37a2d41
Revises: f4b15c7a6d20
Create Date: 2026-08-24 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9c18f37a2d41"
down_revision: str | None = "f4b15c7a6d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modern_trades",
        sa.Column(
            "show_unmatched_items",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "modern_trades",
        sa.Column(
            "show_unmatched_branches",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("modern_trades", "show_unmatched_branches")
    op.drop_column("modern_trades", "show_unmatched_items")
