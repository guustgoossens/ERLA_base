#!/usr/bin/env python
"""Run research with realtime Convex streaming.

This script runs the research agent with events streamed to Convex
for realtime visualization in the Three.js frontend.

Usage:
    uv run python run_research_live.py "transformer attention mechanisms"
    uv run python run_research_live.py "quantum computing applications" --iterations 10
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from both .env and .env.local
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")
load_dotenv(project_root / ".env.local", override=True)

from src.config import load_config
from src.orchestration import ResearchSession
from src.semantic_scholar import SearchFilters
from src.storage import ConvexClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(
    query: str,
    profile: str = "research-fast",
    max_iterations: int = 5,
    use_managing_agent: bool = False,
    filters: SearchFilters | None = None,
) -> None:
    """Run a research session with Convex streaming.

    Args:
        query: Research query to explore
        profile: Configuration profile name
        max_iterations: Maximum iterations to run
        use_managing_agent: Whether to use Claude Opus for intelligent branch splitting
        filters: Optional search filters for paper retrieval
    """
    # Initialize Convex client
    convex = ConvexClient()
    await convex.connect()

    if not convex.enabled:
        logger.warning(
            "Convex not configured. Set CONVEX_URL in .env.local to enable streaming."
        )
        logger.info("Continuing without realtime streaming...")

    try:
        # Load configuration
        config = load_config(profile)
        logger.info(f"Using profile: {profile}")
        if use_managing_agent:
            logger.info("Managing agent enabled (Claude Opus for intelligent splitting)")

        # Run research session
        async with ResearchSession(
            config,
            query,
            convex_client=convex,
            use_managing_agent=use_managing_agent,
            filters=filters,
        ) as session:
            logger.info(f"Started research session: {session.loop_id}")
            logger.info(f"Query: {query}")

            if convex.enabled:
                logger.info(f"Convex session created: {convex.session_id}")
                logger.info("View realtime updates at: https://dashboard.convex.dev")

            # Run research
            state = await session.run(max_iterations=max_iterations)

            # Print results
            logger.info("\n" + "=" * 60)
            logger.info("Research completed!")
            logger.info("=" * 60)

            status = session.get_status()
            logger.info(f"Total branches: {status.get('total_branches', 0)}")
            logger.info(f"Total papers: {status.get('total_papers', 0)}")
            logger.info(f"Total summaries: {status.get('total_summaries', 0)}")
            logger.info(f"Total hypotheses: {status.get('total_hypotheses', 0)}")

            # Print top hypotheses
            hypotheses = session.get_hypotheses(n=5, min_confidence=0.3)
            if hypotheses:
                logger.info("\nTop Hypotheses:")
                for i, h in enumerate(hypotheses, 1):
                    logger.info(f"  {i}. [{h.confidence:.2f}] {h.text[:100]}...")

    finally:
        await convex.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run research with Convex streaming"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="transformer attention mechanisms",
        help="Research query to explore",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default="research-fast",
        help="Configuration profile (default: research-fast)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5,
        help="Maximum iterations (default: 5)",
    )
    parser.add_argument(
        "--use-managing-agent",
        "-m",
        action="store_true",
        help="Use Claude Opus for intelligent branch splitting decisions",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Filter papers published on or after this date (YYYY-MM-DD, YYYY-MM, or YYYY)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Filter papers published on or before this date (YYYY-MM-DD, YYYY-MM, or YYYY)",
    )
    parser.add_argument(
        "--year",
        "-y",
        type=str,
        help="[Deprecated] Year filter (e.g., '2023-2024'). Use --start-date/--end-date instead.",
    )

    args = parser.parse_args()

    # Build filters from CLI args
    filters = None
    if args.start_date or args.end_date:
        filters = SearchFilters(start_date=args.start_date, end_date=args.end_date)
    elif args.year:
        filters = SearchFilters(year=args.year)

    try:
        asyncio.run(main(args.query, args.profile, args.iterations, args.use_managing_agent, filters))
    except KeyboardInterrupt:
        logger.info("\nResearch interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Research failed: {e}")
        sys.exit(1)
