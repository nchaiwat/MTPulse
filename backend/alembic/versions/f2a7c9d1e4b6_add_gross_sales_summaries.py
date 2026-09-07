"""add gross sales summary columns

Revision ID: f2a7c9d1e4b6
Revises: e6f7a8b9c0d1
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a7c9d1e4b6"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("monthly_sales_summaries", "daily_sku_summaries"):
        op.add_column(
            table_name,
            sa.Column(
                "gross_amount",
                sa.Numeric(28, 12),
                nullable=False,
                server_default="0",
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "gross_sales_qty",
                sa.Numeric(20, 4),
                nullable=False,
                server_default="0",
            ),
        )

    op.execute("DELETE FROM monthly_sales_summaries")
    op.execute(
        """
        INSERT INTO monthly_sales_summaries (
            modern_trade_id, month_start, source_sku, source_branch_code,
            source_branch_name, source_description, amount, sales_qty,
            gross_amount, gross_sales_qty
        )
        SELECT
            fact.modern_trade_id,
            DATE_TRUNC('month', fact.data_date)::date,
            fact.source_sku,
            fact.source_branch_code,
            MIN(fact.source_branch_name),
            MIN(fact.source_description),
            SUM(fact.amount),
            SUM(fact.sales_qty),
            SUM(CASE WHEN fact.amount > 0 THEN fact.amount ELSE 0 END),
            SUM(CASE WHEN fact.sales_qty > 0 THEN fact.sales_qty ELSE 0 END)
        FROM sales_inventory_facts AS fact
        GROUP BY
            fact.modern_trade_id,
            DATE_TRUNC('month', fact.data_date)::date,
            fact.source_sku,
            fact.source_branch_code
        """
    )

    op.execute("DELETE FROM daily_sku_summaries")
    op.execute(
        """
        INSERT INTO daily_sku_summaries (
            modern_trade_id, data_date, source_sku, source_description,
            amount, sales_qty, gross_amount, gross_sales_qty,
            stock_on_hand, stock_on_order
        )
        SELECT
            fact.modern_trade_id,
            fact.data_date,
            fact.source_sku,
            MIN(fact.source_description),
            SUM(fact.amount),
            SUM(fact.sales_qty),
            SUM(CASE WHEN fact.amount > 0 THEN fact.amount ELSE 0 END),
            SUM(CASE WHEN fact.sales_qty > 0 THEN fact.sales_qty ELSE 0 END),
            SUM(fact.stock_on_hand),
            SUM(fact.stock_on_order)
        FROM sales_inventory_facts AS fact
        WHERE EXISTS (
            SELECT 1
            FROM branch_mappings AS branch
            WHERE branch.modern_trade_id = fact.modern_trade_id
              AND branch.source_branch_code = fact.source_branch_code
              AND branch.effective_from <= (
                  SELECT MAX(batch.data_date)
                  FROM import_batches AS batch
                  WHERE batch.modern_trade_id = fact.modern_trade_id
                    AND batch.status IN ('imported', 'imported_with_warnings')
              )
              AND (
                  branch.effective_to IS NULL
                  OR branch.effective_to >= (
                      SELECT MAX(batch.data_date)
                      FROM import_batches AS batch
                      WHERE batch.modern_trade_id = fact.modern_trade_id
                        AND batch.status IN ('imported', 'imported_with_warnings')
                  )
              )
        )
        GROUP BY fact.modern_trade_id, fact.data_date, fact.source_sku
        """
    )
    op.execute("ANALYZE monthly_sales_summaries")
    op.execute("ANALYZE daily_sku_summaries")


def downgrade() -> None:
    for table_name in ("daily_sku_summaries", "monthly_sales_summaries"):
        op.drop_column(table_name, "gross_sales_qty")
        op.drop_column(table_name, "gross_amount")
