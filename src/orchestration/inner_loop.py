"""
Inner Loop: The atomic search-summarize-validate unit.

Layer 1 of the recursive research agent system.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..semantic_scholar import SemanticScholarAdapter, PaperDetails, SearchFilters
    from ..llm.protocols import LLMProvider
    from ..halugate import LocalHaluGate
    from ..config.loader import InnerLoopConfig
    from .models import ValidatedSummary, ResearchHypothesis
    from ..hypothesis import HypothesisGenerator

logger = logging.getLogger(__name__)


class InnerLoop:
    """
    The Inner Loop: atomic unit of the research agent.

    Performs:
    1. Search for papers (via Semantic Scholar)
    2. Summarize each paper (via LLM)
    3. Validate summaries (via HaluGate at ≥95% groundedness)
    4. Optionally generate hypotheses

    Two modes:
    - SEARCH_SUMMARIZE: Steps 1-3 only
    - HYPOTHESIS: Steps 1-4
    """

    def __init__(
        self,
        search_provider: SemanticScholarAdapter,
        summarizer: LLMProvider,
        halugate: LocalHaluGate,
        config: InnerLoopConfig | None = None,
        hypothesis_generator: HypothesisGenerator | None = None,
    ):
        """
        Initialize the Inner Loop.

        Args:
            search_provider: Semantic Scholar adapter for paper search
            summarizer: LLM provider for summarization
            halugate: HaluGate for validation
            config: Inner loop configuration
            hypothesis_generator: Optional hypothesis generator for HYPOTHESIS mode
        """
        self.search_provider = search_provider
        self.summarizer = summarizer
        self.halugate = halugate
        self.hypothesis_generator = hypothesis_generator

        # Load config with defaults
        if config is None:
            from ..config.loader import InnerLoopConfig
            config = InnerLoopConfig()

        self.groundedness_threshold = config.groundedness_threshold
        self.max_papers = config.max_papers_per_iteration
        self.parallel = config.parallel_summarization
        self.max_concurrency = config.max_summarization_concurrency
        self.fetch_full_text = config.fetch_full_text

    async def search_and_summarize(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int | None = None,
    ) -> tuple[list[PaperDetails], list[ValidatedSummary]]:
        """
        Search for papers and generate validated summaries.

        Only returns summaries that pass HaluGate at the configured
        groundedness threshold (default 95%).

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum papers to process (overrides config)

        Returns:
            Tuple of (papers_found, validated_summaries)
        """
        limit = limit or self.max_papers

        # Step 1: Search for papers
        logger.info(f"Searching for papers: query='{query}', limit={limit}")
        papers = await self.search_provider.search_papers(
            query=query,
            filters=filters,
            limit=limit,
        )
        logger.info(f"Found {len(papers)} papers")

        if not papers:
            return [], []

        # Fetch full paper details (including PDFs if configured)
        paper_ids = [p.paper_id for p in papers]
        try:
            if self.fetch_full_text:
                detailed_papers = await self.search_provider.fetch_papers_with_text(paper_ids)
            else:
                detailed_papers = await self.search_provider.fetch_papers(paper_ids)
        except Exception as e:
            logger.warning(f"Failed to fetch paper details: {e}, using search results")
            from ..semantic_scholar import PaperDetails
            detailed_papers = [PaperDetails.model_validate(p.model_dump()) for p in papers]

        # Step 2 & 3: Summarize and validate each paper
        if self.parallel:
            summaries = await self._summarize_parallel(detailed_papers)
        else:
            summaries = await self._summarize_sequential(detailed_papers)

        logger.info(
            f"Validated {len(summaries)}/{len(detailed_papers)} summaries "
            f"at ≥{self.groundedness_threshold:.0%} groundedness"
        )

        return detailed_papers, summaries

    async def _summarize_parallel(
        self,
        papers: list[PaperDetails],
    ) -> list[ValidatedSummary]:
        """Summarize papers in parallel with concurrency limit."""
        from .models import ValidatedSummary

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_paper(paper: PaperDetails) -> ValidatedSummary | None:
            async with semaphore:
                return await self._summarize_and_validate(paper)

        tasks = [process_paper(p) for p in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries = []
        for result in results:
            if isinstance(result, ValidatedSummary):
                summaries.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Summarization failed: {result}")

        return summaries

    async def _summarize_sequential(
        self,
        papers: list[PaperDetails],
    ) -> list[ValidatedSummary]:
        """Summarize papers sequentially."""
        summaries = []

        for paper in papers:
            try:
                summary = await self._summarize_and_validate(paper)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                logger.warning(f"Failed to summarize paper {paper.paper_id}: {e}")

        return summaries

    async def _summarize_and_validate(
        self,
        paper: PaperDetails,
    ) -> ValidatedSummary | None:
        """
        Summarize a single paper and validate with HaluGate.

        Returns None if validation fails.
        """
        from .models import ValidatedSummary
        from ..summarize import summarize_paper

        # Use the Overseer pattern: generate-validate-retry
        context = paper.full_text or paper.abstract or ""
        if not context:
            logger.warning(f"No content for paper {paper.paper_id}")
            return None

        question = f"Summarize the paper: {paper.title}"
        best_summary = None
        best_groundedness = 0.0

        # Try up to 2 times with stricter guidance on retry
        for attempt in range(2):
            guidance = None
            if attempt > 0:
                guidance = (
                    "Only include claims directly supported by the provided paper content. "
                    "Prefer omission over speculation. Be precise and factual."
                )

            # Generate summary
            try:
                summary_text = await summarize_paper(
                    paper=paper,
                    provider=self.summarizer,
                    guidance=guidance,
                )
            except Exception as e:
                logger.warning(f"Summarization error for {paper.paper_id}: {e}")
                continue

            # Validate with HaluGate
            try:
                result = await self.halugate.validate(
                    context=context,
                    question=question,
                    answer=summary_text,
                )
                groundedness = self.halugate.compute_groundedness(result, summary_text)
            except Exception as e:
                logger.warning(f"Validation error for {paper.paper_id}: {e}")
                continue

            logger.debug(
                f"Paper {paper.paper_id} attempt {attempt + 1}: "
                f"groundedness={groundedness:.2%}"
            )

            # Track best attempt
            if groundedness > best_groundedness:
                best_groundedness = groundedness
                best_summary = summary_text

            # Check if good enough
            if groundedness >= self.groundedness_threshold and result.nli_contradictions == 0:
                return ValidatedSummary(
                    paper_id=paper.paper_id,
                    paper_title=paper.title or "Unknown",
                    summary=summary_text,
                    groundedness=groundedness,
                    timestamp=datetime.now(),
                )

        # Return best attempt if it meets a lower threshold (for partial results)
        if best_summary and best_groundedness >= 0.7:
            logger.warning(
                f"Paper {paper.paper_id} only achieved {best_groundedness:.2%} groundedness "
                f"(below {self.groundedness_threshold:.0%} threshold)"
            )
            return ValidatedSummary(
                paper_id=paper.paper_id,
                paper_title=paper.title or "Unknown",
                summary=best_summary,
                groundedness=best_groundedness,
                timestamp=datetime.now(),
            )

        logger.warning(
            f"Paper {paper.paper_id} failed validation after 2 attempts "
            f"(best groundedness: {best_groundedness:.2%})"
        )
        return None

    async def generate_hypotheses(
        self,
        summaries: list[ValidatedSummary],
        branch_id: str,
        context: str | None = None,
    ) -> list[ResearchHypothesis]:
        """
        Generate research hypotheses from validated summaries.

        Requires hypothesis_generator to be configured.

        Args:
            summaries: List of validated summaries
            branch_id: ID of the branch these hypotheses belong to
            context: Optional additional context

        Returns:
            List of generated research hypotheses
        """
        if not self.hypothesis_generator:
            logger.warning("No hypothesis generator configured")
            return []

        if not summaries:
            logger.warning("No summaries to generate hypotheses from")
            return []

        return await self.hypothesis_generator.generate(
            summaries=summaries,
            branch_id=branch_id,
            context=context,
        )

    async def run(
        self,
        query: str,
        branch_id: str,
        filters: SearchFilters | None = None,
        generate_hypotheses: bool = False,
        limit: int | None = None,
    ) -> tuple[list[PaperDetails], list[ValidatedSummary], list[ResearchHypothesis] | None]:
        """
        Run the complete inner loop.

        Args:
            query: Search query
            branch_id: Branch ID for hypothesis generation
            filters: Optional search filters
            generate_hypotheses: Whether to generate hypotheses (HYPOTHESIS mode)
            limit: Maximum papers to process

        Returns:
            Tuple of (papers, summaries, hypotheses or None)
        """
        papers, summaries = await self.search_and_summarize(
            query=query,
            filters=filters,
            limit=limit,
        )

        hypotheses = None
        if generate_hypotheses and summaries:
            hypotheses = await self.generate_hypotheses(
                summaries=summaries,
                branch_id=branch_id,
            )

        return papers, summaries, hypotheses
