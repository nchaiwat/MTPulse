"""add sku backfill run fields

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_runs", sa.Column("target_sku", sa.String(length=50)))
    op.add_column("import_runs", sa.Column("range_start", sa.Date()))
    op.add_column("import_runs", sa.Column("range_end", sa.Date()))
    op.add_column(
        "import_runs",
        sa.Column("stop_requested_at", sa.DateTime(timezone=True)),
    )
    op.drop_index("uq_import_run_active_mt", table_name="import_runs")
    op.create_index(
        "uq_import_run_active_mt",
        "import_runs",
        ["modern_trade_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'running', 'stop_requested')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_import_run_active_mt", table_name="import_runs")
    op.create_index(
        "uq_import_run_active_mt",
        "import_runs",
        ["modern_trade_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_column("import_runs", "stop_requested_at")
    op.drop_column("import_runs", "range_end")
    op.drop_column("import_runs", "range_start")
    op.drop_column("import_runs", "target_sku")
