"""Add explicit AD username bindings to CIAM accounts."""

import sqlalchemy as sa

from alembic import op

revision = "9da415c6d7e8"
down_revision = "8c9304b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_users", sa.Column("ad_username", sa.String(200), nullable=True))
    op.create_index("ix_auth_users_ad_username", "auth_users", ["ad_username"], unique=True)


def downgrade():
    op.drop_index("ix_auth_users_ad_username", table_name="auth_users")
    op.drop_column("auth_users", "ad_username")
