import os

import pytest

from weave.scorers.summarization_scorer import (
    SummarizationEvaluationResponse,
    SummarizationScorer,
)

# Define providers and their models
TEST_MODELS = {
    "openai": ["openai/gpt-4o-mini", "openai/gpt-4o"],
    "anthropic": ["anthropic/claude-3-haiku-20240307", "anthropic/claude-3-5-sonnet-20240620"],
    "mistral": ["mistral/mistral-small-latest", "mistral/mistral-large-latest"],
    "gemini": ["gemini/gemini-1.5-flash", "gemini/gemini-1.5-pro"],
}


def get_client_and_model(provider, model):
    api_key_env_vars = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }

    if provider not in TEST_MODELS:
        raise ValueError(f"Unknown provider: {provider}")

    if model not in TEST_MODELS[provider]:
        raise ValueError(f"Model '{model}' not available for provider '{provider}'")

    api_key = os.getenv(api_key_env_vars[provider])
    if not api_key:
        raise OSError(
            f"API key for {provider} not found. Please set '{api_key_env_vars[provider]}' environment variable."
        )

    return model


# Generate test parameters
test_params = [
    (provider, model) for provider, models in TEST_MODELS.items() for model in models
]


@pytest.mark.parametrize("provider,model", test_params, ids=lambda p: f"{p[0]}:{p[1]}")
@pytest.mark.asyncio
async def test_summarization_scorer_evaluate_summary(provider, model):
    model_id = get_client_and_model(provider, model)

    summarization_scorer = SummarizationScorer(
        model_id=model_id,
        temperature=0.7,
        max_tokens=1024,
    )
    input_text = "This is the original text."
    summary_text = "This is the summary."
    result = await summarization_scorer.evaluate_summary(
        input=input_text, summary=summary_text
    )
    assert isinstance(result, SummarizationEvaluationResponse)
