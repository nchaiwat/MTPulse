"""add import warning resolution

Revision ID: f8c1d2e3a4b5
Revises: e5a72b918c44
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8c1d2e3a4b5"
down_revision: str | None = "e5a72b918c44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_batches", sa.Column("warning_resolution", sa.String(32)))
    op.add_column("import_batches", sa.Column("warning_resolution_note", sa.Text()))
    op.add_column("import_batches", sa.Column("warning_resolved_at", sa.DateTime(timezone=True)))
    op.add_column("import_batches", sa.Column("warning_resolved_by", sa.String(200)))


def downgrade() -> None:
    op.drop_column("import_batches", "warning_resolved_by")
    op.drop_column("import_batches", "warning_resolved_at")
    op.drop_column("import_batches", "warning_resolution_note")
    op.drop_column("import_batches", "warning_resolution")
