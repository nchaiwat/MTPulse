"""add fact modern trade key and monthly sales summary

Revision ID: c4f8e2a19b70
Revises: b6e4d9a2c731
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4f8e2a19b70"
down_revision: str | None = "b6e4d9a2c731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sales_inventory_facts",
        sa.Column("modern_trade_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE sales_inventory_facts AS fact
        SET modern_trade_id = batch.modern_trade_id
        FROM import_batches AS batch
        WHERE batch.id = fact.batch_id
        """
    )
    op.alter_column("sales_inventory_facts", "modern_trade_id", nullable=False)
    op.create_foreign_key(
        "fk_fact_modern_trade",
        "sales_inventory_facts",
        "modern_trades",
        ["modern_trade_id"],
        ["id"],
    )
    op.drop_index("ix_fact_date_sku", table_name="sales_inventory_facts")
    op.drop_index("ix_fact_date_branch", table_name="sales_inventory_facts")
    op.create_index(
        "ix_fact_mt_date_sku",
        "sales_inventory_facts",
        ["modern_trade_id", "data_date", "source_sku"],
    )
    op.create_index(
        "ix_fact_mt_date_branch",
        "sales_inventory_facts",
        ["modern_trade_id", "data_date", "source_branch_code"],
    )

    op.create_table(
        "monthly_sales_summaries",
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("source_sku", sa.String(length=50), nullable=False),
        sa.Column("source_branch_code", sa.String(length=30), nullable=False),
        sa.Column("source_branch_name", sa.String(length=300), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=28, scale=12), nullable=False),
        sa.Column("sales_qty", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint(
            "modern_trade_id",
            "month_start",
            "source_sku",
            "source_branch_code",
            name="pk_monthly_sales_summaries",
        ),
    )
    op.create_index(
        "ix_monthly_sales_mt_month_sku",
        "monthly_sales_summaries",
        ["modern_trade_id", "month_start", "source_sku"],
    )
    op.create_index(
        "ix_monthly_sales_mt_month_branch",
        "monthly_sales_summaries",
        ["modern_trade_id", "month_start", "source_branch_code"],
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
            sales_qty
        )
        SELECT
            modern_trade_id,
            date_trunc('month', data_date)::date,
            source_sku,
            source_branch_code,
            min(source_branch_name),
            min(source_description),
            sum(amount),
            sum(sales_qty)
        FROM sales_inventory_facts
        GROUP BY
            modern_trade_id,
            date_trunc('month', data_date)::date,
            source_sku,
            source_branch_code
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monthly_sales_mt_month_branch",
        table_name="monthly_sales_summaries",
    )
    op.drop_index(
        "ix_monthly_sales_mt_month_sku",
        table_name="monthly_sales_summaries",
    )
    op.drop_table("monthly_sales_summaries")
    op.drop_index("ix_fact_mt_date_branch", table_name="sales_inventory_facts")
    op.drop_index("ix_fact_mt_date_sku", table_name="sales_inventory_facts")
    op.create_index(
        "ix_fact_date_branch",
        "sales_inventory_facts",
        ["data_date", "source_branch_code"],
    )
    op.create_index(
        "ix_fact_date_sku",
        "sales_inventory_facts",
        ["data_date", "source_sku"],
    )
    op.drop_constraint(
        "fk_fact_modern_trade",
        "sales_inventory_facts",
        type_="foreignkey",
    )
    op.drop_column("sales_inventory_facts", "modern_trade_id")
