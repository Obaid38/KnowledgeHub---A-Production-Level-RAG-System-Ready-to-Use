import os

from ai.config.config_env import IS_LOCAL

# Semantic cache - Redis-backed; disabled locally
SEMANTIC_CACHE_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "false" if IS_LOCAL else "true").lower() == "true"
SEMANTIC_CACHE_TTL_SECONDS = int(os.getenv("SEMANTIC_CACHE_TTL_SECONDS", "3600"))
SEMANTIC_CACHE_SIMILARITY = float(os.getenv("SEMANTIC_CACHE_SIMILARITY", "0.95"))

# Faithfulness check - rule-based; disabled locally
FAITHFULNESS_CHECK_ENABLED = os.getenv("FAITHFULNESS_CHECK_ENABLED", "false" if IS_LOCAL else "true").lower() == "true"

# Confidence bands
CONFIDENCE_BAND_HIGH = float(os.getenv("CONFIDENCE_BAND_HIGH", "0.85"))
CONFIDENCE_BAND_MEDIUM = float(os.getenv("CONFIDENCE_BAND_MEDIUM", "0.70"))
CONFIDENCE_BAND_LOW = float(os.getenv("CONFIDENCE_BAND_LOW", "0.55"))

# Confidence weights
CONFIDENCE_WEIGHT_RETRIEVAL = float(os.getenv("CONFIDENCE_WEIGHT_RETRIEVAL", "0.60"))
CONFIDENCE_WEIGHT_CLASSIFIER = float(os.getenv("CONFIDENCE_WEIGHT_CLASSIFIER", "0.25"))
CONFIDENCE_WEIGHT_FAITHFULNESS = float(os.getenv("CONFIDENCE_WEIGHT_FAITHFULNESS", "0.15"))
CONFIDENCE_STALE_PENALTY = float(os.getenv("CONFIDENCE_STALE_PENALTY", "0.05"))

# Prompt assembly
PROMPT_TOKEN_BUDGET = int(os.getenv("PROMPT_TOKEN_BUDGET", "6000"))
PROMPT_TRIM_ENABLED = os.getenv("PROMPT_TRIM_ENABLED", "true").lower() == "true"

# Cache eligibility
CACHE_ELIGIBLE_MIN_CONFIDENCE = float(os.getenv("CACHE_ELIGIBLE_MIN_CONFIDENCE", "0.80"))
