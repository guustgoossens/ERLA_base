"""
Master Agent: Orchestrates the entire research loop.

Layer 3 of the recursive research agent system.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config.loader import (
        MasterAgentConfig,
        ResearchLoopConfig,
        ProfileConfig,
    )
    from ..semantic_scholar import SemanticScholarAdapter
    from ..llm.protocols import LLMProvider
    from ..halugate import LocalHaluGate
    from .models import (
        Branch,
        IterationResult,
        InnerLoopMode,
        LoopState,
        LoopStatus,
        ResearchHypothesis,
    )

logger = logging.getLogger(__name__)


class MasterAgent:
    """
    The Master Agent: orchestrates the entire research loop.

    Responsibilities:
    - Manages branches and their lifecycles
    - Monitors context window usage
    - Decides when to split, prune, or switch modes
    - Launches Big Loop 2 with generated hypotheses

    Tool interface:
    - run_iteration: Run one iteration on a branch
    - split_branch: Split when context >80% full
    - switch_mode: Enable hypothesis generation
    - launch_research_loop: Start Big Loop 2
    - prune_branch: Stop low-value branches
    - get_status: Check papers/context per branch
    """

    def __init__(
        self,
        search_provider: SemanticScholarAdapter,
        summarizer: LLMProvider,
        halugate: LocalHaluGate,
        config: ResearchLoopConfig | None = None,
    ):
        """
        Initialize the Master Agent.

        Args:
            search_provider: Semantic Scholar adapter
            summarizer: LLM provider for summarization
            halugate: HaluGate for validation
            config: Research loop configuration
        """
        from .inner_loop import InnerLoop
        from .iteration_loop import IterationLoop
        from .branch_manager import BranchManager
        from .state_store import StateStore
        from ..context.estimator import ContextEstimator
        from ..context.splitter import BranchSplitter
        from ..hypothesis import HypothesisGenerator

        # Load config with defaults
        if config is None:
            from ..config.loader import ResearchLoopConfig
            config = ResearchLoopConfig()

        self.config = config

        # Initialize components
        self.context_estimator = ContextEstimator()
        self.splitter = BranchSplitter()

        # Create hypothesis generator
        self.hypothesis_generator = HypothesisGenerator(
            llm_provider=summarizer,
        )

        # Create inner loop
        self.inner_loop = InnerLoop(
            search_provider=search_provider,
            summarizer=summarizer,
            halugate=halugate,
            config=config.inner_loop,
            hypothesis_generator=self.hypothesis_generator,
        )

        # Create iteration loop
        self.iteration_loop = IterationLoop(
            inner_loop=self.inner_loop,
            search_provider=search_provider,
            context_estimator=self.context_estimator,
            config=config.iteration_loop,
        )

        # Create branch manager
        self.branch_manager = BranchManager(
            splitter=self.splitter,
            config=config.branch,
        )

        # Create state store
        self.state_store = StateStore()

        # Current loop state
        self._current_state: LoopState | None = None

        # Auto-management flags
        self.auto_split = config.master_agent.auto_split_enabled
        self.auto_prune = config.master_agent.auto_prune_enabled
        self.auto_hypothesis = config.master_agent.auto_hypothesis_mode
        self.max_parallel_branches = config.master_agent.max_parallel_branches

    @property
    def current_state(self) -> LoopState | None:
        """Get current loop state."""
        return self._current_state

    def start_loop(
        self,
        initial_query: str,
        loop_number: int = 1,
        seeding_hypotheses: list[ResearchHypothesis] | None = None,
    ) -> LoopState:
        """
        Start a new research loop.

        Args:
            initial_query: Initial search query
            loop_number: Loop number (1 for initial, 2+ for hypothesis-seeded)
            seeding_hypotheses: Hypotheses that seeded this loop (for Big Loop 2+)

        Returns:
            New loop state
        """
        from .models import LoopState, InnerLoopMode, BranchStatus

        loop_id = str(uuid.uuid4())[:8]

        # Create initial state
        state = LoopState(
            loop_id=loop_id,
            loop_number=loop_number,
            seeding_hypotheses=seeding_hypotheses,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Create initial branch
        initial_branch = self.branch_manager.create_branch(
            query=initial_query,
            mode=InnerLoopMode.SEARCH_SUMMARIZE,
        )
        initial_branch.status = BranchStatus.PENDING
        state.add_branch(initial_branch)

        # Save state
        self._current_state = state
        self.state_store.save_state(state)

        logger.info(
            f"Started loop {loop_id} (loop #{loop_number}) "
            f"with initial query: '{initial_query[:50]}...'"
        )

        return state

    async def run_iteration(
        self,
        branch_id: str,
        mode: str | InnerLoopMode | None = None,
    ) -> IterationResult:
        """
        Run one iteration on a branch.

        Args:
            branch_id: ID of branch to run iteration on
            mode: Optional mode override for this iteration

        Returns:
            IterationResult from the iteration
        """
        from .models import BranchStatus, InnerLoopMode

        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        branch = self._current_state.get_branch(branch_id)
        if not branch:
            raise ValueError(f"Branch not found: {branch_id}")

        # Handle mode override
        if mode:
            if isinstance(mode, str):
                mode = InnerLoopMode(mode)
            branch.mode = mode

        # Update status to running
        branch.status = BranchStatus.RUNNING
        branch.updated_at = datetime.now()

        # Run iteration
        result = await self.iteration_loop.run_iteration(branch)

        # Add result to branch
        branch.add_iteration(result)

        # Auto-management checks
        if self.auto_split and self.branch_manager.should_split(branch):
            logger.info(f"Auto-splitting branch {branch_id} (context threshold reached)")
            await self.split_branch(branch_id, "by_field")

        elif self.auto_hypothesis and self.branch_manager.should_enable_hypothesis_mode(branch):
            logger.info(f"Auto-enabling hypothesis mode for branch {branch_id}")
            self.switch_mode(branch_id, InnerLoopMode.HYPOTHESIS)

            # Immediately run one more iteration to generate hypotheses
            # This ensures hypotheses are generated even if the loop ends after this iteration
            logger.info(f"Running hypothesis generation iteration for branch {branch_id}")
            hyp_result = await self.iteration_loop.run_iteration(branch)
            branch.add_iteration(hyp_result)
            logger.info(f"Generated {len(hyp_result.hypotheses or [])} hypotheses")

        # Save state
        self.state_store.save_state(self._current_state)

        return result

    async def split_branch(
        self,
        branch_id: str,
        criteria: str,
    ) -> list[str]:
        """
        Split a branch into multiple child branches.

        Args:
            branch_id: ID of branch to split
            criteria: Split criteria (by_topic, by_time, by_field, etc.)

        Returns:
            List of new branch IDs
        """
        from ..context.splitter import SplitStrategy

        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        branch = self._current_state.get_branch(branch_id)
        if not branch:
            raise ValueError(f"Branch not found: {branch_id}")

        # Map criteria string to strategy
        strategy = SplitStrategy(criteria)

        # Split the branch
        new_branches = self.branch_manager.split_branch(branch, strategy)

        # Add new branches to state
        for new_branch in new_branches:
            self._current_state.add_branch(new_branch)

        # Save state
        self.state_store.save_state(self._current_state)

        return [b.id for b in new_branches]

    def switch_mode(
        self,
        branch_id: str,
        mode: str | InnerLoopMode,
    ) -> None:
        """
        Switch the mode of a branch.

        Args:
            branch_id: ID of branch to update
            mode: New mode
        """
        from .models import InnerLoopMode

        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        branch = self._current_state.get_branch(branch_id)
        if not branch:
            raise ValueError(f"Branch not found: {branch_id}")

        if isinstance(mode, str):
            mode = InnerLoopMode(mode)

        old_mode = branch.mode
        branch.mode = mode
        branch.updated_at = datetime.now()

        logger.info(
            f"Branch {branch_id} mode: {old_mode.value} -> {mode.value}"
        )

        self.state_store.save_state(self._current_state)

    async def launch_research_loop(
        self,
        hypothesis_ids: list[str],
    ) -> str:
        """
        Launch Big Loop 2 seeded with hypotheses.

        Takes research hypotheses from the current loop and
        starts a new loop using them as queries.

        Args:
            hypothesis_ids: IDs of hypotheses to use as seeds

        Returns:
            ID of the new loop
        """
        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        # Collect hypotheses
        all_hypotheses = self._current_state.collect_all_hypotheses()
        hypothesis_map = {h.id: h for h in all_hypotheses}

        seeding_hypotheses = []
        for hid in hypothesis_ids:
            if hid in hypothesis_map:
                seeding_hypotheses.append(hypothesis_map[hid])
            else:
                logger.warning(f"Hypothesis not found: {hid}")

        if not seeding_hypotheses:
            raise ValueError("No valid hypotheses found for seeding")

        # Create query from hypotheses
        combined_query = " AND ".join(
            h.text[:100] for h in seeding_hypotheses[:3]
        )

        # Start new loop
        new_state = self.start_loop(
            initial_query=combined_query,
            loop_number=self._current_state.loop_number + 1,
            seeding_hypotheses=seeding_hypotheses,
        )

        logger.info(
            f"Launched Big Loop {new_state.loop_number} "
            f"with {len(seeding_hypotheses)} hypotheses"
        )

        return new_state.loop_id

    def prune_branch(
        self,
        branch_id: str,
        reason: str = "",
    ) -> None:
        """
        Prune a branch (stop exploration).

        Args:
            branch_id: ID of branch to prune
            reason: Optional reason for pruning
        """
        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        branch = self._current_state.get_branch(branch_id)
        if not branch:
            raise ValueError(f"Branch not found: {branch_id}")

        self.branch_manager.prune_branch(branch, reason)
        self.state_store.save_state(self._current_state)

    def get_status(
        self,
        branch_id: str | None = None,
    ) -> dict:
        """
        Get status of the loop or a specific branch.

        Args:
            branch_id: Optional branch ID for branch-specific status

        Returns:
            Status dict
        """
        from .models import LoopStatus

        if not self._current_state:
            return {"error": "No active loop"}

        if branch_id:
            branch = self._current_state.get_branch(branch_id)
            if not branch:
                return {"error": f"Branch not found: {branch_id}"}
            return self.branch_manager.get_branch_stats(branch)

        # Return overall loop status
        status = LoopStatus.from_loop_state(self._current_state)
        return {
            "loop_id": status.loop_id,
            "loop_number": status.loop_number,
            "total_branches": status.total_branches,
            "active_branches": status.active_branches,
            "completed_branches": status.completed_branches,
            "pruned_branches": status.pruned_branches,
            "total_papers": status.total_papers,
            "total_summaries": status.total_summaries,
            "total_hypotheses": status.total_hypotheses,
            "total_context_used": status.total_context_used,
        }

    async def run_auto(
        self,
        max_iterations: int = 10,
        stop_on_hypotheses: int = 0,
    ) -> LoopState:
        """
        Run the loop automatically until stopping conditions are met.

        Args:
            max_iterations: Maximum total iterations across all branches
            stop_on_hypotheses: Stop when this many hypotheses are generated (0=disabled)

        Returns:
            Final loop state
        """
        from .models import BranchStatus

        if not self._current_state:
            raise RuntimeError("No active loop. Call start_loop() first.")

        total_iterations = 0

        while total_iterations < max_iterations:
            # Find next branch to process
            branch = self.branch_manager.get_next_branch(self._current_state)
            if not branch:
                logger.info("No more branches to process")
                break

            # Run iteration
            try:
                result = await self.run_iteration(branch.id)
                total_iterations += 1

                logger.info(
                    f"Iteration {total_iterations}: "
                    f"branch={branch.id}, papers={len(result.papers_found)}, "
                    f"summaries={len(result.summaries)}"
                )

            except Exception as e:
                logger.error(f"Error running iteration on branch {branch.id}: {e}")
                self.prune_branch(branch.id, f"Error: {e}")

            # Check hypothesis stopping condition
            if stop_on_hypotheses > 0:
                all_hypotheses = self._current_state.collect_all_hypotheses()
                if len(all_hypotheses) >= stop_on_hypotheses:
                    logger.info(
                        f"Stopping: reached {len(all_hypotheses)} hypotheses "
                        f"(target: {stop_on_hypotheses})"
                    )
                    break

        # Mark remaining pending branches as paused
        for branch in self._current_state.branches.values():
            if branch.status == BranchStatus.PENDING:
                branch.status = BranchStatus.PAUSED

        self.state_store.save_state(self._current_state)

        return self._current_state

    def get_all_hypotheses(self) -> list[ResearchHypothesis]:
        """Get all hypotheses from the current loop."""
        if not self._current_state:
            return []
        return self._current_state.collect_all_hypotheses()

    def get_top_hypotheses(
        self,
        n: int = 5,
        min_confidence: float = 0.5,
    ) -> list[ResearchHypothesis]:
        """
        Get top N hypotheses by confidence.

        Args:
            n: Number of hypotheses to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of top hypotheses
        """
        hypotheses = self.get_all_hypotheses()

        # Filter by confidence
        filtered = [h for h in hypotheses if h.confidence >= min_confidence]

        # Sort by confidence descending
        sorted_hypotheses = sorted(filtered, key=lambda h: h.confidence, reverse=True)

        return sorted_hypotheses[:n]


class ResearchSession:
    """
    Context manager for running a research session.

    Usage:
        async with ResearchSession(config, "Transformer architectures") as session:
            await session.run(max_iterations=10)
            hypotheses = session.get_hypotheses()
    """

    def __init__(
        self,
        config: ProfileConfig,
        initial_query: str,
    ):
        """
        Initialize a research session.

        Args:
            config: Profile configuration
            initial_query: Initial research query
        """
        self.config = config
        self.initial_query = initial_query
        self._adapter = None
        self._summarizer = None
        self._master_agent = None

    async def __aenter__(self) -> ResearchSession:
        from ..semantic_scholar import SemanticScholarAdapter
        from ..config.factory import create_summarizer, create_halugate

        # Create adapter
        self._adapter = SemanticScholarAdapter()
        await self._adapter.__aenter__()

        # Create backends
        self._summarizer = create_summarizer(self.config.summarizer)
        # Enter summarizer context if it supports async context manager
        if hasattr(self._summarizer, '__aenter__'):
            await self._summarizer.__aenter__()

        halugate = create_halugate(self.config.halugate)

        # Create master agent
        self._master_agent = MasterAgent(
            search_provider=self._adapter,
            summarizer=self._summarizer,
            halugate=halugate,
            config=self.config.research_loop,
        )

        # Start the loop
        self._master_agent.start_loop(self.initial_query)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Close summarizer if it has async context
        if self._summarizer and hasattr(self._summarizer, '__aexit__'):
            await self._summarizer.__aexit__(exc_type, exc_val, exc_tb)
        if self._adapter:
            await self._adapter.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def master_agent(self) -> MasterAgent:
        """Get the master agent."""
        if not self._master_agent:
            raise RuntimeError("Session not started. Use 'async with' context manager.")
        return self._master_agent

    async def run(
        self,
        max_iterations: int = 10,
        stop_on_hypotheses: int = 0,
    ) -> LoopState:
        """Run the research session."""
        return await self.master_agent.run_auto(
            max_iterations=max_iterations,
            stop_on_hypotheses=stop_on_hypotheses,
        )

    def get_hypotheses(
        self,
        n: int = 10,
        min_confidence: float = 0.5,
    ) -> list[ResearchHypothesis]:
        """Get top hypotheses from the session."""
        return self.master_agent.get_top_hypotheses(n, min_confidence)

    def get_status(self) -> dict:
        """Get session status."""
        return self.master_agent.get_status()
