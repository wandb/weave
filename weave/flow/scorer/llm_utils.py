from typing import List, TypeVar, Union

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


_LLM_CLIENT_TYPES = []

try:
    from openai import AsyncOpenAI, OpenAI

    _LLM_CLIENT_TYPES.append(OpenAI)
    _LLM_CLIENT_TYPES.append(AsyncOpenAI)
except:
    pass
try:
    from anthropic import Anthropic, AsyncAnthropic

    _LLM_CLIENT_TYPES.append(Anthropic)
    _LLM_CLIENT_TYPES.append(AsyncAnthropic)
except:
    pass
try:
    from mistralai import Mistral

    _LLM_CLIENT_TYPES.append(Mistral)
except:
    pass

_LLM_CLIENTS = TypeVar(Union[tuple(_LLM_CLIENT_TYPES)])


def instructor_client(client: _LLM_CLIENTS):
    client_type = type(client).__name__.lower()
    if "mistral" in client_type:
        return instructor.from_mistral(client)
    elif "openai" in client_type:
        return instructor.from_openai(client)
    elif "anthropic" in client_type:
        return instructor.from_anthropic(client)
    else:
        raise ValueError(f"Unsupported client type: {client_type}")


def create(client: _LLM_CLIENTS, *args, **kwargs):
    return client.chat.completions.create(*args, **kwargs)


def embed(
    client: _LLM_CLIENTS, model_id: str, texts: Union[str, List[str]], **kwargs
) -> List[List[float]]:
    client_type = type(client).__name__.lower()
    if "mistral" in client_type:
        response = client.embeddings.create(model=model_id, inputs=texts, **kwargs)
        return [embedding.embedding for embedding in response.data]
    elif "openai" in client_type:
        response = client.embeddings.create(model=model_id, input=texts, **kwargs)
        return [embedding.embedding for embedding in response.data]
    else:
        raise ValueError(f"Unsupported client type: {type(client).__name__.lower()}")


# Helper function for dynamic imports
def import_client(provider: str):
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


# Example usage:
if __name__ == "__main__":
    import os

    # Mistral example
    MistralClient = import_client("mistral")
    if MistralClient:
        mistral_client = instructor_client(
            Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))
        )
        mistral_response = mistral_client.chat.completions.create(
            messages=[{"role": "user", "content": "What is the best French cheese?"}],
            model=MISTRAL_DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            response_model=str,
        )
        print("Mistral response:", mistral_response)

    # OpenAI example with system message
    OpenAIClient = import_client("openai")
    if OpenAIClient:
        openai_client = instructor_client(
            OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY"))
        )
        openai_response = openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant specialized in writing poetry.",
                },
                {
                    "role": "user",
                    "content": "Write a haiku about recursion in programming.",
                },
            ],
            model=OPENAI_DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            response_model=str,
        )
        print("OpenAI response:", openai_response)

    # Anthropic example with system message
    AnthropicClient = import_client("anthropic")
    if AnthropicClient:
        anthropic_client = instructor_client(
            AnthropicClient(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        )
        anthropic_response = anthropic_client.messages.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Claude, an AI assistant created by Anthropic.",
                },
                {"role": "user", "content": "Hello, Claude"},
            ],
            model=ANTHROPIC_DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            response_model=str,
        )
        print("Anthropic response:", anthropic_response)

    # Embedding example
    if OpenAIClient:
        openai_embed_client = OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY"))
        openai_embeddings = embed(
            openai_embed_client,
            OPENAI_DEFAULT_EMBEDDING_MODEL,
            ["Embed this sentence.", "As well as this one."],
        )
        print("OpenAI embeddings:", openai_embeddings)

    if MistralClient:
        mistral_embed_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
        mistral_embeddings = embed(
            mistral_embed_client,
            MISTRAL_DEFAULT_EMBEDDING_MODEL,
            ["Embed this sentence.", "As well as this one."],
        )
        print("Mistral embeddings:", mistral_embeddings)
