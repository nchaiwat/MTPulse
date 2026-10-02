"""Add structured authentication transaction logs; preserve legacy audit history."""

import sqlalchemy as sa

from alembic import op

revision = "ab1526d7e8f9"
down_revision = "9da415c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transaction_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("triggered_by", sa.String(220), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_transaction_logs_category", "transaction_logs", ["category"])
    op.create_index("ix_transaction_logs_created_at", "transaction_logs", ["created_at"])


def downgrade():
    op.drop_index("ix_transaction_logs_created_at", table_name="transaction_logs")
    op.drop_index("ix_transaction_logs_category", table_name="transaction_logs")
    op.drop_table("transaction_logs")
