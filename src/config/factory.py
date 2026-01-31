"""Factory functions to create backends from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.protocols import LLMProvider
    from ..halugate import LocalHaluGate
    from ..orchestration.overseer import Overseer
    from .loader import ProfileConfig, SummarizerConfig, HaluGateConfig, OverseerConfig


class MockLLMProvider:
    """Mock LLM provider for testing."""

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Return a mock completion."""
        return f"[Mock summary of: {prompt[:50]}...]"

    async def complete_messages(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Return a mock completion for messages."""
        return "[Mock response]"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockHaluGate:
    """Mock HaluGate for testing - always returns no hallucinations."""

    def __init__(self):
        from ..halugate.models import HallucinationResult

        self._result_class = HallucinationResult

    async def validate(
        self,
        context: str,
        question: str,
        answer: str,
    ):
        """Return a mock validation result with no hallucinations."""
        return self._result_class(
            fact_check_needed=True,
            hallucination_detected=False,
            spans=[],
            max_severity=0,
            nli_contradictions=0,
            raw_response="[Mock: no hallucinations]",
        )

    def compute_groundedness(self, result, answer: str) -> float:
        """Return perfect groundedness for mock."""
        return 1.0


def create_summarizer(config: SummarizerConfig) -> LLMProvider:
    """Create a summarizer backend from configuration.

    Args:
        config: Summarizer configuration

    Returns:
        LLMProvider instance (OpenRouterAdapter or Mock)

    Raises:
        ValueError: If backend type is not supported
    """
    if config.backend == "openrouter":
        from ..llm import OpenRouterAdapter

        if not config.api_key:
            raise ValueError("OpenRouter backend requires api_key")

        return OpenRouterAdapter(
            api_key=config.api_key,
            model=config.model,
        )

    elif config.backend == "mock":
        return MockLLMProvider()

    else:
        raise ValueError(f"Unsupported summarizer backend: {config.backend}")


def create_halugate(config: HaluGateConfig) -> LocalHaluGate:
    """Create HaluGate from configuration.

    Args:
        config: HaluGate configuration

    Returns:
        LocalHaluGate instance (local, HTTP, or mock)

    Raises:
        ValueError: If backend type is not supported or required fields are missing
    """
    if config.backend == "local":
        from ..halugate import LocalHaluGate

        return LocalHaluGate(
            device=config.device,
            use_sentinel=config.use_sentinel,
        )

    elif config.backend == "http":
        # HTTP backend would require a separate implementation
        # For now, raise an error as HTTP is not yet implemented
        raise NotImplementedError(
            "HTTP HaluGate backend not yet implemented. "
            "Use 'local' backend for now."
        )

    elif config.backend == "mock":
        return MockHaluGate()

    else:
        raise ValueError(f"Unsupported HaluGate backend: {config.backend}")


def create_overseer(
    halugate,
    summarizer,
    config: OverseerConfig,
) -> Overseer:
    """Create Overseer from configuration.

    Args:
        halugate: HaluGate instance for validation
        summarizer: LLM provider for summarization
        config: Overseer configuration

    Returns:
        Overseer instance with configured retry logic
    """
    from ..orchestration.overseer import Overseer

    return Overseer(
        halugate=halugate,
        summarizer=summarizer,
        max_retries=config.max_retries,
        groundedness_threshold=config.groundedness_threshold,
    )


def create_from_profile(
    profile: ProfileConfig,
) -> tuple:
    """Create all backends from a profile configuration.

    This is the main factory function that creates a complete set of backends
    from a configuration profile.

    Args:
        profile: Profile configuration containing all backend configs

    Returns:
        Tuple of (summarizer, halugate, overseer)

    Raises:
        ValueError: If any backend configuration is invalid
    """
    summarizer = create_summarizer(profile.summarizer)
    halugate = create_halugate(profile.halugate)
    overseer = create_overseer(halugate, summarizer, profile.overseer)

    return summarizer, halugate, overseer
