from typing import TYPE_CHECKING, List, Optional, Union

import instructor

from weave.trace.autopatch import autopatch

autopatch()  # fix instrucor tracing

# TODO: Gemini

OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet-20240620"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"

DEFAULT_MAX_TOKENS = 4096

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from mistralai import Mistral
    from openai import AsyncOpenAI, OpenAI

    _LLM_CLIENTS = Union[OpenAI, AsyncOpenAI, Anthropic, AsyncAnthropic, Mistral]
else:
    _LLM_CLIENTS = object


def instructor_client(client: _LLM_CLIENTS) -> instructor.client:  # type: ignore
    client_type = type(client).__name__.lower()
    if "mistral" in client_type:
        return instructor.from_mistral(client)
    elif "openai" in client_type:
        return instructor.from_openai(client)
    elif "anthropic" in client_type:
        return instructor.from_anthropic(client)
    else:
        raise ValueError(f"Unsupported client type: {client_type}")


def create(client: _LLM_CLIENTS, *args, **kwargs):  # type: ignore
    return client.chat.completions.create(*args, **kwargs)


def embed(
    client: _LLM_CLIENTS, model_id: str, texts: Union[str, List[str]], **kwargs
) -> List[List[float]]:  # type: ignore
    client_type = type(client).__name__.lower()
    if "mistral" in client_type:
        response = client.embeddings.create(model=model_id, inputs=texts, **kwargs)  # type: ignore
        return [embedding.embedding for embedding in response.data]
    elif "openai" in client_type:
        response = client.embeddings.create(model=model_id, input=texts, **kwargs)  # type: ignore
        return [embedding.embedding for embedding in response.data]
    else:
        raise ValueError(f"Unsupported client type: {type(client).__name__.lower()}")


# Helper function for dynamic imports
def import_client(provider: str) -> Optional[_LLM_CLIENTS]:  # type: ignore
    try:
        if provider == "mistral":
            from mistralai import Mistral

            return Mistral
        elif provider == "openai":
            from openai import OpenAI

            return OpenAI
        elif provider == "anthropic":
            import anthropic

            return anthropic.Anthropic
    except ImportError:
        return None
