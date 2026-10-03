"""Add confirmed assortment memberships and versioned monthly forecast plans."""

import sqlalchemy as sa

from alembic import op

revision = "cd3748f901a2"
down_revision = "bc2637e8f901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assortment_bases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("attributes", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "assortment_members",
        sa.Column("wa_item_code", sa.String(50), primary_key=True),
        sa.Column("base_id", sa.String(36), sa.ForeignKey("assortment_bases.id"), nullable=False),
    )
    op.create_index("ix_assortment_members_base_id", "assortment_members", ["base_id"])
    op.create_table(
        "assortment_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("primary_year", sa.Integer(), unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("year BETWEEN 2000 AND 2100"),
    )
    op.create_table(
        "assortment_forecasts",
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("assortment_plans.id"), primary_key=True),
        sa.Column("base_id", sa.String(36), sa.ForeignKey("assortment_bases.id"), primary_key=True),
        sa.Column("mt_code", sa.String(10), primary_key=True),
        sa.Column("months", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("assortment_forecasts")
    op.drop_table("assortment_plans")
    op.drop_table("assortment_members")
    op.drop_table("assortment_bases")
