"""Default model configurations for different LLM providers."""

import os

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_MODERATION_MODEL = "omni-moderation-latest"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

LOCAL_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "weave_models")

# Model paths for various scorers
MODEL_PATHS = {
    "hallucination_hhem_scorer": "c-metrics/weave-scorers/hallucination_hhem_scorer:v0",
    "faithfulness_scorer": "c-metrics/weave-scorers/faithfulness_scorer:v1",
    "coherence_scorer": "c-metrics/weave-scorers/coherence_scorer:v0",
    "fluency_scorer": "c-metrics/weave-scorers/fluency_scorer:v0",
    "toxicity_scorer": "c-metrics/weave-scorers/toxicity_scorer:v0",
    "bias_scorer": "c-metrics/weave-scorers/bias_scorer:v0",
    "relevance_scorer": "c-metrics/context-relevance-scorer/relevance_scorer:v0",
    "embedding_model": "c-metrics/weave-scorers/robustness_scorer_embedding_model:v0",
    "llamaguard": "c-metrics/weave-scorers/llamaguard:v0",
}
