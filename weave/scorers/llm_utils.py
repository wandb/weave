from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_MODERATION_MODEL = "text-moderation-latest"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096

if TYPE_CHECKING:
    import instructor
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
    try:
        import instructor
    except ImportError:
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
    client: _LLM_CLIENTS, model_id: str, texts: str | list[str], **kwargs: Any
) -> list[list[float]]:
    client_type = type(client).__name__.lower()
    if "openai" in client_type:
        response = client.embeddings.create(model=model_id, input=texts, **kwargs)
        return [embedding.embedding for embedding in response.data]
    elif "mistral" in client_type:
        response = client.embeddings.create(model=model_id, inputs=texts, **kwargs)
        return [embedding.embedding for embedding in response.data]
    else:
        raise ValueError(f"Unsupported client type: {type(client).__name__.lower()}")
