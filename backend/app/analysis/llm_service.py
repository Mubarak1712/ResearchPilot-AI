from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence

from app.analysis.llm_provider import LLMProvider, LLMProviderError, UnavailableLLMProvider
from app.analysis.llm_schemas import LLMGapInterpretation, LLMInterpretationResponse
from app.analysis.schemas import CandidateResearchGap, EvidenceItem


LLM_PROMPT_VERSION = "1.0"
MAX_PROMPT_ITEMS = 50
LLM_PROVIDER_TIMEOUT_SECONDS = 20


def get_configured_provider() -> LLMProvider:
    # No provider adapter or credentials are shipped in this phase.
    # Deployments can replace this factory without changing analysis code.
    if not (os.getenv("LLM_PROVIDER") or "").strip():
        return UnavailableLLMProvider()
    return UnavailableLLMProvider()


async def interpret_gaps(
    *,
    provider: LLMProvider,
    evidence: Sequence[EvidenceItem],
    gaps: Sequence[CandidateResearchGap],
    paper_ids: Sequence[int],
    methodology_version: str,
) -> LLMInterpretationResponse:
    selected_evidence = list(evidence)[:MAX_PROMPT_ITEMS]
    selected_gaps = list(gaps)[:MAX_PROMPT_ITEMS]
    system_prompt = (
        f"You are interpreting deterministic candidate gaps under methodology {methodology_version}. "
        "Use only the supplied evidence and candidate gaps. Do not invent papers, quotations, evidence, "
        "facts, or gaps; do not claim absence of literature. Preserve uncertainty and return structured output only."
    )
    user_prompt = (
        f"Corpus paper IDs: {sorted(paper_ids)}\n"
        f"Evidence: {[item.model_dump(mode='json') for item in selected_evidence]}\n"
        f"Candidate gaps: {[gap.model_dump(mode='json') for gap in selected_gaps]}\n"
        "Known limitation: evidence is derived from the selected corpus and available text only."
    )
    try:
        raw = await asyncio.wait_for(
            provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=LLMInterpretationResponse,
            ),
            timeout=LLM_PROVIDER_TIMEOUT_SECONDS,
        )
    except LLMProviderError:
        raise
    except Exception as error:
        raise LLMProviderError("LLM provider request failed") from error
    try:
        parsed = (
            raw
            if isinstance(raw, LLMInterpretationResponse)
            else LLMInterpretationResponse.model_validate(raw)
        )
    except Exception as error:
        raise LLMProviderError("LLM provider returned invalid structured output") from error
    _validate_against_inputs(parsed.interpretations, selected_evidence, selected_gaps, paper_ids)
    return parsed


def _validate_against_inputs(
    interpretations: Sequence[LLMGapInterpretation],
    evidence: Sequence[EvidenceItem],
    gaps: Sequence[CandidateResearchGap],
    paper_ids: Sequence[int],
) -> None:
    gap_ids = {gap.id for gap in gaps}
    evidence_claims = {item.claim for item in evidence}
    allowed_papers = set(paper_ids)
    for interpretation in interpretations:
        if interpretation.gap_id not in gap_ids:
            raise LLMProviderError("LLM referenced an unknown candidate gap")
        if not set(interpretation.supporting_paper_ids).issubset(allowed_papers):
            raise LLMProviderError("LLM referenced a paper outside the analysis corpus")
        if not set(interpretation.evidence_claims).issubset(evidence_claims):
            raise LLMProviderError("LLM referenced evidence outside the supplied evidence set")
