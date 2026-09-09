"""align HP/MH item identifiers with source facts

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # HP/MH source SKUs are native numeric identifiers. Earlier mapping imports
    # accidentally applied TWD's nine-character zero padding. Only normalize a
    # value when the source facts prove a single canonical identifier.
    op.execute(
        """
        WITH canonical AS (
            SELECT
                f.modern_trade_id,
                ltrim(f.source_sku, '0') AS normalized_sku,
                min(f.source_sku) AS source_sku
            FROM sales_inventory_facts AS f
            JOIN modern_trades AS mt ON mt.id = f.modern_trade_id
            WHERE mt.code IN ('HP', 'MH')
              AND f.source_sku ~ '^[0-9]+$'
            GROUP BY f.modern_trade_id, ltrim(f.source_sku, '0')
            HAVING count(DISTINCT f.source_sku) = 1
        )
        UPDATE item_mappings AS im
        SET source_sku = canonical.source_sku,
            changed_by = 'migration:c1d2e3f4a5b6',
            changed_at = now()
        FROM canonical
        WHERE im.modern_trade_id = canonical.modern_trade_id
          AND im.source_sku ~ '^0+[0-9]+$'
          AND ltrim(im.source_sku, '0') = canonical.normalized_sku
          AND im.source_sku <> canonical.source_sku
          AND NOT EXISTS (
              SELECT 1
              FROM item_mappings AS existing
              WHERE existing.modern_trade_id = im.modern_trade_id
                AND existing.source_sku = canonical.source_sku
                AND existing.id <> im.id
          )
        """
    )

    # Preserve the canonical interest row and remove only the duplicate padded
    # row generated when those broken mappings were confirmed.
    op.execute(
        """
        WITH canonical AS (
            SELECT
                f.modern_trade_id,
                ltrim(f.source_sku, '0') AS normalized_sku,
                min(f.source_sku) AS source_sku
            FROM sales_inventory_facts AS f
            JOIN modern_trades AS mt ON mt.id = f.modern_trade_id
            WHERE mt.code IN ('HP', 'MH')
              AND f.source_sku ~ '^[0-9]+$'
            GROUP BY f.modern_trade_id, ltrim(f.source_sku, '0')
            HAVING count(DISTINCT f.source_sku) = 1
        )
        DELETE FROM sku_interests AS padded
        USING canonical
        WHERE padded.modern_trade_id = canonical.modern_trade_id
          AND padded.source_sku ~ '^0+[0-9]+$'
          AND ltrim(padded.source_sku, '0') = canonical.normalized_sku
          AND padded.source_sku <> canonical.source_sku
          AND EXISTS (
              SELECT 1
              FROM sku_interests AS native
              WHERE native.modern_trade_id = padded.modern_trade_id
                AND native.source_sku = canonical.source_sku
          )
        """
    )

    # Analysis flags are shared by all users. Merge a possible padded flag into
    # its canonical row before deleting the duplicate, then normalize leftovers.
    op.execute(
        """
        WITH canonical AS (
            SELECT
                f.modern_trade_id,
                ltrim(f.source_sku, '0') AS normalized_sku,
                min(f.source_sku) AS source_sku
            FROM sales_inventory_facts AS f
            JOIN modern_trades AS mt ON mt.id = f.modern_trade_id
            WHERE mt.code IN ('HP', 'MH')
              AND f.source_sku ~ '^[0-9]+$'
            GROUP BY f.modern_trade_id, ltrim(f.source_sku, '0')
            HAVING count(DISTINCT f.source_sku) = 1
        )
        UPDATE sku_analysis_flags AS native
        SET is_showroom = native.is_showroom OR padded.is_showroom,
            is_promotion = native.is_promotion OR padded.is_promotion,
            updated_at = now(),
            updated_by = 'migration:c1d2e3f4a5b6'
        FROM sku_analysis_flags AS padded, canonical
        WHERE native.modern_trade_id = canonical.modern_trade_id
          AND native.source_sku = canonical.source_sku
          AND padded.modern_trade_id = canonical.modern_trade_id
          AND padded.source_sku ~ '^0+[0-9]+$'
          AND ltrim(padded.source_sku, '0') = canonical.normalized_sku
          AND padded.source_sku <> canonical.source_sku
        """
    )
    op.execute(
        """
        WITH canonical AS (
            SELECT
                f.modern_trade_id,
                ltrim(f.source_sku, '0') AS normalized_sku,
                min(f.source_sku) AS source_sku
            FROM sales_inventory_facts AS f
            JOIN modern_trades AS mt ON mt.id = f.modern_trade_id
            WHERE mt.code IN ('HP', 'MH')
              AND f.source_sku ~ '^[0-9]+$'
            GROUP BY f.modern_trade_id, ltrim(f.source_sku, '0')
            HAVING count(DISTINCT f.source_sku) = 1
        )
        DELETE FROM sku_analysis_flags AS padded
        USING canonical
        WHERE padded.modern_trade_id = canonical.modern_trade_id
          AND padded.source_sku ~ '^0+[0-9]+$'
          AND ltrim(padded.source_sku, '0') = canonical.normalized_sku
          AND padded.source_sku <> canonical.source_sku
          AND EXISTS (
              SELECT 1
              FROM sku_analysis_flags AS native
              WHERE native.modern_trade_id = padded.modern_trade_id
                AND native.source_sku = canonical.source_sku
          )
        """
    )


def downgrade() -> None:
    # Data correction is intentionally irreversible: TWD padding was never a
    # valid identifier rule for HP/MH source data.
    pass
