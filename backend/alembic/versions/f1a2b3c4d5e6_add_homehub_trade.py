"""add HomeHub modern trade

Revision ID: f1a2b3c4d5e6
Revises: d3e4f5a6b7c8
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        text(
            """
            INSERT INTO modern_trades (
                code, name, vat_mode, vat_rate,
                show_unmatched_items, show_unmatched_branches,
                report_page_size, source_subfolder, source_enabled,
                schedule_enabled, source_group_code
            )
            SELECT
                'HH', 'HomeHub', 'exclude', 0.07,
                true, true, 25, 'HomeHub', false,
                false, 'HH'
            WHERE NOT EXISTS (
                SELECT 1 FROM modern_trades WHERE code = 'HH'
            )
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(text("DELETE FROM modern_trades WHERE code = 'HH'"))
