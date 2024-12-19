from __future__ import annotations

import inspect
import os
from typing import TYPE_CHECKING, Any, Optional, Union

try:
    import instructor
except ImportError:
    instructor = None

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_MODERATION_MODEL = "omni-moderation-latest"

ANTHROPIC_DEFAULT_MODEL = "claude-3-sonnet"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096

# Local model directory
LOCAL_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "weave_models")

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from google.generativeai import GenerativeModel
    from instructor.patch import InstructorChatCompletionCreate
    from mistralai import Mistral
    from openai import AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI, OpenAI

    _LLM_CLIENTS = Union[
        OpenAI,
        AsyncOpenAI,
        AzureOpenAI,
        AsyncAzureOpenAI,
        Anthropic,
        AsyncAnthropic,
        Mistral,
        GenerativeModel,
    ]
else:
    _LLM_CLIENTS = object

_LLM_CLIENTS_NAMES = (
    "OpenAI",
    "AsyncOpenAI",
    "AzureOpenAI",
    "AsyncAzureOpenAI",
    "Anthropic",
    "AsyncAnthropic",
    "Mistral",
    "GenerativeModel",
)


def instructor_client(client: _LLM_CLIENTS) -> instructor.client:
    if instructor is None:
        raise ImportError(
            "The `instructor` package is required to use LLM-powered scorers, please run `pip install instructor`"
        )

    client_type = type(client).__name__.lower()

    if "openai" in client_type:
        return instructor.from_openai(client)
    elif "anthropic" in client_type:
        return instructor.from_anthropic(client)
    elif "mistral" in client_type:
        return instructor.from_mistral(client)
    elif "generativemodel" in client_type:
        return instructor.from_gemini(
            client=client,
            mode=instructor.Mode.GEMINI_JSON,
        )
    else:
        raise ValueError(f"Unsupported client type: {client_type}")


def create(
    client: instructor.client, *args: Any, **kwargs: Any
) -> InstructorChatCompletionCreate:
    # gemini has slightly different argument namings...
    # max_tokens -> max_output_tokens
    if "generativemodel" in type(client.client).__name__.lower():
        max_output_tokens = kwargs.pop("max_tokens")
        temperature = kwargs.pop("temperature", None)
        _ = kwargs.pop("model")  # model is baked in the client
        kwargs["generation_config"] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
    return client.chat.completions.create(*args, **kwargs)


def embed(
    client: _LLM_CLIENTS, model_id: str, texts: Union[str, list[str]], **kwargs: Any
) -> list[list[float]]:
    client_type = type(client).__name__.lower()
    if "openai" in client_type:
        response = client.embeddings.create(model=model_id, input=texts, **kwargs)
        if inspect.iscoroutine(response):
            raise ValueError(
                "Async client used with sync function. Use await with async clients."
            )
        return [embedding.embedding for embedding in response.data]
    elif "mistral" in client_type:
        response = client.embeddings.create(model=model_id, inputs=texts, **kwargs)
        return [embedding.embedding for embedding in response.data]
    else:
        raise ValueError(f"Unsupported client type: {type(client).__name__.lower()}")


def set_device(device: Optional[str] = None) -> str:
    import torch

    assert device in [None, "cpu", "cuda"], "device must be None, 'cpu', or 'cuda'"
    cuda_available = torch.cuda.is_available()
    if not cuda_available and device == "cuda":
        raise ValueError("CUDA is not available")
    if device is None:
        device = "cuda" if cuda_available else "cpu"
    return device


def download_model(model_name_or_path: str, local_dir: str = "weave_models") -> str:
    from wandb import Api

    api = Api()
    art = api.artifact(
        type="model",
        name=model_name_or_path,
    )
    model_name = model_name_or_path.split("/")[-1].replace(":", "_")
    local_model_path = f"{local_dir}/{model_name}"
    art.download(local_model_path)
    return local_model_path


# Model paths for various scorers
MODEL_PATHS = {
    "hallucination_scorer": "c-metrics/weave-scorers/hallucination_scorer:v1",
    "hallucination_hhem_scorer": "c-metrics/hallucination/hallucination_hhem_scorer:v0",
    "faithfulness_scorer": "c-metrics/weave-scorers/faithfulness_scorer:v1",
    "coherence_scorer": "c-metrics/weave-scorers/coherence_scorer:v0",
    "toxicity_scorer": "c-metrics/weave-scorers/toxicity_scorer:v0",
    "bias_scorer": "c-metrics/weave-scorers/bias_scorer:v0",
    "relevance_scorer": "c-metrics/context-relevance-scorer/relevance_scorer:v0",
    "llamaguard": "c-metrics/weave-scorers/llamaguard:v0",
}


def get_model_path(model_name: str) -> str:
    """Get the full model path for a scorer."""
    if model_name in MODEL_PATHS:
        return MODEL_PATHS[model_name]
    return model_name
