import asyncio

import pytest

from app.analysis.llm_provider import LLMProviderError, UnavailableLLMProvider
from app.analysis.llm_schemas import LLMInterpretationResponse


def test_unconfigured_provider_fails_safely() -> None:
    with pytest.raises(LLMProviderError, match="not configured"):
        asyncio.run(
            UnavailableLLMProvider().generate_structured(
                system_prompt="system",
                user_prompt="user",
                response_schema=LLMInterpretationResponse,
            )
        )
