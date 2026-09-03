"""add daily sku summary

Revision ID: b3c4d5e6f7a8
Revises: a2c3d4e5f6b7
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2c3d4e5f6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_sku_summaries",
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("source_sku", sa.String(length=50), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=28, scale=12), nullable=False),
        sa.Column("sales_qty", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("stock_on_hand", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("stock_on_order", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint(
            "modern_trade_id",
            "data_date",
            "source_sku",
            name="pk_daily_sku_summaries",
        ),
    )
    op.create_index(
        "ix_daily_sku_mt_sku_date",
        "daily_sku_summaries",
        ["modern_trade_id", "source_sku", "data_date"],
    )
    op.execute(
        """
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
            modern_trade_id,
            data_date,
            source_sku,
            MIN(source_description),
            SUM(amount),
            SUM(sales_qty),
            SUM(stock_on_hand),
            SUM(stock_on_order)
        FROM sales_inventory_facts
        GROUP BY modern_trade_id, data_date, source_sku
        """
    )
    op.execute("ANALYZE daily_sku_summaries")


def downgrade() -> None:
    op.drop_index(
        "ix_daily_sku_mt_sku_date",
        table_name="daily_sku_summaries",
    )
    op.drop_table("daily_sku_summaries")
