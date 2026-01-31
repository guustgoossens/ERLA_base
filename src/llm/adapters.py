"""Adapter implementations for LLM providers."""

import logging

from openai import AsyncOpenAI

from ..settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_DEFAULT_MODEL,
)
from .protocols import LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)


class OpenRouterAdapter(LLMProvider):
    """
    Adapter for OpenRouter API.

    OpenRouter provides access to many LLMs through an OpenAI-compatible API.

    Usage:
        async with OpenRouterAdapter() as llm:
            response = await llm.complete("What is machine learning?")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """
        Initialize the OpenRouter adapter.

        Args:
            api_key: Optional API key. If not provided, uses OPENROUTER_API_KEY env var.
            model: Model to use. Defaults to OPENROUTER_DEFAULT_MODEL.
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or OPENROUTER_DEFAULT_MODEL
        self._client: AsyncOpenAI | None = None

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY in .env"
            )

        logger.info(f"OpenRouter adapter initialized with model: {self.model}")

    async def __aenter__(self) -> "OpenRouterAdapter":
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=OPENROUTER_BASE_URL,
            max_retries=10,  # More retries for free tier rate limits
            timeout=120.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for a simple prompt."""
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        logger.info(f"Completing prompt ({len(prompt)} chars) with {self.model}")
        logger.debug(f"Temperature: {temperature}, max_tokens: {max_tokens}")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content or ""
        logger.info(f"Completion received ({len(result)} chars)")
        logger.debug(f"Usage: {response.usage}")

        return result

    async def complete_messages(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for a conversation."""
        formatted_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""
