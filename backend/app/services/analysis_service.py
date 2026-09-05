from __future__ import annotations

import asyncio
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analysis.evidence_extractor import extract_evidence, extract_key_themes
from app.analysis.gap_detector import detect_candidate_gaps, detect_corpus_coherence
from app.analysis.llm_provider import LLMProviderError
from app.analysis.llm_service import LLM_PROMPT_VERSION, get_configured_provider, interpret_gaps
from app.analysis.models import (
    PaperEvidence,
    ResearchAnalysis,
    ResearchAnalysisPaper,
    ResearchGap,
    ResearchGapSupport,
)
from app.analysis.repository import AnalysisRepository
from app.analysis.schemas import AnalysisLimitations, AnalysisStatus, EvidenceItem
from app.models.paper import Paper
from app.models.user import User
from app.models.user_saved_paper import UserSavedPaper
from app.schemas.analysis_api import (
    AnalysisCreateRequest,
    AnalysisEvidenceResponse,
    AnalysisGapResponse,
    AnalysisPaperResponse,
    AnalysisResponse,
    CorpusCoherenceResponse,
    KeyThemeResponse,
    LLMInterpretationResponseView,
)


METHODOLOGY_VERSION = "5C-5E-deterministic-v1"


class AnalysisServiceError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def create_analysis(
    *,
    session: Session | None,
    user: User,
    request: AnalysisCreateRequest,
) -> AnalysisResponse:
    if session is None:
        raise AnalysisServiceError("Analysis persistence is unavailable.", status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        # Authentication performs a read on this request session first. Clear
        # that implicit transaction before opening the atomic write transaction.
        session.rollback()
        with session.begin():
            papers = _load_allowed_papers(session, user.id, request.paper_ids)
            repository = AnalysisRepository(session)
            analysis = repository.create_analysis(
                user_id=user.id,
                status=AnalysisStatus.RUNNING.value,
                methodology_version=METHODOLOGY_VERSION,
                research_question=request.research_question,
                framework=request.framework,
            )
            analysis_papers = {
                paper.id: repository.create_analysis_paper_snapshot(
                    analysis_id=analysis.id,
                    paper_id=paper.id,
                    input_order=index,
                    paper=paper,
                )
                for index, paper in enumerate(papers)
            }
            extracted = extract_evidence(papers)
            theme_summary = extract_key_themes(papers)
            gaps = detect_candidate_gaps(
                extracted,
                papers,
                research_question=request.research_question,
                methodology_version=METHODOLOGY_VERSION,
            )
            evidence_records: list[PaperEvidence] = []
            for item in extracted:
                record = repository.create_evidence(
                    analysis_paper_id=analysis_papers[item.paper_id].id,
                    item=item,
                    extraction_method=f"deterministic_rule:{item.evidence_status}",
                )
                evidence_records.append(record)
            for gap in gaps:
                if gap.confidence < request.options.minimum_confidence:
                    continue
                persisted_gap = gap.model_copy(update={"id": f"{analysis.id}-{gap.id}"})
                gap_record = repository.create_gap(analysis_id=analysis.id, gap=persisted_gap)
                _persist_gap_support(
                    repository,
                    analysis.id,
                    gap_record,
                    persisted_gap,
                    evidence_records,
                    analysis_papers,
                )
            if request.options.include_llm_interpretation:
                _attach_optional_interpretation(
                    analysis=analysis,
                    provider=get_configured_provider(),
                    evidence=extracted,
                    gaps=gaps,
                    paper_ids=request.paper_ids,
                )
            analysis.status = AnalysisStatus.COMPLETED.value
            session.flush()
            return _build_response(session, analysis.id, user.id)
    except AnalysisServiceError:
        session.rollback()
        raise
    except (SQLAlchemyError, ValueError, KeyError, RuntimeError) as error:
        session.rollback()
        raise AnalysisServiceError(
            "The analysis could not be completed.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from error


def get_analysis(*, session: Session | None, user: User, analysis_id: int) -> AnalysisResponse:
    return _get_response(session=session, user_id=user.id, analysis_id=analysis_id)


def get_analysis_evidence(
    *, session: Session | None, user: User, analysis_id: int
) -> list[AnalysisEvidenceResponse]:
    response = _get_response(session=session, user_id=user.id, analysis_id=analysis_id)
    return response.evidence


def get_analysis_gaps(
    *, session: Session | None, user: User, analysis_id: int
) -> list[AnalysisGapResponse]:
    response = _get_response(session=session, user_id=user.id, analysis_id=analysis_id)
    return response.candidate_gaps


def _load_allowed_papers(session: Session, user_id: int, paper_ids: Sequence[int]) -> list[Paper]:
    rows = session.scalars(
        select(Paper)
        .join(UserSavedPaper, UserSavedPaper.paper_id == Paper.id)
        .where(UserSavedPaper.user_id == user_id, Paper.id.in_(paper_ids))
    ).all()
    papers_by_id = {paper.id: paper for paper in rows}
    missing = [paper_id for paper_id in paper_ids if paper_id not in papers_by_id]
    if missing:
        raise AnalysisServiceError("One or more selected papers are unavailable.", status.HTTP_404_NOT_FOUND)
    return [papers_by_id[paper_id] for paper_id in paper_ids]


def _get_response(*, session: Session | None, user_id: int, analysis_id: int) -> AnalysisResponse:
    if session is None:
        raise AnalysisServiceError("Analysis persistence is unavailable.", status.HTTP_503_SERVICE_UNAVAILABLE)
    response = session.scalar(
        select(ResearchAnalysis).where(
            ResearchAnalysis.id == analysis_id,
            ResearchAnalysis.user_id == user_id,
        )
    )
    if response is None:
        raise AnalysisServiceError("Analysis not found.", status.HTTP_404_NOT_FOUND)
    return _build_response(session, analysis_id, user_id)


def _build_response(session: Session, analysis_id: int, user_id: int) -> AnalysisResponse:
    analysis = session.scalar(
        select(ResearchAnalysis).where(
            ResearchAnalysis.id == analysis_id,
            ResearchAnalysis.user_id == user_id,
        )
    )
    if analysis is None:
        raise AnalysisServiceError("Analysis not found.", status.HTTP_404_NOT_FOUND)
    analysis_papers = list(session.scalars(
        select(ResearchAnalysisPaper)
        .where(ResearchAnalysisPaper.analysis_id == analysis_id)
        .order_by(ResearchAnalysisPaper.input_order)
    ))
    verified_papers = {
        paper.id: paper
        for paper in session.scalars(select(Paper).where(Paper.id.in_([item.paper_id for item in analysis_papers])))
    }
    paper_ids = [item.paper_id for item in analysis_papers]
    evidence_records = list(session.scalars(
        select(PaperEvidence)
        .join(ResearchAnalysisPaper, ResearchAnalysisPaper.id == PaperEvidence.analysis_paper_id)
        .where(ResearchAnalysisPaper.analysis_id == analysis_id)
        .order_by(PaperEvidence.id)
    ))
    gaps = list(session.scalars(
        select(ResearchGap)
        .where(ResearchGap.analysis_id == analysis_id)
        .order_by(ResearchGap.id)
    ))
    evidence_payload = [
        AnalysisEvidenceResponse(
            id=item.id,
            paper_id=next(paper.paper_id for paper in analysis_papers if paper.id == item.analysis_paper_id),
            evidence_type=item.evidence_type,
            claim=item.claim_text,
            source_excerpt=item.source_excerpt,
            source_field=item.source_field,
            confidence=float(item.confidence),
            extraction_method=item.extraction_method,
            confidence_semantics="rule_match",
            evidence_status=item.extraction_method.split(":", 1)[1] if ":" in item.extraction_method else "research_element",
            interpretation=_interpretation_for_persisted_evidence(item),
        )
        for item in evidence_records
    ]
    papers_for_theme_extraction = [
        type("PaperSnapshot", (), {
            "id": paper.paper_id,
            "title": paper_snapshot.get("title") if isinstance((paper_snapshot := paper.paper_snapshot), dict) else None,
            "abstract": paper_snapshot.get("abstract") if isinstance(paper_snapshot, dict) else None,
        })()
        for paper in analysis_papers
    ]
    themes = extract_key_themes(papers_for_theme_extraction)
    evidence_model_items = [
        EvidenceItem(
            paper_id=item.paper_id,
            evidence_type=item.evidence_type,
            claim=item.claim,
            source_excerpt=item.source_excerpt,
            source_field=item.source_field,
            confidence=item.confidence,
        )
        for item in evidence_payload
    ]
    coherence = detect_corpus_coherence(evidence_model_items, papers_for_theme_extraction)
    limitations = ["Analysis is based on the selected corpus only."]
    if analysis.research_question:
        limitations.append(
            "The deterministic analysis preserves the research question but does not establish "
            "that the selected papers directly answer it; lexical overlap is not semantic relevance."
        )
    return AnalysisResponse(
        analysis_id=analysis.id,
        status=analysis.status,
        methodology_version=analysis.methodology_version,
        paper_count=len(paper_ids),
        paper_ids=paper_ids,
        papers=[
            AnalysisPaperResponse(
                paper_id=paper.paper_id,
                openalex_id=verified_papers[paper.paper_id].openalex_id,
                title=verified_papers[paper.paper_id].title,
                authors=verified_papers[paper.paper_id].authors,
                publication_year=verified_papers[paper.paper_id].publication_year,
                abstract=verified_papers[paper.paper_id].abstract,
                doi=verified_papers[paper.paper_id].doi,
                url=verified_papers[paper.paper_id].url,
            )
            for paper in analysis_papers
        ],
        research_question=analysis.research_question,
        evidence=evidence_payload,
        candidate_gaps=[
            AnalysisGapResponse(
                id=item.id,
                category=item.category,
                statement=item.statement,
                observed_evidence=item.observed_evidence,
               pattern=(
                   f"Multiple independent papers report the same issue: "
                   f"{item.observed_evidence[0]}"
                   if item.observed_evidence
                   else ""
               ),
               inference=item.inference,
               confidence=float(item.confidence),
               confidence_breakdown=_confidence_breakdown_for_gap(item),
               supporting_paper_ids=_supporting_paper_ids(session, item.id, analysis_id),
               limitations=AnalysisLimitations(items=limitations),
           )
           for item in gaps
        ],
        limitations=AnalysisLimitations(items=limitations),
        key_themes=[
            KeyThemeResponse(
                phrase=theme["phrase"],
                normalized_phrase=theme["normalized_phrase"],
                supporting_paper_ids=theme["supporting_paper_ids"],
                paper_count=theme["paper_count"],
                occurrence_count=theme["occurrence_count"],
                score=float(theme["score"]),
            )
            for theme in themes
        ],
        corpus_coherence=CorpusCoherenceResponse(
            status=str(coherence["status"]),
            summary=str(coherence["summary"]),
            dominant_cluster=coherence.get("dominant_cluster"),
        ),
        llm_interpretation=(
            LLMInterpretationResponseView.model_validate(analysis.llm_interpretation)
            if analysis.llm_interpretation
            else None
        ),
    )


def _attach_optional_interpretation(
    *,
    analysis: ResearchAnalysis,
    provider,
    evidence: Sequence[EvidenceItem],
    gaps,
    paper_ids: Sequence[int],
) -> None:
    metadata = {
        "status": "unavailable",
        "provider": getattr(provider, "provider_name", "unknown"),
        "model": getattr(provider, "model_name", "unknown"),
        "prompt_version": LLM_PROMPT_VERSION,
        "interpretations": [],
        "reason": "LLM provider not configured",
    }
    try:
        result = asyncio.run(
            interpret_gaps(
                provider=provider,
                evidence=evidence,
                gaps=gaps,
                paper_ids=paper_ids,
                methodology_version=METHODOLOGY_VERSION,
            )
        )
    except LLMProviderError as error:
        metadata["reason"] = str(error)
    else:
        metadata.update(
            {
                "status": "completed",
                "reason": None,
                "interpretations": [
                    interpretation.model_dump(mode="json")
                    for interpretation in result.interpretations
                ],
            }
        )
    analysis.model_provider = getattr(provider, "provider_name", None)
    analysis.model_name = getattr(provider, "model_name", None)
    analysis.prompt_version = LLM_PROMPT_VERSION
    analysis.llm_interpretation = metadata


def _persist_gap_support(repository, analysis_id, gap, candidate, evidence_records, analysis_papers):
    for paper_id in candidate.supporting_paper_ids:
        matching = next(
            (item for item in evidence_records
             if item.analysis_paper_id == analysis_papers[paper_id].id
             and item.claim_text in candidate.observed_evidence),
            None,
        )
        if matching:
            repository.create_gap_support(
                analysis_id=analysis_id,
                gap_id=gap.id,
                analysis_paper_id=analysis_papers[paper_id].id,
                evidence_id=matching.id,
                support_type="observed",
            )


def _confidence_breakdown_for_gap(gap: object) -> dict[str, float]:
    claim_text = " ".join(getattr(gap, "observed_evidence", []) or []).lower()
    explicit_markers = (
        "limitation",
        "future work",
        "validation",
        "generaliz",
        "sample size",
        "baseline",
        "conflict",
        "worse",
        "better",
        "insufficient",
    )
    specificity_markers = (
        "sample size",
        "generaliz",
        "validation",
        "baseline",
        "population",
        "patient",
        "student",
        "outcome",
        "reproduc",
        "real-world",
    )
    explicit_evidence = 1.0 if any(marker in claim_text for marker in explicit_markers) else 0.2
    specificity = 1.0 if any(marker in claim_text for marker in specificity_markers) else 0.4
    independent_papers = 1.0 if getattr(gap, "supporting_paper_count", 0) >= 2 else 0.5
    cross_paper_consistency = 1.0 if getattr(gap, "supporting_paper_count", 0) >= 2 else 0.5
    inference_penalty = 0.0 if explicit_evidence > 0.5 else 0.2
    corpus_size_penalty = 0.1 if getattr(gap, "supporting_paper_count", 0) < 3 else 0.0
    return {
        "explicit_evidence": round(explicit_evidence, 2),
        "independent_papers": round(independent_papers, 2),
        "cross_paper_consistency": round(cross_paper_consistency, 2),
        "specificity": round(specificity, 2),
        "inference_penalty": round(inference_penalty, 2),
        "corpus_size_penalty": round(corpus_size_penalty, 2),
    }


def _interpretation_for_persisted_evidence(item: PaperEvidence) -> str:
    status = item.extraction_method.split(":", 1)[1] if ":" in item.extraction_method else "research_element"
    if status == "finding":
        return "The abstract explicitly reports a result in this excerpt."
    if item.evidence_type == "outcome":
        return "The abstract mentions this outcome or metric, but the match alone does not report a result."
    if item.evidence_type == "future_work" and item.claim.startswith("Future-work target:"):
        target = item.claim.split(":", 1)[1].strip().rstrip(".")
        return f"The paper explicitly identifies {target} as a future research target."
    if status == "mention":
        return "The source mentions this concept without providing enough detail to establish a research finding."
    return "A research element was identified in the source excerpt; this is not by itself a research gap."


def _supporting_paper_ids(session: Session, gap_id: str, analysis_id: int) -> list[int]:
    rows = session.execute(
        select(ResearchAnalysisPaper.paper_id)
        .join(ResearchGapSupport, ResearchGapSupport.analysis_paper_id == ResearchAnalysisPaper.id)
        .where(
            ResearchGapSupport.gap_id == gap_id,
            ResearchGapSupport.analysis_id == analysis_id,
        )
        .order_by(ResearchAnalysisPaper.paper_id)
    )
    return sorted({row[0] for row in rows})
