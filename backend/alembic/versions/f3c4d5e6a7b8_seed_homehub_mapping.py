"""seed HomeHub item and verified branch mappings

Revision ID: f3c4d5e6a7b8
Revises: f1a2b3c4d5e6
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3c4d5e6a7b8"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "workbook:KPI - HH 2026.xlsx"
EFFECTIVE_FROM = "2025-01-01"

ITEM_MAPPINGS = (
    ("900446593", "FAE00-W0112-120110"),
    ("900446603", "FAE07-W0113-120110"),
    ("900479130", "FAE31-W11414-120110"),
    ("900479120", "FAE31-W11514-120110"),
    ("900442810", "FAE07-W6612-100100"),
    ("900442820", "FAE31-W6612-100110"),
    ("900442830", "FAE31-W6612-120110"),
    ("900442780", "FAE07-W7012-100100"),
    ("900442790", "FAE31-W7012-100110"),
    ("900442840", "FAE07-W6912-100100"),
    ("900442850", "FAE31-W6912-100110"),
    ("900479140", "FAE31-W11714-120110"),
    ("900442800", "FAE00-W7012-120110"),
    ("900442860", "FAE00-W6912-120110"),
    ("900414490", "FA07-F0002-120040"),
    ("900446553", "FA00-F1022-150040"),
    ("900446563", "FA07-F0002-160040"),
    ("900446573", "FA07-F0002-180040"),
    ("900446583", "FA07-F0002-200040"),
    ("112140", "FA07-W0312-240110"),
    ("900384790", "FA07-W0313-180110"),
    ("111240", "FA07-W0313-240110"),
    ("900384800", "FA07-W0322-180110"),
    ("900384780", "FA07-W0323-180110"),
    ("900392850", "FA07-W0112-100110"),
    ("900367720", "FA07-W0112-080050"),
    ("900392840", "FA07-W0113-100110"),
    ("111220", "FA07-W0113-150110"),
    ("900414500", "FA07-W0114-080050"),
    ("111211", "FA07-W0123-120110"),
    ("122101", "FA07-D0122-160205"),
    ("1221210", "FA07-D0122-200205"),
    ("1212211", "FA07-D0123-200205"),
    ("900384810", "FA00-W0312-180110"),
    ("112110", "FA00-W0112-120110"),
    ("112120", "FA00-W0112-150110"),
    ("111210", "FA00-W0113-120110"),
    ("900384760", "FA00-W0114-120110"),
    ("142100", "FA00-W0412-080050"),
    ("141200", "FA00-W0413-080050"),
    ("900216320", "FA00-L1312-060045"),
    ("900307060", "FA00-D0902-190205"),
    ("9152120", "FA00-D0802-100205"),
    ("151220", "FA00-D0803-100205"),
    ("900160360", "FA00-D0112-160205"),
    ("1221200", "FA00-D0112-200205"),
    ("900341510", "FA00-D0113-160205"),
    ("900186900", "FA00-D0113-200205"),
    ("900452740", "FUW17-W6612-100100"),
    ("900452750", "FUW17-W6612-100110"),
    ("900452710", "FUW17-W7012-100100"),
    ("900452720", "FUW17-W7012-100110"),
    ("900452770", "FUW17-W6912-100100"),
    ("900452780", "FUW17-W6912-100110"),
    ("900452790", "FUW17-W6912-120110"),
    ("900452760", "FUW00-W6612-120110"),
    ("900452730", "FUW00-W7012-120110"),
    ("900439940", "FUC17-W0112-100100"),
    ("900439950", "FUC17-W0122-100100"),
    ("900433960", "FUS00-F1022-120040"),
    ("900430230", "FUS00-F1022-150040"),
    ("900434030", "FUS00-W0212-180110"),
    ("900434020", "FUS00-W0112-150110"),
    ("900434040", "FUS00-W2212-240110"),
    ("900434060", "FUS00-W0412-080050"),
    ("900434050", "FUS00-W0512-060110"),
    ("900433970", "FUS17-F1022-160040"),
    ("900430240", "FUS17-F1022-180040"),
    ("900434000", "FUS17-W0112-100110"),
    ("900433990", "FUS17-W0112-080050"),
    ("900434010", "FUS00-W0112-120110"),
    ("900434070", "FUS31-D0112-160205"),
    ("900434080", "FUS00-D0112-200205"),
)

# Only mappings explicitly present in the manual workbook are seeded.
# HH-CHAYANGKUN stays unmatched because the workbook has no verified WA branch code.
BRANCH_MAPPINGS = (
    ("HH-KHONKAEN", "ขอนแก่น", "CHH-0001"),
    ("HH-AMNAT", "อำนาจเจริญ", "CHH-0006"),
    ("HH-WARIN", "วารินฯ", "CHH-0004"),
    ("HH-UBON", "อุบลราชธานี", "CHH-0005"),
)


def _sql_literal(value: str) -> str:
    """Render a trusted, static workbook value in online and offline migrations."""
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    for source_sku, wa_item_code in ITEM_MAPPINGS:
        sku_literal = _sql_literal(source_sku)
        op.execute(
            f"""
            INSERT INTO item_mappings (
                modern_trade_id, source_sku, source_description,
                wa_item_code, wa_item_description, status, item_type,
                report_status, effective_from, effective_to, changed_by
            )
            SELECT mt.id, {sku_literal}, NULL, {_sql_literal(wa_item_code)}, NULL,
                   'confirmed', 'normal', 'active', DATE '{EFFECTIVE_FROM}', NULL,
                   {_sql_literal(SOURCE)}
            FROM modern_trades AS mt
            WHERE mt.code = 'HH'
              AND NOT EXISTS (
                  SELECT 1 FROM item_mappings AS existing
                  WHERE existing.modern_trade_id = mt.id
                    AND existing.source_sku = {sku_literal}
                    AND existing.effective_to IS NULL
              )
            """
        )

    for source_code, source_name, wa_code in BRANCH_MAPPINGS:
        source_code_literal = _sql_literal(source_code)
        op.execute(
            f"""
            INSERT INTO branch_mappings (
                modern_trade_id, source_branch_code, source_branch_description,
                wa_branch_code, wa_branch_description, status,
                effective_from, effective_to, changed_by
            )
            SELECT mt.id, {source_code_literal}, {_sql_literal(source_name)},
                   {_sql_literal(wa_code)}, NULL, 'confirmed',
                   DATE '{EFFECTIVE_FROM}', NULL, {_sql_literal(SOURCE)}
            FROM modern_trades AS mt
            WHERE mt.code = 'HH'
              AND NOT EXISTS (
                  SELECT 1 FROM branch_mappings AS existing
                  WHERE existing.modern_trade_id = mt.id
                    AND existing.source_branch_code = {source_code_literal}
                    AND existing.effective_to IS NULL
              )
            """
        )


def downgrade() -> None:
    for table in ("item_mappings", "branch_mappings"):
        op.execute(
            f"""
            DELETE FROM {table}
            WHERE modern_trade_id = (SELECT id FROM modern_trades WHERE code = 'HH')
              AND changed_by = {_sql_literal(SOURCE)}
              AND effective_from = DATE '{EFFECTIVE_FROM}'
            """
        )
