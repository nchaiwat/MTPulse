"""add DoHome modern trade

Revision ID: 6a718293a4b5
Revises: 5f60718293a4
Create Date: 2026-09-15
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "6a718293a4b5"
down_revision: str | Sequence[str] | None = "5f60718293a4"
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
                report_page_size, source_subfolder,
                source_enabled, schedule_enabled, source_group_code
            )
            SELECT
                'DH', 'DoHome', 'exclude', 0.07,
                true, true,
                25, 'DoHome',
                false, false, 'DH'
            WHERE NOT EXISTS (
                SELECT 1 FROM modern_trades WHERE code = 'DH'
            )
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE modern_trades
            SET name = 'DoHome',
                vat_mode = 'exclude',
                show_unmatched_items = true,
                show_unmatched_branches = true,
                source_subfolder = COALESCE(source_subfolder, 'DoHome'),
                source_group_code = 'DH'
            WHERE code = 'DH'
            """
        )
    )


def downgrade() -> None:
    # Keep the DH identity because Phase 1 price rows may reference it.
    pass
