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
    "toxicity_scorer": "wandb/WeaveToxicityScorerV1",
    "bias_scorer": "wandb/WeaveBiasScorerV1",
    "coherence_scorer": "wandb/WeaveCoherenceScorerV1",
    "fluency_scorer": "wandb/WeaveFluencyScorerV1",
    "hallucination_scorer": "wandb/WeaveHallucinationScorerV1",
    "relevance_scorer": "wandb/WeaveContextRelevanceScorerV1",
}
