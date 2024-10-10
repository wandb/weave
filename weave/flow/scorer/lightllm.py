from abc import ABC, abstractmethod
from typing import List, Dict, Union, Any


OPENAI_DEFAULT_MODEL = "gpt-4o"
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet-20240620"

MISTRAL_DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_DEFAULT_EMBEDDING_MODEL = "mistral-embed"


_LLM_CLIENT_TYPES = []

try:
    from openai import OpenAI, AsyncOpenAI
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

_LLM_CLIENTS = Union[tuple(_LLM_CLIENT_TYPES)]

class BaseLLM(ABC):
    def __init__(self, client: Any, model_id: str):
        self.client = client
        self.model_id = model_id

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass

    @abstractmethod
    async def achat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass

    @abstractmethod
    def embed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        pass

    @abstractmethod
    async def aembed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        pass

class MistralLLM(BaseLLM):
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = self.client.chat.complete(model=self.model_id, messages=messages, **kwargs)
        return response.choices[0].message.content

    async def achat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = await self.client.chat.complete(model=self.model_id, messages=messages, **kwargs)
        return response.choices[0].message.content

    def embed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        response = self.client.embeddings.create(model=self.model_id, inputs=texts)
        return [embedding.embedding for embedding in response.data]

    async def aembed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        response = await self.client.embeddings.create(model=self.model_id, inputs=texts)
        return [embedding.embedding for embedding in response.data]

class OpenAILLM(BaseLLM):
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = self.client.chat.completions.create(model=self.model_id, messages=messages, **kwargs)
        return response.choices[0].message.content

    async def achat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = await self.client.chat.completions.create(model=self.model_id, messages=messages, **kwargs)
        return response.choices[0].message.content

    def embed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        response = self.client.embeddings.create(input=texts, model=self.model_id)
        return [data.embedding for data in response.data]

    async def aembed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]
        response = await self.client.embeddings.create(input=texts, model=self.model_id)
        return [data.embedding for data in response.data]

class AnthropicLLM(BaseLLM):
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        system_message = next((msg['content'] for msg in messages if msg['role'] == 'system'), None)
        user_messages = [msg for msg in messages if msg['role'] != 'system']
        response = self.client.messages.create(
            model=self.model_id,
            messages=user_messages,
            system=system_message,
            max_tokens=2048,
            **kwargs
        )
        return response.content

    async def achat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        system_message = next((msg['content'] for msg in messages if msg['role'] == 'system'), None)
        user_messages = [msg for msg in messages if msg['role'] != 'system']
        response = await self.client.messages.create(
            model=self.model_id,
            messages=user_messages,
            system=system_message,
            max_tokens=2048,
            **kwargs
        )
        return response.content

    def embed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        return [[0.0]]  # Anthropic doesn't support embeddings

    async def aembed(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        return [[0.0]]  # Anthropic doesn't support embeddings

class LLMFactory:
    @staticmethod
    def create(client: Any, model_id: str) -> BaseLLM:
        client_type = type(client).__name__.lower()
        if "mistral" in client_type:
            return MistralLLM(client, model_id)
        elif "openai" in client_type:
            return OpenAILLM(client, model_id)
        elif "anthropic" in client_type:
            return AnthropicLLM(client, model_id)
        else:
            raise ValueError(f"Unsupported client type: {client_type}")

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
    import asyncio

    # Mistral example
    MistralClient = import_client("mistral")
    if MistralClient:
        mistral_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
        mistral_llm = LLMFactory.create(mistral_client, MISTRAL_DEFAULT_MODEL)
        mistral_response = mistral_llm.chat([{"role": "user", "content": "What is the best French cheese?"}])
        print("Mistral response:", mistral_response)

    # OpenAI example with system message
    OpenAIClient = import_client("openai")
    if OpenAIClient:
        openai_client = OpenAIClient()
        openai_llm = LLMFactory.create(openai_client, OPENAI_DEFAULT_MODEL)
        openai_response = openai_llm.chat([
            {"role": "system", "content": "You are a helpful assistant specialized in writing poetry."},
            {"role": "user", "content": "Write a haiku about recursion in programming."}
        ])
        print("OpenAI response:", openai_response)

    # Anthropic example with system message
    AnthropicClient = import_client("anthropic")
    if AnthropicClient:
        anthropic_client = AnthropicClient(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        anthropic_llm = LLMFactory.create(anthropic_client, ANTHROPIC_DEFAULT_MODEL)
        anthropic_response = anthropic_llm.chat([
            {"role": "system", "content": "You are Claude, an AI assistant created by Anthropic."},
            {"role": "user", "content": "Hello, Claude"}
        ])
        print("Anthropic response:", anthropic_response)

    # Embedding example
    if MistralClient:
        mistral_embed_client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))
        mistral_embed_llm = LLMFactory.create(mistral_embed_client, MISTRAL_DEFAULT_EMBEDDING_MODEL)
        mistral_embeddings = mistral_embed_llm.embed(["Embed this sentence.", "As well as this one."])
        print("Mistral embeddings:", mistral_embeddings)

    # Async example with system message
    async def async_example():
        if OpenAIClient:
            from openai import AsyncOpenAI
            openai_async_client = AsyncOpenAI()
            openai_async_llm = LLMFactory.create(openai_async_client, OPENAI_DEFAULT_MODEL)
            openai_async_response = await openai_async_llm.achat([
                {"role": "system", "content": "You are a philosopher AI assistant."},
                {"role": "user", "content": "What's the meaning of life?"}
            ])
            print("OpenAI async response:", openai_async_response)

    asyncio.run(async_example())
