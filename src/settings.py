"""Configuration settings for the magi research agent."""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Semantic Scholar
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"

# OpenRouter
# Available models via OpenRouter:
# - anthropic/claude-3-haiku-20240307 (fast, cheap)
# - anthropic/claude-3-5-sonnet (balanced)
# - upstage/solar-pro-3:free (free tier)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "arcee-ai/trinity-mini:free")

# Rate limiting settings
RATE_LIMIT_REQUESTS_PER_SECOND = 10  # With API key
RATE_LIMIT_REQUESTS_PER_SECOND_NO_KEY = 0.05  # Without API key (1 request per 20 seconds)

# Retry settings
MAX_RETRIES = 7
RETRY_BACKOFF_FACTOR = 2.0
