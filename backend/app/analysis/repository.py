from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.models import (
    PaperEvidence,
    ResearchAnalysis,
    ResearchAnalysisPaper,
    ResearchGap,
    ResearchGapSupport,
)
from app.analysis.schemas import CandidateResearchGap, EvidenceItem


def paper_snapshot(paper: object) -> dict:
    """Build a stable snapshot from supported Paper fields, never serializing the ORM object."""
    return {
        "openalex_id": getattr(paper, "openalex_id", None),
        "title": getattr(paper, "title", None),
        "authors": list(getattr(paper, "authors", None) or []),
        "publication_year": getattr(paper, "publication_year", None),
        "publication_date": getattr(paper, "publication_date", None),
        "abstract": getattr(paper, "abstract", None),
        "doi": getattr(paper, "doi", None),
        "url": getattr(paper, "url", None),
        "citation_count": getattr(paper, "citation_count", None),
        "source_name": getattr(paper, "source_name", None),
    }


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_analysis(
        self,
        *,
        user_id: int,
        status: str,
        methodology_version: str,
        research_question: str | None = None,
        framework: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        prompt_version: str | None = None,
        completed_at: datetime | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ResearchAnalysis:
        analysis = ResearchAnalysis(
            user_id=user_id,
            status=status,
            methodology_version=methodology_version.strip(),
            research_question=research_question,
            framework=framework,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            completed_at=completed_at,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(analysis)
        self.session.flush()
        return analysis

    def get_analysis(self, *, analysis_id: int, user_id: int) -> ResearchAnalysis | None:
        return self.session.scalar(
            select(ResearchAnalysis).where(
                ResearchAnalysis.id == analysis_id,
                ResearchAnalysis.user_id == user_id,
            )
        )

    def create_analysis_paper_snapshot(
        self, *, analysis_id: int, paper_id: int, input_order: int, paper: object
    ) -> ResearchAnalysisPaper:
        record = ResearchAnalysisPaper(
            analysis_id=analysis_id,
            paper_id=paper_id,
            input_order=input_order,
            paper_snapshot=paper_snapshot(paper),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_evidence(
        self,
        *,
        analysis_paper_id: int,
        item: EvidenceItem,
        extraction_method: str = "deterministic_rule",
    ) -> PaperEvidence:
        record = PaperEvidence(
            analysis_paper_id=analysis_paper_id,
            evidence_type=item.evidence_type.value,
            claim_text=item.claim,
            source_excerpt=item.source_excerpt,
            source_field=item.source_field,
            confidence=item.confidence,
            extraction_method=extraction_method,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_gap(
        self, *, analysis_id: int, gap: CandidateResearchGap, priority: int | None = None
    ) -> ResearchGap:
        record = ResearchGap(
            id=gap.id,
            analysis_id=analysis_id,
            category=gap.category.value,
            statement=gap.statement,
            observed_evidence=gap.observed_evidence,
            inference=gap.inference,
            confidence=gap.confidence,
            priority=priority,
            supporting_paper_count=len(gap.supporting_paper_ids),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_gap_support(
        self,
        *,
        analysis_id: int,
        gap_id: str,
        analysis_paper_id: int,
        evidence_id: int,
        support_type: str,
    ) -> ResearchGapSupport:
        record = ResearchGapSupport(
            analysis_id=analysis_id,
            gap_id=gap_id,
            analysis_paper_id=analysis_paper_id,
            evidence_id=evidence_id,
            support_type=support_type,
        )
        self.session.add(record)
        self.session.flush()
        return record
