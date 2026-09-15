"""account ownership

Every saved company, search and scheduled search now belongs to one account,
and each account only sees its own. Records that already exist are assigned
to the earliest admin account — or, when there's no admin, the earliest
account.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED_TABLES = ("companies", "search_queries", "saved_searches")


def upgrade() -> None:
    # Added as nullable first, so existing rows can be assigned an owner
    # before the column becomes required.
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("owner_id", sa.String(length=36), nullable=True))

    conn = op.get_bind()
    has_records = any(
        conn.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() for table in OWNED_TABLES
    )
    if has_records:
        owner_id = conn.execute(
            sa.text("SELECT id FROM users ORDER BY is_admin DESC, created_at ASC LIMIT 1")
        ).scalar()
        if owner_id is None:
            raise RuntimeError(
                "This database has saved companies or searches but no user accounts to "
                "assign them to. Create an account in this database first, then run the "
                "migration again."
            )
        for table in OWNED_TABLES:
            conn.execute(
                sa.text(f"UPDATE {table} SET owner_id = :owner_id WHERE owner_id IS NULL"),
                {"owner_id": owner_id},
            )

    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("owner_id", existing_type=sa.String(length=36), nullable=False)
            batch_op.create_index(f"ix_{table}_owner_id", ["owner_id"], unique=False)
            batch_op.create_foreign_key(
                f"fk_{table}_owner_id_users", "users", ["owner_id"], ["id"]
            )


def downgrade() -> None:
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_owner_id_users", type_="foreignkey")
            batch_op.drop_index(f"ix_{table}_owner_id")
            batch_op.drop_column("owner_id")
