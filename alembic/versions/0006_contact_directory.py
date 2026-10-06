"""contact directory

Adds the shared contact directory: `contact_records` (every business
address discovery has found), `email_domains` (each mail domain's learned
address format and catch-all status), and `suppressed_emails` (the opt-out
list).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("name_key", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("times_seen", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_records_email", "contact_records", ["email"], unique=True)
    op.create_index("ix_contact_records_domain", "contact_records", ["domain"])
    op.create_index("ix_contact_records_name_key", "contact_records", ["name_key"])

    op.create_table(
        "email_domains",
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("pattern_counts", sa.JSON(), nullable=True),
        sa.Column("is_catch_all", sa.Boolean(), nullable=True),
        sa.Column("catch_all_checked_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("domain"),
    )

    op.create_table(
        "suppressed_emails",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suppressed_emails_email", "suppressed_emails", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_suppressed_emails_email", table_name="suppressed_emails")
    op.drop_table("suppressed_emails")
    op.drop_table("email_domains")
    op.drop_index("ix_contact_records_name_key", table_name="contact_records")
    op.drop_index("ix_contact_records_domain", table_name="contact_records")
    op.drop_index("ix_contact_records_email", table_name="contact_records")
    op.drop_table("contact_records")
