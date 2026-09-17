"""token version

Adds `users.token_version`, the counter every session token is stamped with.
Bumping a user's counter invalidates every token issued before it, which is
what makes password changes and "sign out other devices" actually end a
session instead of waiting a week for it to expire.

Existing rows start at 0. Tokens minted before this change carry no version
at all and are refused outright, so everyone signs in once after deploying.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default lets this be NOT NULL immediately: existing rows take 0.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("token_version")
