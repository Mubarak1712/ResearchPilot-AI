from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMProviderError(Exception):
    """Safe provider failure that must not replace deterministic analysis."""


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        ...


class UnavailableLLMProvider:
    provider_name = "unconfigured"
    model_name = "unconfigured"

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        del system_prompt, user_prompt, response_schema
        raise LLMProviderError("LLM provider is not configured")
