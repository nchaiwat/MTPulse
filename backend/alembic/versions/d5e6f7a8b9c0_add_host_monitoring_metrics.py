"""add host monitoring metrics

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "monitoring_snapshots",
        sa.Column("host_cpu_percent", sa.Numeric(precision=6, scale=2), nullable=True),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column(
            "host_memory_used_percent",
            sa.Numeric(precision=6, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column("host_memory_total_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column("host_disk_used_percent", sa.Numeric(precision=6, scale=2), nullable=True),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column("host_disk_total_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column("host_uptime_seconds", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "monitoring_snapshots",
        sa.Column("worker_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitoring_snapshots", "worker_heartbeat_at")
    op.drop_column("monitoring_snapshots", "host_uptime_seconds")
    op.drop_column("monitoring_snapshots", "host_disk_total_bytes")
    op.drop_column("monitoring_snapshots", "host_disk_used_percent")
    op.drop_column("monitoring_snapshots", "host_memory_total_bytes")
    op.drop_column("monitoring_snapshots", "host_memory_used_percent")
    op.drop_column("monitoring_snapshots", "host_cpu_percent")
