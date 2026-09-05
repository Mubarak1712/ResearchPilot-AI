import pytest
from pydantic import ValidationError

from app.analysis import (
    AnalysisLimitations,
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    CandidateResearchGap,
    EvidenceCategory,
    EvidenceItem,
    GapCategory,
)


def test_valid_analysis_request() -> None:
    request = AnalysisRequest(
        paper_ids=[1, 2],
        research_question="How do methods compare?",
        framework="PICOS",
        methodology_version="5B.1",
    )

    assert request.paper_ids == [1, 2]
    assert request.methodology_version == "5B.1"


def test_empty_paper_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(paper_ids=[], methodology_version="5B.1")


def test_duplicate_paper_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(paper_ids=[1, 1], methodology_version="5B.1")


def test_invalid_confidence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            paper_id=1,
            evidence_type=EvidenceCategory.ABSTRACT,
            claim="Observed claim",
            confidence=1.1,
        )


def test_valid_evidence_item() -> None:
    evidence = EvidenceItem(
        paper_id=1,
        evidence_type=EvidenceCategory.LIMITATION,
        claim="The study reports a small sample.",
        source_excerpt="The sample was limited to 20 participants.",
        source_field="abstract",
        confidence=0.8,
    )

    assert evidence.evidence_type is EvidenceCategory.LIMITATION


def test_invalid_evidence_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            paper_id=1,
            evidence_type="unsupported",
            claim="Observed claim",
            confidence=0.5,
        )


def test_valid_candidate_gap() -> None:
    gap = CandidateResearchGap(
        id="gap-1",
        category=GapCategory.REPLICATION,
        statement="Replication evidence is limited.",
        observed_evidence=["Only one selected paper evaluates replication."],
        pattern="Evidence appears in one paper.",
        inference="The selected corpus may lack replication studies.",
        confidence=0.7,
        supporting_paper_ids=[1],
    )

    assert gap.category is GapCategory.REPLICATION


def test_empty_candidate_gap_statement_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CandidateResearchGap(
            id="gap-1",
            category=GapCategory.OTHER,
            statement=" ",
            observed_evidence=["Observation"],
            pattern="Pattern",
            inference="Inference",
            confidence=0.5,
            supporting_paper_ids=[1],
        )


def test_invalid_gap_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CandidateResearchGap(
            id="gap-1",
            category="unsupported",
            statement="A candidate gap.",
            observed_evidence=["Observation"],
            pattern="Pattern",
            inference="Inference",
            confidence=0.5,
            supporting_paper_ids=[1],
        )


def test_supporting_papers_must_belong_to_analysis_input() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(
            analysis_id="analysis-1",
            status=AnalysisStatus.COMPLETED,
            methodology_version="5B.1",
            paper_count=1,
            paper_ids=[1],
            candidate_gaps=[
                CandidateResearchGap(
                    id="gap-1",
                    category=GapCategory.OTHER,
                    statement="A candidate gap.",
                    observed_evidence=["Observation"],
                    pattern="Pattern",
                    inference="Inference",
                    confidence=0.5,
                    supporting_paper_ids=[2],
                )
            ],
        )


def test_valid_completed_analysis_result() -> None:
    result = AnalysisResult(
        analysis_id="analysis-1",
        status=AnalysisStatus.COMPLETED,
        methodology_version="5B.1",
        paper_count=2,
        paper_ids=[1, 2],
        evidence=[
            EvidenceItem(
                paper_id=1,
                evidence_type=EvidenceCategory.TOPIC,
                claim="Topic is concentrated in one context.",
                confidence=0.6,
            )
        ],
    )

    assert result.status is AnalysisStatus.COMPLETED
    assert result.paper_count == 2


def test_analysis_limitations_are_preserved() -> None:
    limitations = AnalysisLimitations(items=["Abstract-only evidence", "Small corpus"])
    result = AnalysisResult(
        analysis_id="analysis-1",
        status=AnalysisStatus.COMPLETED,
        methodology_version="5B.1",
        paper_count=1,
        paper_ids=[1],
        limitations=limitations,
    )

    assert result.limitations.items == ["Abstract-only evidence", "Small corpus"]
