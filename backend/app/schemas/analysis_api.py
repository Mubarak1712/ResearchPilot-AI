from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.analysis.llm_schemas import LLMGapInterpretation
from app.analysis.schemas import AnalysisLimitations, AnalysisStatus, EvidenceCategory, GapCategory


MAX_ANALYSIS_PAPERS = 20


class AnalysisOptions(BaseModel):
    include_llm_interpretation: bool = False
    minimum_confidence: float = Field(default=0, ge=0, le=1)

    @field_validator("include_llm_interpretation")
    @classmethod
    def reject_llm(cls, value: bool) -> bool:
        return value


class AnalysisCreateRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=MAX_ANALYSIS_PAPERS)
    research_question: str | None = None
    framework: str | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @field_validator("paper_ids")
    @classmethod
    def validate_paper_ids(cls, value: list[int]) -> list[int]:
        if any(paper_id <= 0 for paper_id in value):
            raise ValueError("paper_ids must contain positive IDs")
        if len(value) != len(set(value)):
            raise ValueError("paper_ids must not contain duplicates")
        return value

    @field_validator("research_question", "framework")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AnalysisEvidenceResponse(BaseModel):
    id: int
    paper_id: int
    evidence_type: EvidenceCategory
    claim: str
    source_excerpt: str | None
    source_field: str | None
    confidence: float
    extraction_method: str
    confidence_semantics: str = "rule_match"
    evidence_status: str = "research_element"
    interpretation: str = "A research element was identified in the source excerpt."


class AnalysisPaperResponse(BaseModel):
    paper_id: int
    openalex_id: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None


class AnalysisGapResponse(BaseModel):
    id: str
    category: GapCategory
    statement: str
    observed_evidence: list[str]
    pattern: str = ""
    inference: str
    confidence: float
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)
    supporting_paper_ids: list[int]
    limitations: AnalysisLimitations


class KeyThemeResponse(BaseModel):
    phrase: str
    normalized_phrase: str
    supporting_paper_ids: list[int]
    paper_count: int = Field(ge=1)
    occurrence_count: int = Field(ge=1)
    score: float = Field(ge=0)


class CorpusCoherenceResponse(BaseModel):
    status: str
    summary: str
    dominant_cluster: str | None = None


class LLMInterpretationResponseView(BaseModel):
    status: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    interpretations: list[LLMGapInterpretation] = Field(default_factory=list)
    reason: str | None = None


class AnalysisResponse(BaseModel):
    analysis_id: int
    status: AnalysisStatus
    methodology_version: str
    paper_count: int
    paper_ids: list[int]
    papers: list[AnalysisPaperResponse] = Field(default_factory=list)
    research_question: str | None = None
    evidence: list[AnalysisEvidenceResponse]
    candidate_gaps: list[AnalysisGapResponse]
    limitations: AnalysisLimitations
    key_themes: list[KeyThemeResponse] = Field(default_factory=list)
    corpus_coherence: CorpusCoherenceResponse | None = None
    llm_interpretation: LLMInterpretationResponseView | None = None
