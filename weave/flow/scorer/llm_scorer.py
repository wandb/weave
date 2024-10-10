from pydantic import Field, field_validator
from typing import Any, Union, Type
import numpy as np

from weave.flow.scorer.base_scorer import Scorer

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

_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

class LLMScorer(Scorer):
    """
    Score an LLM output.
    """
    client: Any = Field(description="The LLM client to use, has to be instantiated with an api_key")
    model: str = Field(description="The model to use")

    @field_validator('client')
    def validate_client(cls, v):
        if not any(isinstance(v, client_type) for client_type in _LLM_CLIENT_TYPES):
            raise ValueError(f"Invalid client type. Expected one of {_LLM_CLIENT_TYPES}, got {type(v)}")
        return v

class EmbeddingScorer(LLMScorer):
    """
    Check the embedding distance between the model output and the target.
    """
    def score(self, model_output: Any, target: Any) -> Any:
        if not isinstance(self.client, (OpenAI, AsyncOpenAI)):
            raise ValueError("Embedding scoring only works with OpenAI or AsyncOpenAI")
        
        # Use AsyncOpenAI if available, otherwise use OpenAI
        client = self.client if isinstance(self.client, AsyncOpenAI) else self.client
        
        model_embedding = client.embeddings.create(
            input=model_output, model=self.model).data[0].embedding
        target_embedding = client.embeddings.create(
            input=target, model=self.model).data[0].embedding
        
        return self.cosine_similarity(model_embedding, target_embedding)
    

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Compute the cosine similarity between two vectors.
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        cosine_sim =  np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

        # cast to float
        return float(cosine_sim)



if __name__ == "__main__":
    try:
        import openai
        client = openai.OpenAI()
        scorer = EmbeddingScorer(
            client=client, 
            model="text-embedding-3-small")
        print(scorer.score("I don't know", "I don't know"))
    except Exception as e:
        print("Install openai to run this script")
    

