from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchAnalysis(Base):
    __tablename__ = "research_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_research_analyses_status",
        ),
        CheckConstraint(
            "length(trim(methodology_version)) > 0",
            name="ck_research_analyses_methodology_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    research_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    framework: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(128), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_interpretation: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ResearchAnalysisPaper(Base):
    __tablename__ = "research_analysis_papers"
    __table_args__ = (
        UniqueConstraint("analysis_id", "paper_id", name="uq_analysis_papers_analysis_paper"),
        UniqueConstraint("analysis_id", "input_order", name="uq_analysis_papers_analysis_order"),
        UniqueConstraint("id", "analysis_id", name="uq_analysis_papers_id_analysis"),
        CheckConstraint("input_order >= 0", name="ck_analysis_papers_input_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("research_analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    input_order: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaperEvidence(Base):
    __tablename__ = "paper_evidence"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_paper_evidence_confidence"),
        UniqueConstraint("id", "analysis_paper_id", name="uq_paper_evidence_id_analysis_paper"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_paper_id: Mapped[int] = mapped_column(
        ForeignKey("research_analysis_papers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchGap(Base):
    __tablename__ = "research_gaps"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_research_gaps_confidence"),
        UniqueConstraint("id", "analysis_id", name="uq_research_gaps_id_analysis"),
        CheckConstraint("supporting_paper_count >= 0", name="ck_research_gaps_supporting_paper_count"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("research_analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    observed_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    inference: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supporting_paper_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchGapSupport(Base):
    __tablename__ = "research_gap_support"
    __table_args__ = (
        ForeignKeyConstraint(
            ["gap_id", "analysis_id"],
            ["research_gaps.id", "research_gaps.analysis_id"],
            name="fk_gap_support_gap_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["analysis_paper_id", "analysis_id"],
            ["research_analysis_papers.id", "research_analysis_papers.analysis_id"],
            name="fk_gap_support_paper_analysis",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "analysis_paper_id"],
            ["paper_evidence.id", "paper_evidence.analysis_paper_id"],
            name="fk_gap_support_evidence_paper",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    gap_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_paper_id: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_id: Mapped[int] = mapped_column(Integer, nullable=False)
    support_type: Mapped[str] = mapped_column(String(64), nullable=False)
