from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMGapInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_id: str
    interpretation: str
    rationale: str
    confidence: float = Field(ge=0, le=1)
    supporting_paper_ids: list[int] = Field(min_length=1)
    evidence_claims: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("gap_id", "interpretation", "rationale")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("LLM interpretation text cannot be empty")
        return value

    @field_validator("supporting_paper_ids")
    @classmethod
    def valid_paper_ids(cls, value: list[int]) -> list[int]:
        if any(paper_id <= 0 for paper_id in value) or len(value) != len(set(value)):
            raise ValueError("supporting_paper_ids must contain unique positive IDs")
        return value

    @field_validator("evidence_claims", "limitations")
    @classmethod
    def non_empty_strings(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("LLM lists cannot contain empty strings")
        return normalized


class LLMInterpretationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interpretations: list[LLMGapInterpretation] = Field(default_factory=list)
