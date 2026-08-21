"""add branch mapping descriptions

Revision ID: f4b15c7a6d20
Revises: ea79dd2f4e61
Create Date: 2026-08-20 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4b15c7a6d20"
down_revision: str | None = "ea79dd2f4e61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "branch_mappings", sa.Column("source_branch_description", sa.Text(), nullable=True)
    )
    op.add_column(
        "branch_mappings", sa.Column("wa_branch_description", sa.Text(), nullable=True)
    )
    op.execute(
        """
        UPDATE branch_mappings AS mapping
        SET source_branch_description = source.source_branch_name
        FROM (
            SELECT source_branch_code, MIN(source_branch_name) AS source_branch_name
            FROM sales_inventory_facts
            GROUP BY source_branch_code
        ) AS source
        WHERE source.source_branch_code = mapping.source_branch_code
        """
    )


def downgrade() -> None:
    op.drop_column("branch_mappings", "wa_branch_description")
    op.drop_column("branch_mappings", "source_branch_description")
