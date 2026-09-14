"""add Thai-Aust trade and verified TA item mappings

Revision ID: 2c3d4e5f6071
Revises: 1b2c3d4e5f60
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2c3d4e5f6071"
down_revision: str | Sequence[str] | None = "1b2c3d4e5f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "workbook:KPI - TA 2026.xlsx"
EFFECTIVE_FROM = "2025-01-01"

# Exact pairs from the TA Manual summary. The leading zero is part of the
# Product Code found in the daily workbook; no length or zfill rule is used.
ITEM_MAPPINGS = (
    ("082112204932", "FA03-F1022-120040"),
    ("082202075912", "FA03-F1022-150040"),
    ("082006165266", "FA03-F1022-180040"),
    ("082010095541", "FA03-F1022-200040"),
    ("082305244159", "FA03-F1023-120040"),
    ("082305245279", "FA03-F1023-150040"),
    ("082305244693", "FA03-F1023-180040"),
    ("082305243406", "FA03-F1023-200040"),
    ("081905285089", "FA03-W0312-180110"),
    ("082202285170", "FA03-W0312-240110"),
    ("082305169421", "FA03-W0313-240110"),
    ("082305167918", "FA03-W0313-180110"),
    ("081905243828", "FA03-W0112-120110"),
    ("081905283023", "FA03-W0112-150110"),
    ("082203012225", "FA03-W0112-080050"),
    ("082305165622", "FA03-W0113-120110"),
    ("082305164139", "FA03-W0113-150110"),
    ("082305163969", "FA03-W0113-080050"),
    ("082203013156", "FA03-W0412-080050"),
    ("082305165310", "FA03-W0413-080050"),
    ("081905281291", "FA03-D0112-200205"),
    ("082305162119", "FA03-D0113-200205"),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO modern_trades (
            code, name, vat_mode, vat_rate, show_unmatched_items,
            show_unmatched_branches, report_page_size, source_subfolder,
            source_enabled, schedule_enabled, schedule_time,
            source_group_code, branch_prefix
        )
        SELECT 'TA', 'Thai-Aust', 'include', 0.07, false, false, 25,
               'TA', false, false, NULL, 'TA', 'GH'
        WHERE NOT EXISTS (SELECT 1 FROM modern_trades WHERE code = 'TA')
        """
    )
    op.execute(
        """
        UPDATE modern_trades
        SET name = 'Thai-Aust', vat_mode = 'include',
            show_unmatched_items = false, show_unmatched_branches = false,
            source_subfolder = 'TA', source_group_code = 'TA', branch_prefix = 'GH'
        WHERE code = 'TA'
        """
    )

    for source_sku, wa_item_code in ITEM_MAPPINGS:
        source_literal = _sql_literal(source_sku)
        op.execute(
            f"""
            INSERT INTO item_mappings (
                modern_trade_id, source_sku, source_description,
                wa_item_code, wa_item_description, status, item_type,
                report_status, effective_from, effective_to, changed_by
            )
            SELECT mt.id, {source_literal}, NULL, {_sql_literal(wa_item_code)}, NULL,
                   'confirmed', 'normal', 'active', DATE '{EFFECTIVE_FROM}', NULL,
                   {_sql_literal(SOURCE)}
            FROM modern_trades AS mt
            WHERE mt.code = 'TA'
              AND NOT EXISTS (
                  SELECT 1 FROM item_mappings AS existing
                  WHERE existing.modern_trade_id = mt.id
                    AND existing.source_sku = {source_literal}
                    AND existing.effective_to IS NULL
              )
            """
        )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM item_mappings
        WHERE modern_trade_id = (SELECT id FROM modern_trades WHERE code = 'TA')
          AND changed_by = {_sql_literal(SOURCE)}
          AND effective_from = DATE '{EFFECTIVE_FROM}'
        """
    )
