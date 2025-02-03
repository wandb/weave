try:
    from litellm import amoderation
except ImportError:
    raise ImportError(
        "litellm is not installed. Please install it with `pip install litellm`."
    )

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_MODERATION_MODEL = "text-moderation-latest"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

