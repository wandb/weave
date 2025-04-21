"""Default model configurations for different LLM providers."""

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_MODERATION_MODEL = "omni-moderation-latest"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

# Model paths for various scorers
MODEL_PATHS = {
    "toxicity_scorer": "c-metrics/weave-scorers/toxicity_scorer:v0",
    "bias_scorer": "c-metrics/weave-scorers/bias_scorer:v0",
    "coherence_scorer": "c-metrics/weave-scorers/coherence_scorer:v0",
    "fluency_scorer": "c-metrics/weave-scorers/fluency_scorer:v0",
    "hallucination_scorer": "c-metrics/weave-scorers/hallucination_hhem_scorer:v0",
    "relevance_scorer": "c-metrics/weave-scorers/relevance_scorer:v0",
}
