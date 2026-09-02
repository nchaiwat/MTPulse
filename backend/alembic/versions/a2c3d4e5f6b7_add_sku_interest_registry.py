"""add sku interest registry

Revision ID: a2c3d4e5f6b7
Revises: e1b2c3d4f5a6
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2c3d4e5f6b7"
down_revision: str | None = "e1b2c3d4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sku_interests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("source_sku", sa.String(length=50), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("first_seen_date", sa.Date(), nullable=False),
        sa.Column("last_seen_date", sa.Date(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_by", sa.String(length=200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "modern_trade_id",
            "source_sku",
            name="uq_sku_interest_mt_sku",
        ),
    )
    op.create_index(
        "ix_sku_interest_mt_status",
        "sku_interests",
        ["modern_trade_id", "status"],
    )
    op.create_index(
        "ix_fact_mt_sku_branch",
        "sales_inventory_facts",
        ["modern_trade_id", "source_sku", "source_branch_code"],
    )
    op.execute(
        """
        INSERT INTO sku_interests (
            modern_trade_id,
            source_sku,
            source_description,
            status,
            first_seen_date,
            last_seen_date,
            first_seen_at,
            last_seen_at,
            decided_by,
            decided_at
        )
        SELECT
            facts.modern_trade_id,
            facts.source_sku,
            MIN(facts.source_description),
            CASE WHEN EXISTS (
                SELECT 1
                FROM item_mappings mapping
                WHERE mapping.modern_trade_id = facts.modern_trade_id
                  AND mapping.source_sku = facts.source_sku
                  AND mapping.report_status = 'active'
                  AND mapping.effective_to IS NULL
            ) THEN 'active' ELSE 'ignored' END,
            MIN(facts.data_date),
            MAX(facts.data_date),
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            CASE WHEN EXISTS (
                SELECT 1
                FROM item_mappings mapping
                WHERE mapping.modern_trade_id = facts.modern_trade_id
                  AND mapping.source_sku = facts.source_sku
                  AND mapping.report_status = 'active'
                  AND mapping.effective_to IS NULL
            ) THEN 'system:mapping' ELSE 'system:baseline' END,
            CURRENT_TIMESTAMP
        FROM sales_inventory_facts facts
        GROUP BY facts.modern_trade_id, facts.source_sku
        """
    )
    op.execute(
        """
        INSERT INTO sku_interests (
            modern_trade_id,
            source_sku,
            source_description,
            status,
            first_seen_date,
            last_seen_date,
            first_seen_at,
            last_seen_at,
            decided_by,
            decided_at
        )
        SELECT
            mapping.modern_trade_id,
            mapping.source_sku,
            MAX(mapping.source_description),
            'active',
            MIN(mapping.effective_from),
            MAX(mapping.effective_from),
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            'system:mapping',
            CURRENT_TIMESTAMP
        FROM item_mappings mapping
        WHERE mapping.report_status = 'active'
          AND mapping.effective_to IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM sku_interests interest
              WHERE interest.modern_trade_id = mapping.modern_trade_id
                AND interest.source_sku = mapping.source_sku
          )
        GROUP BY mapping.modern_trade_id, mapping.source_sku
        """
    )
    op.execute("ANALYZE item_mappings")
    op.execute("ANALYZE branch_mappings")
    op.execute("ANALYZE sales_inventory_facts")
    op.execute("ANALYZE monthly_sales_summaries")
    op.execute("ANALYZE sku_interests")


def downgrade() -> None:
    op.drop_index("ix_fact_mt_sku_branch", table_name="sales_inventory_facts")
    op.drop_index("ix_sku_interest_mt_status", table_name="sku_interests")
    op.drop_table("sku_interests")
