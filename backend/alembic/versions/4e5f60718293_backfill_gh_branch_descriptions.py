"""backfill Global House branch descriptions from the verified manual workbook

Revision ID: 4e5f60718293
Revises: 3d4e5f607182
Create Date: 2026-09-14
"""

# ruff: noqa: E501 -- Unicode escapes keep Thai data stable through Windows tooling.

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4e5f60718293"
down_revision: str | Sequence[str] | None = "3d4e5f607182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "migration:KPI - GBH 2026.xlsx:branch-descriptions"
BRANCH_DESCRIPTIONS = (
    ("GH-101", "\u0e2a\u0e33\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19\u0e43\u0e2b\u0e0d\u0e48"),
    ("GH-102", "\u0e2a\u0e32\u0e02\u0e32\u0e02\u0e2d\u0e19\u0e41\u0e01\u0e48\u0e19"),
    ("GH-103", "\u0e2a\u0e32\u0e02\u0e32\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35"),
    ("GH-104", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e27\u0e35\u0e22\u0e07\u0e01\u0e38\u0e21\u0e01\u0e32\u0e21"),
    ("GH-105", "\u0e2a\u0e32\u0e02\u0e32\u0e23\u0e30\u0e22\u0e2d\u0e07"),
    ("GH-106", "\u0e2a\u0e32\u0e02\u0e32\u0e0a\u0e25\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-107", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e1b\u0e10\u0e21"),
    ("GH-108", "\u0e2a\u0e32\u0e02\u0e32\u0e23\u0e32\u0e0a\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-109", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e32\u0e2c\u0e2a\u0e34\u0e19\u0e18\u0e38\u0e4c"),
    ("GH-110", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e2a\u0e27\u0e23\u0e23\u0e04\u0e4c"),
    ("GH-112", "\u0e2a\u0e32\u0e02\u0e32\u0e21\u0e2b\u0e32\u0e2a\u0e32\u0e23\u0e04\u0e32\u0e21"),
    ("GH-113", "\u0e2a\u0e32\u0e02\u0e32\u0e1a\u0e49\u0e32\u0e19\u0e44\u0e1c\u0e48"),
    ("GH-114", "\u0e2a\u0e32\u0e02\u0e32\u0e2b\u0e19\u0e2d\u0e07\u0e04\u0e32\u0e22"),
    ("GH-115", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e23\u0e32\u0e0a\u0e2a\u0e35\u0e21\u0e32"),
    ("GH-116", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e01\u0e25\u0e19\u0e04\u0e23"),
    ("GH-117", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e1e\u0e19\u0e21"),
    ("GH-118", "\u0e2a\u0e32\u0e02\u0e32\u0e0a\u0e31\u0e22\u0e20\u0e39\u0e21\u0e34"),
    ("GH-119", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e38\u0e23\u0e34\u0e19\u0e17\u0e23\u0e4c"),
    ("GH-120", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e34\u0e29\u0e13\u0e38\u0e42\u0e25\u0e01"),
    ("GH-121", "\u0e2a\u0e32\u0e02\u0e32\u0e25\u0e33\u0e1e\u0e39\u0e19"),
    ("GH-122", "\u0e2a\u0e32\u0e02\u0e32\u0e21\u0e38\u0e01\u0e14\u0e32\u0e2b\u0e32\u0e23"),
    ("GH-123", "\u0e2a\u0e32\u0e02\u0e32\u0e1b\u0e23\u0e30\u0e08\u0e27\u0e1a\u0e04\u0e35\u0e23\u0e35\u0e02\u0e31\u0e19\u0e18\u0e4c"),
    ("GH-124", "\u0e2a\u0e32\u0e02\u0e32\u0e25\u0e33\u0e1b\u0e32\u0e07"),
    ("GH-125", "\u0e2a\u0e32\u0e02\u0e32\u0e41\u0e1e\u0e23\u0e48"),
    ("GH-126", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e48\u0e32\u0e19"),
    ("GH-127", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e23\u0e32\u0e22"),
    ("GH-128", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e38\u0e42\u0e02\u0e17\u0e31\u0e22"),
    ("GH-129", "\u0e2a\u0e32\u0e02\u0e32\u0e2d\u0e38\u0e1a\u0e25\u0e23\u0e32\u0e0a\u0e18\u0e32\u0e19\u0e35"),
    ("GH-130", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e33\u0e41\u0e1e\u0e07\u0e40\u0e1e\u0e0a\u0e23"),
    ("GH-131", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e1e\u0e0a\u0e23\u0e1a\u0e39\u0e23\u0e13\u0e4c"),
    ("GH-132", "\u0e2a\u0e32\u0e02\u0e32\u0e25\u0e1e\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-135", "\u0e2a\u0e32\u0e02\u0e32\u0e08\u0e31\u0e19\u0e17\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-136", "\u0e2a\u0e32\u0e02\u0e32\u0e15\u0e23\u0e32\u0e14"),
    ("GH-137", "\u0e2a\u0e32\u0e02\u0e32\u0e1a\u0e49\u0e32\u0e19\u0e15\u0e32\u0e14"),
    ("GH-138", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e30\u0e40\u0e22\u0e32"),
    ("GH-139", "\u0e2a\u0e32\u0e02\u0e32\u0e1a\u0e38\u0e23\u0e35\u0e23\u0e31\u0e21\u0e22\u0e4c"),
    ("GH-140", "\u0e2a\u0e32\u0e02\u0e32\u0e1b\u0e23\u0e32\u0e13\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-141", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e17\u0e1e\u0e32\u0e23\u0e31\u0e01\u0e29\u0e4c"),
    ("GH-142", "\u0e2a\u0e32\u0e02\u0e32\u0e2b\u0e19\u0e2d\u0e07\u0e1a\u0e31\u0e27\u0e25\u0e33\u0e20\u0e39"),
    ("GH-144", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e21\u0e38\u0e17\u0e23\u0e2a\u0e07\u0e04\u0e23\u0e32\u0e21"),
    ("GH-145", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e23\u0e30\u0e19\u0e04\u0e23\u0e28\u0e23\u0e35\u0e2d\u0e22\u0e38\u0e18\u0e22\u0e32"),
    ("GH-146", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e19\u0e32\u0e22\u0e01"),
    ("GH-150", "\u0e2a\u0e32\u0e02\u0e32\u0e1b\u0e17\u0e38\u0e21\u0e18\u0e32\u0e19\u0e351"),
    ("GH-151", "\u0e2a\u0e32\u0e02\u0e32\u0e28\u0e32\u0e25\u0e32\u0e22\u0e32"),
    ("GH-152", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e04\u0e23\u0e28\u0e23\u0e35\u0e18\u0e23\u0e23\u0e21\u0e23\u0e32\u0e0a"),
    ("GH-153", "\u0e2a\u0e32\u0e02\u0e32\u0e1a\u0e36\u0e07\u0e01\u0e32\u0e2c"),
    ("GH-154", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e38\u0e23\u0e32\u0e29\u0e0e\u0e23\u0e4c\u0e18\u0e32\u0e19\u0e35"),
    ("GH-155", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e32\u0e0d\u0e08\u0e19\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-156", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e34\u0e07\u0e2b\u0e4c\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-158", "\u0e2a\u0e32\u0e02\u0e32\u0e22\u0e42\u0e2a\u0e18\u0e23"),
    ("GH-159", "\u0e2a\u0e32\u0e02\u0e32\u0e2d\u0e48\u0e32\u0e07\u0e17\u0e2d\u0e07"),
    ("GH-160", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e25\u0e22"),
    ("GH-161", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e31\u0e17\u0e25\u0e38\u0e07"),
    ("GH-162", "\u0e2a\u0e32\u0e02\u0e32\u0e2d\u0e38\u0e15\u0e23\u0e14\u0e34\u0e15\u0e16\u0e4c"),
    ("GH-163", "\u0e2a\u0e32\u0e02\u0e32\u0e0a\u0e38\u0e21\u0e41\u0e1e"),
    ("GH-164", "\u0e2a\u0e32\u0e02\u0e32\u0e20\u0e39\u0e40\u0e01\u0e47\u0e15"),
    ("GH-166", "\u0e2a\u0e32\u0e02\u0e32\u0e41\u0e21\u0e48\u0e2a\u0e32\u0e22"),
    ("GH-168", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e31\u0e07\u0e42\u0e04\u0e19"),
    ("GH-169", "\u0e2a\u0e32\u0e02\u0e32\u0e41\u0e21\u0e48\u0e2e\u0e48\u0e2d\u0e07\u0e2a\u0e2d\u0e19"),
    ("GH-171", "\u0e2a\u0e32\u0e02\u0e32\u0e42\u0e0a\u0e04\u0e0a\u0e31\u0e22"),
    ("GH-172", "\u0e2a\u0e32\u0e02\u0e32\u0e0a\u0e31\u0e22\u0e19\u0e32\u0e17"),
    ("GH-173", "\u0e2a\u0e32\u0e02\u0e32\u0e1d\u0e32\u0e07"),
    ("GH-174", "\u0e2a\u0e32\u0e02\u0e32\u0e14\u0e48\u0e32\u0e19\u0e02\u0e38\u0e19\u0e17\u0e14"),
    ("GH-175", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e15\u0e39\u0e25"),
    ("GH-176", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e14\u0e0a\u0e2d\u0e38\u0e14\u0e21"),
    ("GH-177", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e31\u0e19\u0e17\u0e23\u0e25\u0e31\u0e01\u0e29\u0e4c"),
    ("GH-178", "\u0e2a\u0e32\u0e02\u0e32\u0e19\u0e32\u0e07\u0e23\u0e2d\u0e07"),
    ("GH-179", "\u0e2a\u0e32\u0e02\u0e32\u0e44\u0e17\u0e23\u0e19\u0e49\u0e2d\u0e22"),
    ("GH-182", "\u0e2a\u0e32\u0e02\u0e32\u0e2b\u0e19\u0e2d\u0e07\u0e2b\u0e32\u0e19"),
    ("GH-183", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e23\u0e30\u0e17\u0e38\u0e48\u0e21\u0e41\u0e1a\u0e19"),
    ("GH-184", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e22\u0e31\u0e04\u0e06\u0e20\u0e39\u0e21\u0e34\u0e1e\u0e34\u0e2a\u0e31\u0e22"),
    ("GH-185", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e1a\u0e34\u0e19\u0e17\u0e23\u0e4c\u0e1a\u0e38\u0e23\u0e35"),
    ("GH-186", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e38\u0e09\u0e34\u0e19\u0e32\u0e23\u0e32\u0e22\u0e13\u0e4c"),
    ("GH-187", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e21\u0e38\u0e22"),
    ("GH-188", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e32\u0e19"),
    ("GH-189", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e27\u0e35\u0e22\u0e07\u0e1b\u0e48\u0e32\u0e40\u0e1b\u0e49\u0e32"),
    ("GH-192", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e34\u0e08\u0e34\u0e15\u0e23"),
    ("GH-193", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e23\u0e40\u0e08\u0e23\u0e34\u0e0d"),
    ("GH-194", "\u0e2a\u0e32\u0e02\u0e32\u0e23\u0e30\u0e19\u0e2d\u0e07"),
    ("GH-195", "\u0e2a\u0e32\u0e02\u0e32\u0e42\u0e1e\u0e19\u0e17\u0e2d\u0e07"),
    ("GH-197", "\u0e2a\u0e32\u0e02\u0e32\u0e40\u0e25\u0e34\u0e07\u0e19\u0e01\u0e17\u0e32"),
    ("GH-200", "\u0e2a\u0e32\u0e02\u0e32\u0e0a\u0e38\u0e21\u0e1e\u0e23"),
    ("GH-201", "\u0e2a\u0e32\u0e02\u0e32\u0e1e\u0e34\u0e21\u0e32\u0e22"),
    ("GH-203", "\u0e2a\u0e32\u0e02\u0e32\u0e01\u0e23\u0e30\u0e19\u0e27\u0e19"),
    ("GH-206", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e27\u0e48\u0e32\u0e07\u0e41\u0e14\u0e19\u0e14\u0e34\u0e19"),
    ("GH-207", "\u0e2a\u0e32\u0e02\u0e32\u0e25\u0e33\u0e1b\u0e25\u0e32\u0e22\u0e21\u0e32\u0e28"),
    ("GH-209", "\u0e2a\u0e32\u0e02\u0e32\u0e2a\u0e27\u0e23\u0e23\u0e04\u0e42\u0e25\u0e01"),
    ("GH-214", "\u0e2a\u0e32\u0e02\u0e32\u0e41\u0e21\u0e48\u0e2a\u0e2d\u0e14"),
    ("GH-300", "New Store1"),
    ("GH-301", "New Store2"),
    ("GH-302", "New Store3"),
)


def upgrade() -> None:
    connection = op.get_bind()
    modern_trade_id = connection.execute(
        sa.text("SELECT id FROM modern_trades WHERE code = :code"),
        {"code": "GH"},
    ).scalar_one_or_none()
    if modern_trade_id is None:
        return

    for source_code, source_description in BRANCH_DESCRIPTIONS:
        result = connection.execute(
            sa.text(
                """
                UPDATE branch_mappings
                SET source_branch_description = :source_description,
                    changed_by = :actor,
                    changed_at = CURRENT_TIMESTAMP
                WHERE modern_trade_id = :modern_trade_id
                  AND source_branch_code = :source_code
                  AND (
                      source_branch_description IS NULL
                      OR TRIM(source_branch_description) = ''
                  )
                """
            ),
            {
                "source_description": source_description,
                "actor": SOURCE,
                "modern_trade_id": modern_trade_id,
                "source_code": source_code,
            },
        )
        if result.rowcount:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO audit_events (
                        entity_type, entity_id, action, actor,
                        before_json, after_json
                    )
                    VALUES (
                        'branch_mapping', :entity_id,
                        'backfill_source_branch_description', :actor,
                        :before_json, :after_json
                    )
                    """
                ),
                {
                    "entity_id": source_code,
                    "actor": SOURCE,
                    "before_json": json.dumps(
                        {"source_branch_description": None},
                        ensure_ascii=False,
                    ),
                    "after_json": json.dumps(
                        {"source_branch_description": source_description},
                        ensure_ascii=False,
                    ),
                },
            )


def downgrade() -> None:
    # Keep verified descriptions: removing production mapping data on downgrade
    # would be more destructive than leaving this data-only repair in place.
    pass
