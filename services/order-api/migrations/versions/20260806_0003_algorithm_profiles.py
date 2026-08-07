"""Add algorithm drill-down profiles.

Revision ID: 20260806_0003
Revises: 20260806_0002
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0003"
down_revision: str | None = "20260806_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order_decisions", sa.Column("algorithm_profile", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_decisions", "algorithm_profile")
