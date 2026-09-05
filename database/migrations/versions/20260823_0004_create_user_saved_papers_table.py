"""Create user saved papers table.

Revision ID: 20260823_0004
Revises: 20260823_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0004"
down_revision = "20260823_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_saved_papers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_saved_papers_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"], ["papers.id"], name="fk_user_saved_papers_paper_id_papers", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "paper_id", name="uq_user_saved_papers_user_paper"),
    )
    op.create_index("ix_user_saved_papers_user_id", "user_saved_papers", ["user_id"])
    op.create_index("ix_user_saved_papers_paper_id", "user_saved_papers", ["paper_id"])


def downgrade() -> None:
    op.drop_index("ix_user_saved_papers_paper_id", table_name="user_saved_papers")
    op.drop_index("ix_user_saved_papers_user_id", table_name="user_saved_papers")
    op.drop_table("user_saved_papers")
