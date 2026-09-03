"""scope daily summary to mapped branches

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rebuild(*, mapped_only: bool) -> None:
    branch_filter = (
        """
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
        """
        if mapped_only
        else ""
    )
    op.execute("DELETE FROM daily_sku_summaries")
    op.execute(
        f"""
        INSERT INTO daily_sku_summaries (
            modern_trade_id,
            data_date,
            source_sku,
            source_description,
            amount,
            sales_qty,
            stock_on_hand,
            stock_on_order
        )
        SELECT
            fact.modern_trade_id,
            fact.data_date,
            fact.source_sku,
            MIN(fact.source_description),
            SUM(fact.amount),
            SUM(fact.sales_qty),
            SUM(fact.stock_on_hand),
            SUM(fact.stock_on_order)
        FROM sales_inventory_facts AS fact
        {branch_filter}
        GROUP BY fact.modern_trade_id, fact.data_date, fact.source_sku
        """
    )
    op.execute("ANALYZE daily_sku_summaries")


def upgrade() -> None:
    _rebuild(mapped_only=True)


def downgrade() -> None:
    _rebuild(mapped_only=False)
