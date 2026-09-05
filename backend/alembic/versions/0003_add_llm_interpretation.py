"""add optional LLM interpretation payload to analyses

Revision ID: 0003_add_llm_interpretation
Revises: 0002_research_analysis_persistence
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_llm_interpretation"
down_revision = '0002_analysis_persistence'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("research_analyses", sa.Column("llm_interpretation", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("research_analyses", "llm_interpretation")
