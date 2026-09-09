"""add HP/MH shared import fields

Revision ID: a9b8c7d6e5f4
Revises: f2a7c9d1e4b6
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "f2a7c9d1e4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASELINE_SKUS = (
    "1165985", "1165857", "1165839", "1166012", "1165799", "1166031",
    "1166032", "1166002", "1166041", "1166042", "1165940", "1165840",
    "1165927", "1165984", "1165909", "1165963", "1165973", "1165955",
    "1165928", "1165800", "1238372", "1238350", "1239117", "1239121",
    "1238371", "1238340", "1239118", "1239088", "1164089", "1128052",
    "1128437", "1128072", "1164088", "1128473", "281871", "272466",
    "280762", "272467", "1128484", "1164186", "1128033", "1128539",
    "1164241", "1164135", "1164235", "1164147", "1164224", "1164148",
    "1164223", "1164236", "1164146", "1164251", "1128688", "1164203",
    "1164214", "1164198", "1128065", "1164118", "1164175", "1178222",
    "1164157", "1164176", "1213914", "1164136", "1164242", "1164184",
    "1158318", "1164185", "1158306", "1164204", "1164117", "1213906",
    "1271616", "1271607", "1271632", "1271631", "1271608",
)


def upgrade() -> None:
    op.add_column("modern_trades", sa.Column("source_group_code", sa.String(30)))
    op.add_column("modern_trades", sa.Column("branch_prefix", sa.String(10)))
    op.create_index(
        "ix_modern_trades_source_group_code",
        "modern_trades",
        ["source_group_code"],
    )

    op.add_column(
        "import_batches",
        sa.Column(
            "stock_value",
            sa.Numeric(28, 12),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("import_batches", sa.Column("business_fingerprint", sa.String(64)))
    op.add_column("import_batches", sa.Column("source_pair_json", sa.Text()))
    op.create_index(
        "ix_import_batches_business_fingerprint",
        "import_batches",
        ["business_fingerprint"],
    )

    op.add_column("source_files", sa.Column("source_kind", sa.String(20)))
    op.add_column("source_files", sa.Column("pair_key", sa.String(100)))
    op.add_column(
        "source_files",
        sa.Column("pair_generation_at", sa.DateTime(timezone=True)),
    )
    op.add_column("source_files", sa.Column("business_fingerprint", sa.String(64)))
    op.create_index("ix_source_files_source_kind", "source_files", ["source_kind"])
    op.create_index("ix_source_files_pair_key", "source_files", ["pair_key"])
    op.create_index(
        "ix_source_files_business_fingerprint",
        "source_files",
        ["business_fingerprint"],
    )

    op.add_column(
        "sales_inventory_facts",
        sa.Column(
            "stock_value",
            sa.Numeric(28, 12),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "daily_sku_summaries",
        sa.Column(
            "stock_value",
            sa.Numeric(28, 12),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "inventory_coverages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("source_skus_json", sa.Text(), nullable=False),
        sa.Column("source_branches_json", sa.Text(), nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "modern_trade_id",
            "data_date",
            name="uq_inventory_coverage_mt_date",
        ),
    )
    op.create_index(
        "ix_inventory_coverage_mt_date",
        "inventory_coverages",
        ["modern_trade_id", "data_date"],
    )

    connection = op.get_bind()
    for code, name, prefix in (
        ("HP", "HomePro", "S"),
        ("MH", "MegaHome", "M"),
    ):
        seed_trade = sa.text(
                """
                INSERT INTO modern_trades (
                    code, name, vat_mode, vat_rate,
                    show_unmatched_items, show_unmatched_branches,
                    report_page_size, source_subfolder, source_enabled,
                    schedule_enabled, source_group_code, branch_prefix
                )
                SELECT
                    :code, :name, 'include', 0.07,
                    false, false, 25, 'HP_MH', false,
                    false, 'HP_MH', :prefix
                WHERE NOT EXISTS (
                    SELECT 1 FROM modern_trades WHERE code = :code
                )
                """
            ).bindparams(
                sa.bindparam("code", type_=sa.String(20)),
                sa.bindparam("name", type_=sa.String(200)),
                sa.bindparam("prefix", type_=sa.String(10)),
            )
        connection.execute(
            seed_trade,
            {"code": code, "name": name, "prefix": prefix},
        )
        update_trade = sa.text(
                """
                UPDATE modern_trades
                SET source_group_code = 'HP_MH',
                    branch_prefix = :prefix
                WHERE code = :code
                """
            ).bindparams(
                sa.bindparam("code", type_=sa.String(20)),
                sa.bindparam("prefix", type_=sa.String(10)),
            )
        connection.execute(
            update_trade,
            {"code": code, "prefix": prefix},
        )

    for code in ("HP", "MH"):
        for source_sku in BASELINE_SKUS:
            seed_sku = sa.text(
                    """
                    INSERT INTO sku_interests (
                        modern_trade_id, source_sku, source_description, status,
                        first_seen_date, last_seen_date, first_seen_at, last_seen_at,
                        decided_by, decided_at
                    )
                    SELECT
                        mt.id, :source_sku, NULL, 'active',
                        DATE '2025-01-01', DATE '2025-01-01', NOW(), NOW(),
                        'system:kpi-baseline', NOW()
                    FROM modern_trades AS mt
                    WHERE mt.code = :code
                      AND NOT EXISTS (
                          SELECT 1
                          FROM sku_interests AS existing
                          WHERE existing.modern_trade_id = mt.id
                            AND existing.source_sku = :source_sku
                      )
                    """
                ).bindparams(
                    sa.bindparam("code", type_=sa.String(20)),
                    sa.bindparam("source_sku", type_=sa.String(50)),
                )
            connection.execute(
                seed_sku,
                {"code": code, "source_sku": source_sku},
            )


def downgrade() -> None:
    op.drop_index("ix_inventory_coverage_mt_date", table_name="inventory_coverages")
    op.drop_table("inventory_coverages")
    op.drop_column("daily_sku_summaries", "stock_value")
    op.drop_column("sales_inventory_facts", "stock_value")
    op.drop_index(
        "ix_source_files_business_fingerprint",
        table_name="source_files",
    )
    op.drop_index("ix_source_files_pair_key", table_name="source_files")
    op.drop_index("ix_source_files_source_kind", table_name="source_files")
    op.drop_column("source_files", "business_fingerprint")
    op.drop_column("source_files", "pair_generation_at")
    op.drop_column("source_files", "pair_key")
    op.drop_column("source_files", "source_kind")
    op.drop_index(
        "ix_import_batches_business_fingerprint",
        table_name="import_batches",
    )
    op.drop_column("import_batches", "source_pair_json")
    op.drop_column("import_batches", "business_fingerprint")
    op.drop_column("import_batches", "stock_value")
    op.drop_index(
        "ix_modern_trades_source_group_code",
        table_name="modern_trades",
    )
    op.drop_column("modern_trades", "branch_prefix")
    op.drop_column("modern_trades", "source_group_code")
