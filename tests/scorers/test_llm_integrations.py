import os

import pytest

from weave.scorers.summarization_scorer import (
    SummarizationEvaluationResponse,
    SummarizationScorer,
)

# Centralized dictionary for providers with their associated models and API key environment variable.
PROVIDERS = {
    "openai": {
        "models": ["openai/gpt-4o"],
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "models": ["anthropic/claude-3-5-sonnet-20240620"],
        "env_key": "ANTHROPIC_API_KEY",
    },
    "mistral": {
        "models": ["mistral/mistral-large-latest"],
        "env_key": "MISTRAL_API_KEY",
    },
    "gemini": {
        "models": ["gemini/gemini-1.5-pro"],
        "env_key": "GOOGLE_API_KEY",
    },
}

# Generate test parameters by iterating over each provider and its associated models.
test_params = [
    (provider, model) for provider, cfg in PROVIDERS.items() for model in cfg["models"]
]


@pytest.mark.parametrize("provider,model", test_params, ids=lambda p: f"{p[0]}:{p[1]}")
@pytest.mark.asyncio
async def test_summarization_scorer_evaluate_summary(provider, model):
    # Retrieve the environment variable key for the provider
    env_key = PROVIDERS[provider]["env_key"]

    # Check for the corresponding API key; skip the test if it's not present.
    if not os.getenv(env_key):
        pytest.skip(f"API key for {provider} not found. Skipping test.")

    # Use the model directly as the model_id
    model_id = model

    summarization_scorer = SummarizationScorer(
        model_id=model_id,
        temperature=0.7,
        max_tokens=1024,
    )
    input_text = "The wolf is lonely in the forest. He is not happy that the fox is not with him."
    summary_text = "Wolf is lonely and missing the fox."
    result = await summarization_scorer.evaluate_summary(
        input=input_text, summary=summary_text
    )
    assert isinstance(result, SummarizationEvaluationResponse)