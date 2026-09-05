"""Add explicit saved state to papers.

Revision ID: 20260821_0002
Revises: 20260818_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0002"
down_revision = "20260818_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "papers",
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("papers", "is_saved", server_default=sa.false())


def downgrade() -> None:
    op.drop_column("papers", "is_saved")
