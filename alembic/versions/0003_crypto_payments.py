"""crypto payments

Payment orders for plans paid in BTC, USDT (TRC-20) or TRX and confirmed by
an admin, plus the end of each subscription's paid period.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A database adopted from before migrations may have had its missing
    # `subscriptions` table created from the current models, which already
    # include this column (see app/database/migrations.py).
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("subscriptions")}
    if "paid_until" not in columns:
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.add_column(sa.Column("paid_until", sa.DateTime(), nullable=True))

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("credits_per_month", sa.Integer(), nullable=False),
        sa.Column("billing_period", sa.String(length=10), nullable=False),
        sa.Column("amount_usd_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=20), nullable=False),
        sa.Column("pay_address", sa.String(length=120), nullable=False),
        sa.Column("amount_crypto", sa.String(length=40), nullable=False),
        sa.Column("usd_rate", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("tx_hash", sa.String(length=100), nullable=True),
        sa.Column("admin_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_payment_orders_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"], ["users.id"], name="fk_payment_orders_reviewed_by_id_users"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash", name="uq_payment_orders_tx_hash"),
    )
    with op.batch_alter_table("payment_orders") as batch_op:
        batch_op.create_index("ix_payment_orders_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_payment_orders_status", ["status"], unique=False)
        batch_op.create_index("ix_payment_orders_created_at", ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("payment_orders") as batch_op:
        batch_op.drop_index("ix_payment_orders_created_at")
        batch_op.drop_index("ix_payment_orders_status")
        batch_op.drop_index("ix_payment_orders_user_id")
    op.drop_table("payment_orders")

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("paid_until")
