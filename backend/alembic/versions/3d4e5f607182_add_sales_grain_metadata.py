"""add sales grain metadata for daily versus rolling source values

Revision ID: 3d4e5f607182
Revises: 2c3d4e5f6071
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3d4e5f607182"
down_revision: str | Sequence[str] | None = "2c3d4e5f6071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("sales_grain", sa.String(length=20), server_default="daily", nullable=False),
    )
    op.add_column(
        "import_batches",
        sa.Column("sales_window_days", sa.Integer(), nullable=True),
    )
    op.create_index("ix_import_batches_sales_grain", "import_batches", ["sales_grain"])

    op.add_column(
        "sales_inventory_facts",
        sa.Column("sales_grain", sa.String(length=20), server_default="daily", nullable=False),
    )
    op.add_column(
        "sales_inventory_facts",
        sa.Column("sales_window_days", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sales_inventory_facts_sales_grain",
        "sales_inventory_facts",
        ["sales_grain"],
    )

    op.execute(
        """
        UPDATE import_batches AS b
        SET sales_grain = 'rolling_30d', sales_window_days = 30
        FROM modern_trades AS mt
        WHERE b.modern_trade_id = mt.id
          AND mt.code IN ('GH', 'TA')
          AND b.data_date >= DATE '2026-08-04'
        """
    )
    op.execute(
        """
        UPDATE sales_inventory_facts AS f
        SET sales_grain = 'rolling_30d', sales_window_days = 30
        FROM modern_trades AS mt
        WHERE f.modern_trade_id = mt.id
          AND mt.code IN ('GH', 'TA')
          AND f.data_date >= DATE '2026-08-04'
        """
    )

    # Remove the previously inflated rolling values from aggregate sales while
    # preserving the as-of inventory columns in daily_sku_summaries.
    op.execute(
        """
        UPDATE daily_sku_summaries AS d
        SET amount = 0,
            sales_qty = 0,
            gross_amount = 0,
            gross_sales_qty = 0
        FROM modern_trades AS mt
        WHERE d.modern_trade_id = mt.id
          AND mt.code IN ('GH', 'TA')
          AND d.data_date >= DATE '2026-08-04'
        """
    )
    op.execute(
        """
        DELETE FROM monthly_sales_summaries AS m
        USING modern_trades AS mt
        WHERE m.modern_trade_id = mt.id
          AND mt.code IN ('GH', 'TA')
          AND m.month_start >= DATE '2026-08-01'
        """
    )
    op.execute(
        """
        INSERT INTO monthly_sales_summaries (
            modern_trade_id,
            month_start,
            source_sku,
            source_branch_code,
            source_branch_name,
            source_description,
            amount,
            sales_qty,
            gross_amount,
            gross_sales_qty
        )
        SELECT
            f.modern_trade_id,
            date_trunc('month', f.data_date)::date,
            f.source_sku,
            f.source_branch_code,
            min(f.source_branch_name),
            min(f.source_description),
            sum(f.amount),
            sum(f.sales_qty),
            sum(CASE WHEN f.amount > 0 THEN f.amount ELSE 0 END),
            sum(CASE WHEN f.sales_qty > 0 THEN f.sales_qty ELSE 0 END)
        FROM sales_inventory_facts AS f
        JOIN modern_trades AS mt ON mt.id = f.modern_trade_id
        WHERE mt.code IN ('GH', 'TA')
          AND f.data_date >= DATE '2026-08-01'
          AND f.sales_grain = 'daily'
        GROUP BY
            f.modern_trade_id,
            date_trunc('month', f.data_date)::date,
            f.source_sku,
            f.source_branch_code
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sales_inventory_facts_sales_grain", table_name="sales_inventory_facts")
    op.drop_column("sales_inventory_facts", "sales_window_days")
    op.drop_column("sales_inventory_facts", "sales_grain")
    op.drop_index("ix_import_batches_sales_grain", table_name="import_batches")
    op.drop_column("import_batches", "sales_window_days")
    op.drop_column("import_batches", "sales_grain")
