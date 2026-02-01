"""Adapter implementations for LLM providers."""

import logging

from openai import AsyncOpenAI

from ..settings import (
    ANTHROPIC_API_KEY,
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


class AnthropicAdapter(LLMProvider):
    """
    Adapter for Anthropic API (direct).

    Uses the Anthropic Python SDK directly for Claude models.

    Usage:
        async with AnthropicAdapter() as llm:
            response = await llm.complete("What is machine learning?")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-haiku-20240307",
    ):
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Optional API key. If not provided, uses ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to claude-3-haiku-20240307.
        """
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model
        self._client = None

        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY in .env"
            )

        logger.info(f"Anthropic adapter initialized with model: {self.model}")

    async def __aenter__(self) -> "AnthropicAdapter":
        import anthropic

        self._client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            max_retries=10,
            timeout=120.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self):
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
        logger.info(f"Completing prompt ({len(prompt)} chars) with {self.model}")
        logger.debug(f"Temperature: {temperature}, max_tokens: {max_tokens}")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 4096,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        result = message.content[0].text if message.content else ""
        logger.info(f"Completion received ({len(result)} chars)")
        logger.debug(f"Usage: input={message.usage.input_tokens}, output={message.usage.output_tokens}")

        return result

    async def complete_messages(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for a conversation."""
        # Extract system message if present
        system_prompt = ""
        formatted_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
            else:
                formatted_messages.append({"role": msg.role.value, "content": msg.content})

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 4096,
            system=system_prompt,
            messages=formatted_messages,
            temperature=temperature,
        )

        return message.content[0].text if message.content else ""

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Generate a completion with tool use support.

        Args:
            prompt: User prompt
            tools: List of tool definitions in Anthropic format
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dict containing:
                - content: Text content from the response
                - tool_use: List of tool use blocks if any
                - stop_reason: Why generation stopped
        """
        logger.info(f"Completing with tools ({len(tools)} tools) using {self.model}")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 4096,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            temperature=temperature,
        )

        # Parse response
        result = {
            "content": "",
            "tool_use": [],
            "stop_reason": message.stop_reason,
        }

        for block in message.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_use"].append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        logger.info(
            f"Tool completion received: {len(result['tool_use'])} tool calls, "
            f"stop_reason={message.stop_reason}"
        )

        return result
