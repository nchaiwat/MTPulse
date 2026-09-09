"""finish HP/MH native item identifier alignment

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # HP/MH numeric SKUs are native identifiers and must never inherit TWD's
    # fixed nine-character formatting, including mappings with no current fact.
    op.execute(
        """
        UPDATE item_mappings AS mapping
        SET source_sku = ltrim(mapping.source_sku, '0'),
            changed_by = 'migration:c2d3e4f5a6b7',
            changed_at = now()
        FROM modern_trades AS mt
        WHERE mt.id = mapping.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND mapping.source_sku ~ '^0+[1-9][0-9]*$'
          AND NOT EXISTS (
              SELECT 1
              FROM item_mappings AS native
              WHERE native.modern_trade_id = mapping.modern_trade_id
                AND native.source_sku = ltrim(mapping.source_sku, '0')
                AND native.id <> mapping.id
          )
        """
    )

    # The importer had also activated an interest row under the padded key.
    # Keep the existing native registry row and remove only that duplicate.
    op.execute(
        """
        DELETE FROM sku_interests AS padded
        USING modern_trades AS mt
        WHERE mt.id = padded.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND padded.source_sku ~ '^0+[1-9][0-9]*$'
          AND EXISTS (
              SELECT 1
              FROM sku_interests AS native
              WHERE native.modern_trade_id = padded.modern_trade_id
                AND native.source_sku = ltrim(padded.source_sku, '0')
          )
        """
    )
    op.execute(
        """
        UPDATE sku_interests AS interest
        SET source_sku = ltrim(interest.source_sku, '0')
        FROM modern_trades AS mt
        WHERE mt.id = interest.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND interest.source_sku ~ '^0+[1-9][0-9]*$'
        """
    )

    # Preserve shared Sho/Pro selections if a padded flag was ever created.
    op.execute(
        """
        UPDATE sku_analysis_flags AS native
        SET is_showroom = native.is_showroom OR padded.is_showroom,
            is_promotion = native.is_promotion OR padded.is_promotion,
            updated_at = now(),
            updated_by = 'migration:c2d3e4f5a6b7'
        FROM sku_analysis_flags AS padded, modern_trades AS mt
        WHERE mt.id = native.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND padded.modern_trade_id = native.modern_trade_id
          AND padded.source_sku ~ '^0+[1-9][0-9]*$'
          AND native.source_sku = ltrim(padded.source_sku, '0')
        """
    )
    op.execute(
        """
        DELETE FROM sku_analysis_flags AS padded
        USING modern_trades AS mt
        WHERE mt.id = padded.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND padded.source_sku ~ '^0+[1-9][0-9]*$'
          AND EXISTS (
              SELECT 1
              FROM sku_analysis_flags AS native
              WHERE native.modern_trade_id = padded.modern_trade_id
                AND native.source_sku = ltrim(padded.source_sku, '0')
          )
        """
    )
    op.execute(
        """
        UPDATE sku_analysis_flags AS flag
        SET source_sku = ltrim(flag.source_sku, '0'),
            updated_at = now(),
            updated_by = 'migration:c2d3e4f5a6b7'
        FROM modern_trades AS mt
        WHERE mt.id = flag.modern_trade_id
          AND mt.code IN ('HP', 'MH')
          AND flag.source_sku ~ '^0+[1-9][0-9]*$'
        """
    )


def downgrade() -> None:
    # Native HP/MH identifiers are the canonical source keys.
    pass
