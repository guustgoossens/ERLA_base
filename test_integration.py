"""Integration test: Search papers and summarize with LLM."""

import asyncio
import logging
import os

# Set up logging before imports
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

from src.semantic_scholar import SemanticScholarAdapter, SearchFilters
from src.llm import OpenRouterAdapter


async def main():
    query = input("Enter search query (or press Enter for default): ").strip()
    if not query:
        query = "large language models reasoning"

    print(f"\n=== Searching for papers on: '{query}' ===\n")

    # Phase 1: Search papers (relaxed filters for better results)
    async with SemanticScholarAdapter() as search:
        results = await search.search_papers(
            query,
            filters=SearchFilters(year="2020-2025"),  # Wider year range, no citation filter
            limit=5,
        )

    if not results:
        print("No papers found.")
        return

    print(f"Found {len(results)} papers:\n")
    for i, paper in enumerate(results, 1):
        print(f"{i}. {paper.title} ({paper.year})")
        print(f"   Citations: {paper.citation_count}")
        print()

    # Prepare context for LLM
    papers_context = "\n\n".join(
        f"Paper {i}: {p.title}\nYear: {p.year}\nAbstract: {p.abstract or 'N/A'}"
        for i, p in enumerate(results, 1)
    )

    # Phase 2: Summarize with LLM
    print("=== Generating summary with LLM ===\n")

    async with OpenRouterAdapter(model="arcee-ai/trinity-mini:free") as llm:
        summary = await llm.complete(
            prompt=f"""Based on these research papers, provide a brief synthesis of the current state of research on "{query}".

{papers_context}

Provide:
1. Key themes across these papers
2. Notable findings
3. Research gaps or future directions""",
            system_prompt="You are a research assistant helping synthesize academic papers. Be concise and precise.",
            temperature=0.3,
        )

    print("Summary:")
    print("-" * 40)
    print(summary)


if __name__ == "__main__":
    # Check for API keys
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY not set in .env")
        print("Get a key at: https://openrouter.ai/keys")
        exit(1)

    asyncio.run(main())
