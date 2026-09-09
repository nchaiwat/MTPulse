"""add SKU analysis flags

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sku_analysis_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("source_sku", sa.String(length=50), nullable=False),
        sa.Column(
            "is_showroom",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_promotion",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "modern_trade_id",
            "source_sku",
            name="uq_sku_analysis_flag_mt_sku",
        ),
    )
    op.create_index(
        "ix_sku_analysis_flag_mt_flags_sku",
        "sku_analysis_flags",
        ["modern_trade_id", "is_showroom", "is_promotion", "source_sku"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sku_analysis_flag_mt_flags_sku",
        table_name="sku_analysis_flags",
    )
    op.drop_table("sku_analysis_flags")
