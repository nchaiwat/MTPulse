"""add automatic fileshare import

Revision ID: e1b2c3d4f5a6
Revises: d8a6f2c4e901
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1b2c3d4f5a6"
down_revision: str | None = "d8a6f2c4e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "modern_trades",
        sa.Column(
            "schedule_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "modern_trades",
        sa.Column("schedule_time", sa.Time(), nullable=True),
    )
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="import", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=200), nullable=False),
        sa.Column("scheduled_local_date", sa.Date(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("found_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ready_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pending_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_status", "import_runs", ["status"])
    op.create_index(
        "ix_import_run_mt_requested",
        "import_runs",
        ["modern_trade_id", "requested_at"],
    )
    op.create_index(
        "uq_import_run_active_mt",
        "import_runs",
        ["modern_trade_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "source_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("modern_trade_id", sa.Integer(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("detected_data_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("imported_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["imported_batch_id"], ["import_batches.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_run_id"], ["import_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["modern_trade_id"], ["modern_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "modern_trade_id", "source_path", name="uq_source_file_mt_path"
        ),
    )
    op.create_index("ix_source_files_status", "source_files", ["status"])
    op.create_index(
        "ix_source_file_mt_status",
        "source_files",
        ["modern_trade_id", "status"],
    )
    op.create_index(
        "ix_source_file_mt_data_date",
        "source_files",
        ["modern_trade_id", "detected_data_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_file_mt_data_date", table_name="source_files")
    op.drop_index("ix_source_file_mt_status", table_name="source_files")
    op.drop_index("ix_source_files_status", table_name="source_files")
    op.drop_table("source_files")
    op.drop_index("uq_import_run_active_mt", table_name="import_runs")
    op.drop_index("ix_import_run_mt_requested", table_name="import_runs")
    op.drop_index("ix_import_runs_status", table_name="import_runs")
    op.drop_table("import_runs")
    op.drop_column("modern_trades", "schedule_time")
    op.drop_column("modern_trades", "schedule_enabled")
