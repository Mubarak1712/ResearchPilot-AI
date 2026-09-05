"""create research gap analysis persistence tables

Revision ID: 0002_research_analysis_persistence
Revises: 0001_add_auth_tokens
"""

from alembic import op
import sqlalchemy as sa


revision = '0002_analysis_persistence'
down_revision = "0001_add_auth_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("research_question", sa.Text()),
        sa.Column("framework", sa.Text()),
        sa.Column("methodology_version", sa.String(128), nullable=False),
        sa.Column("model_provider", sa.String(128)),
        sa.Column("model_name", sa.String(128)),
        sa.Column("prompt_version", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(128)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_research_analyses_status",
        ),
        sa.CheckConstraint(
            "length(trim(methodology_version)) > 0",
            name="ck_research_analyses_methodology_version",
        ),
    )
    op.create_index("ix_research_analyses_user_id", "research_analyses", ["user_id"])

    op.create_table(
        "research_analysis_papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("research_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("input_order", sa.Integer(), nullable=False),
        sa.Column("paper_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("analysis_id", "paper_id", name="uq_analysis_papers_analysis_paper"),
        sa.UniqueConstraint("analysis_id", "input_order", name="uq_analysis_papers_analysis_order"),
        sa.UniqueConstraint("id", "analysis_id", name="uq_analysis_papers_id_analysis"),
        sa.CheckConstraint("input_order >= 0", name="ck_analysis_papers_input_order"),
    )
    op.create_index("ix_research_analysis_papers_analysis_id", "research_analysis_papers", ["analysis_id"])
    op.create_index("ix_research_analysis_papers_paper_id", "research_analysis_papers", ["paper_id"])

    op.create_table(
        "paper_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_paper_id", sa.Integer(), sa.ForeignKey("research_analysis_papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text()),
        sa.Column("source_field", sa.String(128)),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_paper_evidence_confidence"),
        sa.UniqueConstraint("id", "analysis_paper_id", name="uq_paper_evidence_id_analysis_paper"),
    )
    op.create_index("ix_paper_evidence_analysis_paper_id", "paper_evidence", ["analysis_paper_id"])

    op.create_table(
        "research_gaps",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("research_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("observed_evidence", sa.JSON(), nullable=False),
        sa.Column("inference", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("priority", sa.Integer()),
        sa.Column("supporting_paper_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_research_gaps_confidence"),
        sa.UniqueConstraint("id", "analysis_id", name="uq_research_gaps_id_analysis"),
        sa.CheckConstraint("supporting_paper_count >= 0", name="ck_research_gaps_supporting_paper_count"),
    )
    op.create_index("ix_research_gaps_analysis_id", "research_gaps", ["analysis_id"])

    op.create_table(
        "research_gap_support",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("gap_id", sa.String(128), nullable=False),
        sa.Column("analysis_paper_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("support_type", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["gap_id", "analysis_id"],
            ["research_gaps.id", "research_gaps.analysis_id"],
            name="fk_gap_support_gap_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_paper_id", "analysis_id"],
            ["research_analysis_papers.id", "research_analysis_papers.analysis_id"],
            name="fk_gap_support_paper_analysis",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "analysis_paper_id"],
            ["paper_evidence.id", "paper_evidence.analysis_paper_id"],
            name="fk_gap_support_evidence_paper",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_research_gap_support_gap_id", "research_gap_support", ["gap_id"])


def downgrade():
    op.drop_index("ix_research_gap_support_gap_id", table_name="research_gap_support")
    op.drop_table("research_gap_support")
    op.drop_index("ix_research_gaps_analysis_id", table_name="research_gaps")
    op.drop_table("research_gaps")
    op.drop_index("ix_paper_evidence_analysis_paper_id", table_name="paper_evidence")
    op.drop_table("paper_evidence")
    op.drop_index("ix_research_analysis_papers_paper_id", table_name="research_analysis_papers")
    op.drop_index("ix_research_analysis_papers_analysis_id", table_name="research_analysis_papers")
    op.drop_table("research_analysis_papers")
    op.drop_index("ix_research_analyses_user_id", table_name="research_analyses")
    op.drop_table("research_analyses")
