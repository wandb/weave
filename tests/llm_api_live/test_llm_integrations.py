import os

import pytest

from weave.scorers.summarization_scorer import (
    SummarizationEvaluationResponse,
    SummarizationScorer,
)

# Define providers and their models
TEST_MODELS = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-haiku-20240307", "claude-3-5-sonnet-20240620"],
    "mistral": ["mistral-small-latest", "mistral-large-latest"],
    "gemini": ["gemini-1.5-flash", "gemini-1.5-pro-latest"],
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

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
    elif provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
    elif provider == "mistral":
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
    elif provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(model_name=model)
        model = "gemini"  # Adjust if necessary

    return client, model


# Generate test parameters
test_params = [
    (provider, model) for provider, models in TEST_MODELS.items() for model in models
]


@pytest.mark.parametrize("provider,model", test_params, ids=lambda p: f"{p[0]}:{p[1]}")
def test_summarization_scorer_evaluate_summary(provider, model):
    client, model_id = get_client_and_model(provider, model)

    summarization_scorer = SummarizationScorer(
        client=client,
        model_id=model_id,
        temperature=0.7,
        max_tokens=1024,
    )
    input_text = "This is the original text."
    summary_text = "This is the summary."
    result = summarization_scorer.evaluate_summary(
        input=input_text, summary=summary_text
    )
    assert isinstance(result, SummarizationEvaluationResponse)
