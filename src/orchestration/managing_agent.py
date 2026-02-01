"""
Managing Agent: Intelligent branch splitting with Claude Opus.

The Managing Agent uses Claude Opus 4.5 with tool use to make intelligent
decisions about when and how to split research branches based on paper content,
rather than simple context window thresholds.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config.loader import ManagingAgentConfig
    from ..llm.adapters import AnthropicAdapter
    from .models import Branch

logger = logging.getLogger(__name__)


@dataclass
class SplitRecommendation:
    """Recommendation from the managing agent about branch splitting."""

    should_split: bool
    num_branches: int
    paper_groups: list[list[str]]  # Paper IDs grouped for each new branch
    group_queries: list[str]  # Search queries for each group
    group_labels: list[str]  # Human-readable labels for each group
    reasoning: str  # Why this split was recommended

    @classmethod
    def no_split(cls, reasoning: str = "Splitting not recommended") -> SplitRecommendation:
        """Create a recommendation to not split."""
        return cls(
            should_split=False,
            num_branches=0,
            paper_groups=[],
            group_queries=[],
            group_labels=[],
            reasoning=reasoning,
        )


# Tool definitions for Claude
ANALYZE_RESEARCH_STATE_TOOL = {
    "name": "analyze_research_state",
    "description": """Analyze the current research branch state to determine if splitting is beneficial.

Consider:
- Are there distinct research themes emerging?
- Would splitting help explore different directions more deeply?
- Is there enough diversity in papers to warrant separate branches?
- Are papers naturally clustering around different topics, methodologies, or time periods?

Return a detailed analysis with a split recommendation.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "should_split": {
                "type": "boolean",
                "description": "Whether the branch should be split",
            },
            "num_branches": {
                "type": "integer",
                "description": "Number of branches to create (2-4)",
                "minimum": 2,
                "maximum": 4,
            },
            "split_strategy": {
                "type": "string",
                "enum": ["by_topic", "by_methodology", "by_time_period", "by_application_domain"],
                "description": "The strategy for splitting papers",
            },
            "paper_assignments": {
                "type": "array",
                "description": "List of paper groupings. Each group contains paper IDs.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Human-readable label for this group",
                        },
                        "query": {
                            "type": "string",
                            "description": "Refined search query for this research direction",
                        },
                        "paper_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Paper IDs belonging to this group",
                        },
                    },
                    "required": ["label", "query", "paper_ids"],
                },
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed explanation of the split decision",
            },
        },
        "required": ["should_split", "reasoning"],
    },
}


class ManagingAgent:
    """
    Intelligent branch management agent using Claude Opus.

    The managing agent analyzes research branch content and makes
    informed decisions about when and how to split branches based
    on the actual content rather than simple heuristics.
    """

    def __init__(
        self,
        llm_adapter: AnthropicAdapter,
        config: ManagingAgentConfig | None = None,
    ):
        """
        Initialize the managing agent.

        Args:
            llm_adapter: Anthropic adapter configured for Claude Opus
            config: Managing agent configuration
        """
        self.llm = llm_adapter

        if config is None:
            from ..config.loader import ManagingAgentConfig
            config = ManagingAgentConfig()

        self.config = config
        self.min_papers = config.min_papers_before_evaluation
        self.evaluation_interval = config.evaluation_interval

        # Track evaluation history
        self._evaluation_count: dict[str, int] = {}

    def should_evaluate(self, branch: Branch) -> bool:
        """
        Check if a branch should be evaluated for splitting.

        Args:
            branch: Branch to check

        Returns:
            True if evaluation should occur
        """
        # Need minimum papers
        if len(branch.accumulated_papers) < self.min_papers:
            return False

        # Check evaluation interval
        branch_evals = self._evaluation_count.get(branch.id, 0)
        iterations_since_eval = len(branch.iterations) - (branch_evals * self.evaluation_interval)

        return iterations_since_eval >= self.evaluation_interval

    async def evaluate_branch(self, branch: Branch) -> SplitRecommendation | None:
        """
        Evaluate a branch and recommend whether to split.

        Uses Claude Opus with tool use to analyze the research content
        and make an intelligent splitting decision.

        Args:
            branch: Branch to evaluate

        Returns:
            SplitRecommendation if splitting is recommended, None otherwise
        """
        if not self.should_evaluate(branch):
            return None

        logger.info(f"Managing agent evaluating branch {branch.id}")

        # Build context from papers and summaries
        context = self._build_evaluation_context(branch)

        # Create the prompt
        prompt = self._build_evaluation_prompt(branch, context)

        try:
            # Call Claude Opus with tool use
            response = await self.llm.complete_with_tools(
                prompt=prompt,
                tools=[ANALYZE_RESEARCH_STATE_TOOL],
                system_prompt=self._get_system_prompt(),
                temperature=0.3,  # Lower temperature for more consistent decisions
                max_tokens=4096,
            )

            # Track that we evaluated
            self._evaluation_count[branch.id] = self._evaluation_count.get(branch.id, 0) + 1

            # Parse the tool use response
            if response["tool_use"]:
                return self._parse_tool_response(response["tool_use"][0], branch)
            else:
                logger.warning("Managing agent did not use the analysis tool")
                return None

        except Exception as e:
            logger.error(f"Error evaluating branch with managing agent: {e}")
            return None

    def _build_evaluation_context(self, branch: Branch) -> dict[str, Any]:
        """Build context dict from branch papers and summaries."""
        papers_info = []
        for paper_id, paper in branch.accumulated_papers.items():
            paper_info = {
                "id": paper_id,
                "title": paper.title,
                "year": paper.year,
                "citation_count": paper.citation_count,
                "fields": paper.fields_of_study or [],
            }

            # Add summary if available
            if paper_id in branch.accumulated_summaries:
                summary = branch.accumulated_summaries[paper_id]
                paper_info["summary"] = summary.summary[:500]  # Truncate for context
                paper_info["groundedness"] = summary.groundedness

            papers_info.append(paper_info)

        return {
            "branch_id": branch.id,
            "query": branch.query,
            "iteration_count": len(branch.iterations),
            "paper_count": len(papers_info),
            "context_utilization": branch.context_utilization,
            "papers": papers_info,
        }

    def _build_evaluation_prompt(self, branch: Branch, context: dict) -> str:
        """Build the evaluation prompt for Claude."""
        papers_text = "\n".join([
            f"- [{p['id']}] {p['title']} ({p['year']}) - "
            f"Citations: {p['citation_count']}, Fields: {', '.join(p['fields'][:3])}"
            + (f"\n  Summary: {p.get('summary', 'N/A')[:200]}..." if p.get('summary') else "")
            for p in context["papers"]
        ])

        return f"""Analyze this research branch and decide if it should be split into sub-branches.

## Current Branch
- Query: "{context['query']}"
- Papers collected: {context['paper_count']}
- Iterations completed: {context['iteration_count']}
- Context utilization: {context['context_utilization']:.1%}

## Papers in this branch:
{papers_text}

## Instructions
Use the analyze_research_state tool to:
1. Identify if there are distinct research themes, methodologies, or application domains
2. Decide if splitting would improve research depth
3. If splitting, group papers by theme and suggest refined queries for each group
4. Provide clear reasoning for your decision

Consider that splitting is most valuable when:
- Papers naturally cluster around 2-4 distinct themes
- Each theme has enough papers (3+) to form a viable branch
- The themes are coherent and would benefit from focused exploration

Do NOT recommend splitting if:
- Papers are highly related and form one coherent research direction
- There aren't enough papers for meaningful sub-branches
- The research is still in early exploration phase"""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the managing agent."""
        return """You are an expert research manager analyzing academic paper collections.
Your role is to intelligently decide when research branches should be split to enable
deeper exploration of distinct research directions.

You have deep expertise in:
- Identifying research themes and methodologies
- Recognizing when research directions diverge
- Optimizing research exploration strategies

Always use the analyze_research_state tool to provide your analysis.
Be conservative with splitting - only recommend it when there's clear benefit."""

    def _parse_tool_response(
        self,
        tool_call: dict,
        branch: Branch,
    ) -> SplitRecommendation | None:
        """Parse the tool call response into a SplitRecommendation."""
        try:
            input_data = tool_call["input"]

            if not input_data.get("should_split", False):
                logger.info(
                    f"Managing agent recommends NO split for branch {branch.id}: "
                    f"{input_data.get('reasoning', 'No reasoning provided')}"
                )
                return SplitRecommendation.no_split(input_data.get("reasoning", ""))

            # Parse paper assignments
            assignments = input_data.get("paper_assignments", [])
            if not assignments:
                logger.warning("Split recommended but no paper assignments provided")
                return None

            paper_groups = [a["paper_ids"] for a in assignments]
            group_queries = [a["query"] for a in assignments]
            group_labels = [a["label"] for a in assignments]

            recommendation = SplitRecommendation(
                should_split=True,
                num_branches=len(assignments),
                paper_groups=paper_groups,
                group_queries=group_queries,
                group_labels=group_labels,
                reasoning=input_data.get("reasoning", ""),
            )

            logger.info(
                f"Managing agent recommends split for branch {branch.id} into "
                f"{recommendation.num_branches} branches: {group_labels}"
            )
            logger.debug(f"Split reasoning: {recommendation.reasoning}")

            return recommendation

        except Exception as e:
            logger.error(f"Error parsing managing agent response: {e}")
            return None


async def create_managing_agent(
    config: ManagingAgentConfig | None = None,
) -> ManagingAgent:
    """
    Factory function to create a ManagingAgent with proper adapter.

    Args:
        config: Managing agent configuration

    Returns:
        Configured ManagingAgent instance
    """
    from ..llm.adapters import AnthropicAdapter
    from ..settings import ANTHROPIC_API_KEY

    if config is None:
        from ..config.loader import ManagingAgentConfig
        config = ManagingAgentConfig()

    # Create adapter with Opus model
    adapter = AnthropicAdapter(
        api_key=ANTHROPIC_API_KEY,
        model=config.model,
    )

    return ManagingAgent(llm_adapter=adapter, config=config)
