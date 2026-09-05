from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class GapCategory(str, Enum):
    TOPIC_UNDERREPRESENTATION = "topic_underrepresentation"
    POPULATION_CONTEXT = "population_context"
    METHODOLOGY = "methodology"
    DATASET = "dataset"
    TEMPORAL = "temporal"
    MISSING_COMPARISON = "missing_comparison"
    MISSING_OUTCOME = "missing_outcome"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    FUTURE_WORK = "future_work"
    REPLICATION = "replication"
    OTHER = "other"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    IMPRECISE_EVIDENCE = "imprecise_evidence"
    METHODOLOGICAL_LIMITATION = "methodological_limitation"
    INCONSISTENT_EVIDENCE = "inconsistent_evidence"
    POPULATION_GAP = "population_gap"
    INTERVENTION_OR_METHOD_GAP = "intervention_or_method_gap"
    COMPARISON_GAP = "comparison_gap"
    OUTCOME_GAP = "outcome_gap"
    SETTING_OR_CONTEXT_GAP = "setting_or_context_gap"
    VALIDATION_GAP = "validation_gap"


class EvidenceCategory(str, Enum):
    PAPER_METADATA = "paper_metadata"
    ABSTRACT = "abstract"
    LIMITATION = "limitation"
    FUTURE_WORK = "future_work"
    METHODOLOGY = "methodology"
    POPULATION_CONTEXT = "population_context"
    OUTCOME = "outcome"
    COMPARISON = "comparison"
    DATASET = "dataset"
    TEMPORAL = "temporal"
    CONTRADICTION = "contradiction"
    TOPIC = "topic"
    FINDING = "finding"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MethodologyVersion(str):
    """Non-empty identifier for the deterministic analysis methodology."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
        )

    @classmethod
    def _validate(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("methodology_version cannot be empty")
        return value


class SelectedPaperInput(BaseModel):
    paper_id: int = Field(gt=0)


class AnalysisLimitations(BaseModel):
    items: list[str] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def validate_items(cls, items: list[str]) -> list[str]:
        normalized = [item.strip() for item in items]
        if any(not item for item in normalized):
            raise ValueError("limitations cannot contain empty statements")
        return normalized


class AnalysisRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1)
    research_question: str | None = None
    framework: str | None = None
    methodology_version: MethodologyVersion

    @field_validator("paper_ids")
    @classmethod
    def validate_paper_ids(cls, paper_ids: list[int]) -> list[int]:
        if any(paper_id <= 0 for paper_id in paper_ids):
            raise ValueError("paper_ids must contain positive IDs")
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("paper_ids must not contain duplicates")
        return paper_ids

    @field_validator("research_question", "framework")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class EvidenceItem(BaseModel):
    paper_id: int = Field(gt=0)
    evidence_type: EvidenceCategory
    claim: str
    source_excerpt: str | None = None
    source_field: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_status: str = "research_element"
    interpretation: str = "A research element was identified in the source excerpt."

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, claim: str) -> str:
        claim = claim.strip()
        if not claim:
            raise ValueError("claim cannot be empty")
        return claim

    @field_validator("source_excerpt", "source_field")
    @classmethod
    def normalize_optional_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ConfidenceBreakdown(BaseModel):
    explicit_evidence: float = Field(default=0.0, ge=0, le=1)
    independent_papers: float = Field(default=0.0, ge=0, le=1)
    cross_paper_consistency: float = Field(default=0.0, ge=0, le=1)
    specificity: float = Field(default=0.0, ge=0, le=1)
    inference_penalty: float = Field(default=0.0, ge=0, le=1)
    corpus_size_penalty: float = Field(default=0.0, ge=0, le=1)


class CandidateResearchGap(BaseModel):
    id: str
    category: GapCategory
    statement: str
    observed_evidence: list[str] = Field(min_length=1)
    pattern: str
    inference: str
    confidence: float = Field(ge=0, le=1)
    confidence_breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    supporting_paper_ids: list[int] = Field(min_length=1)
    limitations: AnalysisLimitations = Field(default_factory=AnalysisLimitations)

    @field_validator("id", "statement", "pattern", "inference")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("gap text fields cannot be empty")
        return value

    @field_validator("observed_evidence")
    @classmethod
    def validate_observed_evidence(cls, evidence: list[str]) -> list[str]:
        normalized = [item.strip() for item in evidence]
        if any(not item for item in normalized):
            raise ValueError("observed_evidence cannot contain empty statements")
        return normalized

    @field_validator("supporting_paper_ids")
    @classmethod
    def validate_supporting_paper_ids(cls, paper_ids: list[int]) -> list[int]:
        if any(paper_id <= 0 for paper_id in paper_ids):
            raise ValueError("supporting_paper_ids must contain positive IDs")
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("supporting_paper_ids must not contain duplicates")
        return paper_ids


class AnalysisResult(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    methodology_version: MethodologyVersion
    paper_count: int = Field(ge=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    candidate_gaps: list[CandidateResearchGap] = Field(default_factory=list)
    limitations: AnalysisLimitations = Field(default_factory=AnalysisLimitations)
    paper_ids: list[int] = Field(min_length=1)

    @field_validator("analysis_id")
    @classmethod
    def validate_analysis_id(cls, analysis_id: str) -> str:
        analysis_id = analysis_id.strip()
        if not analysis_id:
            raise ValueError("analysis_id cannot be empty")
        return analysis_id

    @field_validator("paper_ids")
    @classmethod
    def validate_result_paper_ids(cls, paper_ids: list[int]) -> list[int]:
        if any(paper_id <= 0 for paper_id in paper_ids):
            raise ValueError("paper_ids must contain positive IDs")
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("paper_ids must not contain duplicates")
        return paper_ids

    @model_validator(mode="after")
    def validate_paper_references(self) -> "AnalysisResult":
        input_ids = set(self.paper_ids)
        if self.paper_count != len(self.paper_ids):
            raise ValueError("paper_count must match the number of paper_ids")
        evidence_ids = {item.paper_id for item in self.evidence}
        if not evidence_ids.issubset(input_ids):
            raise ValueError("evidence paper IDs must belong to the analysis input")
        for gap in self.candidate_gaps:
            if not set(gap.supporting_paper_ids).issubset(input_ids):
                raise ValueError("supporting paper IDs must belong to the analysis input")
        return self
