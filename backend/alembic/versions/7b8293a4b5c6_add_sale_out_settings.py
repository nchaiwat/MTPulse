"""add Sale Out settings

Revision ID: 7b8293a4b5c6
Revises: 6a718293a4b5
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "7b8293a4b5c6"
down_revision: str | Sequence[str] | None = "6a718293a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("modern_trades", sa.Column("sale_out_start_date", sa.Date(), nullable=True))
    op.add_column(
        "modern_trades",
        sa.Column(
            "sale_out_include_in_total",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    connection = op.get_bind()
    connection.execute(
        text(
            """
            UPDATE modern_trades
            SET sale_out_start_date = DATE '2025-01-01',
                sale_out_include_in_total = CASE
                    WHEN code IN ('TWD', 'HP', 'MH', 'HH', 'GH', 'TA') THEN true
                    ELSE false
                END
            WHERE code IN ('TWD', 'HP', 'MH', 'HH', 'GH', 'TA', 'DH')
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO system_settings (key, value, is_secret, updated_by)
            VALUES
                ('sale_out_active_common_cutoff', NULL, false, 'sale-out-migration'),
                ('sale_out_common_cutoff_frozen', 'false', false, 'sale-out-migration'),
                ('sale_out_common_cutoff_auto_advance', 'true', false, 'sale-out-migration')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_column("modern_trades", "sale_out_include_in_total")
    op.drop_column("modern_trades", "sale_out_start_date")
