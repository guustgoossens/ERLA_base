# ERLA — Exploratory Recursive Language Agents

## Inspiration

Computers used to be machines of wonder. Today we have models capable of reasoning and synthesis that would have seemed like magic a decade ago, yet computing increasingly feels as though it's stuck on rails. Ironically, the very models that could enable open-ended exploration are held back by their tendency to hallucinate.

ERLA (Exploratory Recursive Language Agents) is our attempt to bring the sense of wonder back to computing—safely. We built a system that lets AI explore scientific literature recursively and autonomously, whilst maintaining epistemic integrity at every step.

## What it does

ERLA is a recursive research agent designed to explore scientific literature whilst remaining epistemically grounded. Rather than a monolithic system, ERLA orchestrates a fleet of parallel research units called **Scouts** (implemented as Branches).

Each Scout can:
1. **Search** Semantic Scholar for relevant papers
2. **Summarise** papers using LLMs
3. **Validate** every summary through token-level hallucination detection
4. **Generate** research hypotheses from validated findings

The **Master Agent** monitors Scout progress and decides when to spawn new Scouts based on context utilisation and research heuristics, enabling recursive parallel exploration of the research space.

The key innovation is our **Captain**: a pure Python implementation of vLLM's HaluGate protocol that validates every generated token against source material using a 3-stage pipeline (Sentinel → Detector → Explainer). Only summaries achieving ≥95% groundedness pass through, ensuring epistemic integrity throughout the research process.

## How we built it

**Architecture** - 3-layer recursive system:
- **Inner Loop**: Atomic search-summarise-validate unit
- **Iteration Loop**: Manages iterations per branch with context tracking
- **Master Agent**: Orchestrates branch lifecycle, splitting, and pruning

**HaluGate Implementation**:
We implemented HaluGate entirely in pure Python, eliminating the Docker/vLLM dependency:
1. **Sentinel**: Fact-check classifier determines if validation is needed
2. **Detector**: LettuceDetect for token-level hallucination detection
3. **Explainer**: NLI-based verification to filter false positives

**Key Technologies**:
- Semantic Scholar API for paper search and full-text extraction
- Anthropic Claude for summarisation via OpenRouter
- LettuceDetect + ModernBERT-NLI for validation pipeline
- PyMuPDF for PDF parsing
- FastAPI + Convex for real-time research visualisation

**Complete Library Stack**:

*Core Dependencies:*
- **httpx** (≥0.27) - Async HTTP client for API calls
- **pydantic** (≥2.0) - Data validation and settings management
- **python-dotenv** (≥1.0) - Environment configuration
- **pymupdf** (≥1.24) - PDF parsing and text extraction
- **openai** (≥1.0) - OpenRouter API client (OpenAI-compatible)
- **anthropic** (≥0.40) - Anthropic API client for Claude
- **lettucedetect** (≥0.1.8) - Token-level hallucination detection
- **transformers** (≥4.40) - HuggingFace transformers for NLI models
- **torch** (≥2.0) - PyTorch backend for ML models
- **pyyaml** (≥6.0) - YAML configuration loading
- **fastapi** (≥0.115) - HTTP server framework for HaluGate service
- **uvicorn** (≥0.34) - ASGI server for FastAPI

*Development Dependencies:*
- **pytest** (≥9.0.2) - Testing framework
- **pytest-asyncio** (≥1.3.0) - Async test support

**Branch System**:
The Master Agent decides when to spawn child Scouts based on context utilisation hitting 80%, using intelligent splitting strategies (by_field, by_topic, by_time) to divide the research space coherently.

## Challenges we ran into

**Hallucination at Scale**: With embarrassingly parallel Scout spawning, a single hallucination could cascade through the entire research tree. We solved this by enforcing validation at the atomic level—no summary enters the knowledge base without passing HaluGate.

**Context Window Management**: Tracking context usage across recursive branches whilst deciding optimal split points required careful estimation and strategy selection.

**Pure Python HaluGate**: Replicating vLLM's Docker-based HaluGate in pure Python required understanding the full 3-stage pipeline and correctly chaining Sentinel → LettuceDetect → NLI models with proper filtering.

**Coordination Without Centralisation**: Enabling Scouts to explore autonomously whilst maintaining global coherence required careful state management and branch lifecycle tracking.

## Accomplishments that we're proud of

- **Token-level truth**: Pure Python HaluGate achieving 95%+ groundedness on validated summaries
- **Intelligent recursion**: Master Agent orchestrates Scout spawning based on context thresholds and research heuristics, deciding optimal split strategies (by_field, by_topic, by_time) rather than hard-coded rules
- **Epistemic compartmentalisation**: Every Scout maintains its own validated knowledge base, preventing hallucination propagation across the research tree
- **Full pipeline**: From user query → recursive search → validated summaries → hypotheses → visualisation
- **Research velocity**: Parallel summarisation with configurable concurrency (up to 5 concurrent paper validations per Scout)

## What we learned

**Epistemic integrity matters more than the findings themselves.** Knowing how much you can trust a model's output is as important as the output itself.

Through compartmentalisation, we shifted from "better prompting" to **maintenance and development of epistemic integrity**. By validating at the atomic level (individual summaries) rather than system level (final report), we enable the best parts of emergent parallel exploration whilst ensuring every single token has foundation in scientific context.

The recursive Scout architecture taught us that **homogeneous agents with simple rules can produce complex, valuable behaviour** when given the right tools and constraints. You don't need a complex hierarchy—just good primitives and validation.

## What's next for ERLA

**Citation graph traversal**: Currently Scouts split by topic/time/field. Next: follow citation chains to discover foundational papers and recent developments automatically.

**Big Loop 2**: Implement hypothesis-seeded research loops where top hypotheses from one loop become queries for a deeper investigation phase.

**Cross-branch synthesis**: Enable Scouts to share insights across branches, allowing discoveries in one subtree to inform exploration in another.

**Adaptive groundedness thresholds**: Dynamic thresholds based on research phase—stricter for factual claims, relaxed for hypothesis generation.

**Academic paper generation**: Synthesise validated findings into properly cited academic papers with automatic bibliography generation from Semantic Scholar metadata.
