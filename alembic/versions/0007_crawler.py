"""crawler

Adds the background crawler's queue (`crawl_targets`) and its seed
searches (`crawl_seeds`).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawl_targets",
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("website", sa.Text(), nullable=False),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(), nullable=True),
        sa.Column("next_crawl_at", sa.DateTime(), nullable=False),
        sa.Column("emails_found", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("domain"),
    )
    op.create_index("ix_crawl_targets_next_crawl_at", "crawl_targets", ["next_crawl_at"])

    op.create_table(
        "crawl_seeds",
        sa.Column("query", sa.String(length=300), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("sites_found", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("query"),
    )


def downgrade() -> None:
    op.drop_table("crawl_seeds")
    op.drop_index("ix_crawl_targets_next_crawl_at", table_name="crawl_targets")
    op.drop_table("crawl_targets")
