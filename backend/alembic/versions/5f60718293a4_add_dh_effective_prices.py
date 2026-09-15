"""add DoHome effective prices

Revision ID: 5f60718293a4
Revises: 4e5f60718293
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5f60718293a4"
down_revision: str | Sequence[str] | None = "4e5f60718293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dh_effective_prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("source_sku", sa.String(length=50), nullable=False),
        sa.Column("unit_price_ex_vat", sa.Numeric(precision=28, scale=12), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("changed_by", sa.String(length=200), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_dh_price_date_range",
        ),
        sa.CheckConstraint(
            "unit_price_ex_vat > 0",
            name="ck_dh_price_positive",
        ),
        sa.ForeignKeyConstraint(
            ["modern_trade_id"],
            ["modern_trades.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "modern_trade_id",
            "source_sku",
            "effective_from",
            name="uq_dh_price_mt_sku_from",
        ),
    )
    op.create_index(
        "ix_dh_price_lookup",
        "dh_effective_prices",
        ["modern_trade_id", "source_sku", "effective_from", "effective_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dh_price_lookup", table_name="dh_effective_prices")
    op.drop_table("dh_effective_prices")
