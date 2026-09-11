"""widen fact taxonomy labels for HomeHub

Revision ID: 0a1b2c3d4e5f
Revises: f3c4d5e6a7b8
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "f3c4d5e6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "sales_inventory_facts",
        "category",
        existing_type=sa.String(length=30),
        type_=sa.String(length=300),
        existing_nullable=True,
    )
    op.alter_column(
        "sales_inventory_facts",
        "subcategory",
        existing_type=sa.String(length=30),
        type_=sa.String(length=300),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "sales_inventory_facts",
        "subcategory",
        existing_type=sa.String(length=300),
        type_=sa.String(length=30),
        existing_nullable=True,
    )
    op.alter_column(
        "sales_inventory_facts",
        "category",
        existing_type=sa.String(length=300),
        type_=sa.String(length=30),
        existing_nullable=True,
    )
