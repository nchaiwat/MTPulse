"""add manual upload batch staging contracts

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manual_upload_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_mode", sa.String(length=16), nullable=False),
        sa.Column("detected_source_group", sa.String(length=30), nullable=True),
        sa.Column(
            "detection_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("needs_review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("summary_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_manual_upload_batch_status_activity",
        "manual_upload_batches",
        ["status", "last_activity_at"],
    )
    op.create_index(
        "ix_manual_upload_batch_expiry",
        "manual_upload_batches",
        ["expires_at"],
    )
    op.create_table(
        "manual_upload_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("staging_key", sa.String(length=255), nullable=True),
        sa.Column("relative_depth", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("detected_mt_code", sa.String(length=20), nullable=True),
        sa.Column("detected_source_group", sa.String(length=30), nullable=True),
        sa.Column("source_kind", sa.String(length=20), nullable=True),
        sa.Column("data_date", sa.Date(), nullable=True),
        sa.Column("business_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "detection_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "validation_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("source_file_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["upload_batch_id"], ["manual_upload_batches.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "upload_batch_id",
            "idempotency_key",
            name="uq_manual_upload_file_batch_idempotency",
        ),
    )
    op.create_index(
        "ix_manual_upload_file_batch_status",
        "manual_upload_files",
        ["upload_batch_id", "status"],
    )
    op.create_index(
        "ix_manual_upload_file_mt_status",
        "manual_upload_files",
        ["detected_mt_code", "status"],
    )
    op.create_index(
        "ix_manual_upload_file_expiry",
        "manual_upload_files",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_manual_upload_file_expiry", table_name="manual_upload_files")
    op.drop_index("ix_manual_upload_file_mt_status", table_name="manual_upload_files")
    op.drop_index("ix_manual_upload_file_batch_status", table_name="manual_upload_files")
    op.drop_table("manual_upload_files")
    op.drop_index("ix_manual_upload_batch_expiry", table_name="manual_upload_batches")
    op.drop_index(
        "ix_manual_upload_batch_status_activity",
        table_name="manual_upload_batches",
    )
    op.drop_table("manual_upload_batches")
