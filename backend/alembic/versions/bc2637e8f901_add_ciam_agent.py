"""Durable outbound CIAM agent state and command journal."""

import sqlalchemy as sa

from alembic import op

revision = "bc2637e8f901"
down_revision = "ab1526d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ciam_agent_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "ciam_agent_commands",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("command_id", sa.String(200), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_ciam_agent_commands_scope", "ciam_agent_commands", ["scope"])
    op.create_index("ix_ciam_agent_commands_username", "ciam_agent_commands", ["username"])


def downgrade():
    op.drop_table("ciam_agent_commands")
    op.drop_table("ciam_agent_state")
