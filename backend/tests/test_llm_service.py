import asyncio

import pytest

from app.analysis.llm_provider import LLMProviderError
from app.analysis.llm_schemas import LLMGapInterpretation, LLMInterpretationResponse
from app.analysis.llm_service import interpret_gaps
from app.analysis.schemas import CandidateResearchGap, EvidenceCategory, EvidenceItem, GapCategory


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_schema):
        self.calls += 1
        assert "Do not invent" in system_prompt
        assert "Candidate gaps" in user_prompt
        if self.error:
            raise self.error
        return self.response


class SlowProvider(FakeProvider):
    async def generate_structured(self, **kwargs):
        await asyncio.sleep(0.05)
        return await super().generate_structured(**kwargs)


def inputs():
    evidence = [
        EvidenceItem(
            paper_id=1,
            evidence_type=EvidenceCategory.METHODOLOGY,
            claim="Survey evidence",
            source_excerpt="Survey evidence",
            confidence=0.95,
        )
    ]
    gap = CandidateResearchGap(
        id="gap-1",
        category=GapCategory.METHODOLOGY,
        statement="Methods vary.",
        observed_evidence=["Survey evidence"],
        pattern="Repeated survey evidence.",
        inference="Methods may be concentrated.",
        confidence=0.7,
        supporting_paper_ids=[1],
    )
    return evidence, [gap]


def valid_response():
    return LLMInterpretationResponse(
        interpretations=[
            LLMGapInterpretation(
                gap_id="gap-1",
                interpretation="The method pattern deserves validation.",
                rationale="Survey evidence was supplied.",
                confidence=0.6,
                supporting_paper_ids=[1],
                evidence_claims=["Survey evidence"],
            )
        ]
    )


def run(provider):
    evidence, gaps = inputs()
    return asyncio.run(
        interpret_gaps(
            provider=provider,
            evidence=evidence,
            gaps=gaps,
            paper_ids=[1],
            methodology_version="v1",
        )
    )


def test_valid_structured_response_is_returned() -> None:
    provider = FakeProvider(valid_response())
    result = run(provider)
    assert result.interpretations[0].gap_id == "gap-1"
    assert provider.calls == 1


@pytest.mark.parametrize(
    "response",
    [
        LLMInterpretationResponse(
            interpretations=[
                LLMGapInterpretation(
                    gap_id="unknown",
                    interpretation="x",
                    rationale="x",
                    confidence=0.5,
                    supporting_paper_ids=[1],
                    evidence_claims=["Survey evidence"],
                )
            ]
        ),
        LLMInterpretationResponse(
            interpretations=[
                LLMGapInterpretation(
                    gap_id="gap-1",
                    interpretation="x",
                    rationale="x",
                    confidence=0.5,
                    supporting_paper_ids=[2],
                    evidence_claims=["Survey evidence"],
                )
            ]
        ),
        LLMInterpretationResponse(
            interpretations=[
                LLMGapInterpretation(
                    gap_id="gap-1",
                    interpretation="x",
                    rationale="x",
                    confidence=0.5,
                    supporting_paper_ids=[1],
                    evidence_claims=["invented evidence"],
                )
            ]
        ),
    ],
)
def test_hallucinated_references_are_rejected(response) -> None:
    with pytest.raises(LLMProviderError):
        run(FakeProvider(response))


def test_provider_exception_is_normalized() -> None:
    with pytest.raises(LLMProviderError, match="request failed"):
        run(FakeProvider(error=TimeoutError()))


def test_invalid_structured_output_is_rejected() -> None:
    with pytest.raises(LLMProviderError, match="invalid structured output"):
        run(FakeProvider({"unexpected": "value"}))


def test_provider_timeout_is_bounded(monkeypatch) -> None:
    import app.analysis.llm_service as service

    monkeypatch.setattr(service, "LLM_PROVIDER_TIMEOUT_SECONDS", 0.001)
    with pytest.raises(LLMProviderError, match="request failed"):
        run(SlowProvider())
