"""add Global House trade and verified manual mappings

Revision ID: 1b2c3d4e5f60
Revises: 0a1b2c3d4e5f
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "1b2c3d4e5f60"
down_revision: str | Sequence[str] | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "workbook:KPI - GBH 2026.xlsx"
EFFECTIVE_FROM = "2025-01-01"

# Exact pairs from the two matching Manual summary sheets.
ITEM_MAPPINGS = (
    ("8859283002155", "FUS00-D0112-200205"),
    ("8859283002148", "FUS28-D0112-160205"),
    ("8859283002100", "FUS00-W0112-120110"),
    ("8859283002063", "FUS22-W0112-080050"),
    ("8859283002094", "FUS22-W0112-100110"),
    ("8859283002162", "FUS22-F1022-060040"),
    ("8859283002223", "FUS22-F1022-200040"),
    ("8859283002216", "FUS22-F1022-180040"),
    ("8859283002209", "FUS22-F1022-160040"),
    ("8859283002179", "FUS22-F1022-100040"),
    ("8859283002087", "FUS00-W0512-060110"),
    ("8859283002070", "FUS00-W0412-080050"),
    ("8859283002131", "FUS00-W2212-240110"),
    ("8859283002117", "FUS00-W0112-150110"),
    ("8859283002124", "FUS00-W0212-180110"),
    ("8859283002193", "FUS00-F1022-150040"),
    ("8859283002186", "FUS00-F1022-120040"),
    ("8859283003084", "FUW22-W6712-120110"),
    ("8859283006306", "FUW22-W12112-120110"),
    ("8859283005989", "FUW22-W0122-100100"),
    ("8859283005972", "FUW22-W0112-120110"),
)

# Verified BusinessPartner pairs. CGH-0084 is intentionally excluded because
# its WA branch code is blank in the workbook.
_WA_BRANCH_CODES = (
    "101",
    "102",
    "103",
    "104",
    "105",
    "106",
    "107",
    "108",
    "109",
    "110",
    "112",
    "114",
    "115",
    "116",
    "117",
    "118",
    "119",
    "120",
    "121",
    "122",
    "125",
    "126",
    "130",
    "113",
    "124",
    "137",
    "129",
    "132",
    "138",
    "135",
    "131",
    "142",
    "139",
    "146",
    "158",
    "153",
    "140",
    "151",
    "156",
    "127",
    "150",
    "154",
    "152",
    "144",
    "161",
    "136",
    "128",
    "145",
    "160",
    "162",
    "123",
    "163",
    "155",
    "168",
    "159",
    "171",
    "141",
    "172",
    "174",
    "173",
    "169",
    "178",
    "164",
    "175",
    "177",
    "166",
    "183",
    "179",
    "176",
    "186",
    "189",
    "184",
    "185",
    "182",
    "187",
    "188",
    "193",
    "194",
    "195",
    "192",
    "197",
    "203",
    "200",
    "206",
    "209",
    "214",
)
_SOURCE_BRANCH_NUMBERS = tuple(range(1, 84)) + tuple(range(85, 88))
BRANCH_MAPPINGS = tuple(
    (f"GH-{wa_number}", f"CGH-{source_number:04d}")
    for source_number, wa_number in zip(_SOURCE_BRANCH_NUMBERS, _WA_BRANCH_CODES, strict=True)
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
        SELECT 'GH', 'Global House', 'include', 0.07, false, false, 25,
               'GBH', false, false, NULL, 'GH', 'GH'
        WHERE NOT EXISTS (SELECT 1 FROM modern_trades WHERE code = 'GH')
        """
    )
    op.execute(
        """
        UPDATE modern_trades
        SET name = 'Global House', vat_mode = 'include',
            show_unmatched_items = false, show_unmatched_branches = false,
            source_subfolder = COALESCE(source_subfolder, 'GBH'),
            source_group_code = 'GH', branch_prefix = COALESCE(branch_prefix, 'GH')
        WHERE code = 'GH'
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
            WHERE mt.code = 'GH'
              AND NOT EXISTS (
                  SELECT 1 FROM item_mappings AS existing
                  WHERE existing.modern_trade_id = mt.id
                    AND existing.source_sku = {source_literal}
                    AND existing.effective_to IS NULL
              )
            """
        )

    for source_code, wa_code in BRANCH_MAPPINGS:
        source_literal = _sql_literal(source_code)
        op.execute(
            f"""
            INSERT INTO branch_mappings (
                modern_trade_id, source_branch_code, source_branch_description,
                wa_branch_code, wa_branch_description, status,
                effective_from, effective_to, changed_by
            )
            SELECT mt.id, {source_literal}, NULL, {_sql_literal(wa_code)}, NULL,
                   'confirmed', DATE '{EFFECTIVE_FROM}', NULL, {_sql_literal(SOURCE)}
            FROM modern_trades AS mt
            WHERE mt.code = 'GH'
              AND NOT EXISTS (
                  SELECT 1 FROM branch_mappings AS existing
                  WHERE existing.modern_trade_id = mt.id
                    AND existing.source_branch_code = {source_literal}
                    AND existing.effective_to IS NULL
              )
            """
        )


def downgrade() -> None:
    for table in ("item_mappings", "branch_mappings"):
        op.execute(
            f"""
            DELETE FROM {table}
            WHERE modern_trade_id = (SELECT id FROM modern_trades WHERE code = 'GH')
              AND changed_by = {_sql_literal(SOURCE)}
              AND effective_from = DATE '{EFFECTIVE_FROM}'
            """
        )
