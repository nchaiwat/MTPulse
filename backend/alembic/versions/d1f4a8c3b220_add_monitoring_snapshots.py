"""add monitoring snapshots and query statistics

Revision ID: d1f4a8c3b220
Revises: a7d4c2e91f30
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1f4a8c3b220"
down_revision: str | None = "a7d4c2e91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    op.create_table(
        "monitoring_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("overall_status", sa.String(length=20), nullable=False),
        sa.Column("fact_count", sa.BigInteger(), nullable=False),
        sa.Column("database_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fact_table_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fact_indexes_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("dead_tuple_count", sa.BigInteger(), nullable=False),
        sa.Column("dead_tuple_ratio", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("active_connections", sa.Integer(), nullable=False),
        sa.Column("max_connections", sa.Integer(), nullable=False),
        sa.Column("latest_data_date", sa.Date(), nullable=True),
        sa.Column("latest_import_status", sa.String(length=32), nullable=True),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("last_vacuum_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_analyze_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modern_trades_json", sa.Text(), nullable=False),
        sa.Column("slow_queries_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_date"),
    )
    op.create_index(
        "ix_monitoring_snapshots_snapshot_date",
        "monitoring_snapshots",
        ["snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monitoring_snapshots_snapshot_date",
        table_name="monitoring_snapshots",
    )
    op.drop_table("monitoring_snapshots")
