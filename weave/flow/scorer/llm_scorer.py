from pydantic import Field, field_validator
from typing import Any, Union, Type
import numpy as np

from weave.flow.scorer.base_scorer import Scorer
from weave.flow.scorer.lightllm import LLMFactory, _LLM_CLIENT_TYPES

try:
    from openai import OpenAI, AsyncOpenAI
except:
    pass    

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

class PromptScorer(LLMScorer):
    """
    Score an LLM output based on the prompt.
    """
    system_prompt: str = Field(default="You are a helpful assistant.", description="The system prompt to use")
    user_prompt: str = Field(description="The user prompt to use")

    @field_validator('user_prompt')
    def validate_user_prompt(cls, v):
        if "{model_output}" not in v:
            raise ValueError("The user prompt must contain the `{model_output}` variable.")
        return v
    
    def score(self, model_output: Any) -> Any:
        llm = LLMFactory.create(self.client, self.model)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(model_output=model_output)},
        ]
        return llm.chat(messages=messages)

class EmbeddingSimilarityScorer(LLMScorer):
    """
    Check the embedding distance between the model output and the target.
    """
    def score(self, model_output: Any, target: Any) -> Any:
        model_embedding, target_embedding = self._compute_embeddings(model_output, target)
        return self.cosine_similarity(model_embedding, target_embedding)
    
    def _compute_embeddings(self, model_output: str, target: str) -> list[float]:
        llm = LLMFactory.create(self.client, self.model)
        return llm.embed([model_output, target])
    
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Compute the cosine similarity between two vectors.
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        cosine_sim =  np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

        # cast to float
        return float(cosine_sim)


class OpenAIModerationScorer(LLMScorer):
    "Use OpenAI moderation API to check if the model output is safe"

    def score(self, model_output: Any) -> Any:
        if not isinstance(self.client, (OpenAI, AsyncOpenAI)):
            raise ValueError("Moderation scoring only works with OpenAI or AsyncOpenAI")
        
        response = self.client.moderations.create(
            model=self.model,
            input=model_output,
        ).results[0]
        categories = {k: v for k, v in response.categories.dict().items() if v}
        return {"flagged": response.flagged, "categories": categories}
        


if __name__ == "__main__":
    try:
        import openai
        client = openai.OpenAI()
        scorer = EmbeddingSimilarityScorer(
            client=client, 
            model="text-embedding-3-small")
        print(scorer.score("I don't know", "I don't know"))
    except Exception as e:
        print("Install openai to run this script")

    try:
        import openai
        client = openai.OpenAI()
        scorer = OpenAIModerationScorer(
            client=client, 
            model="omni-moderation-latest")
        print(scorer.score("I should kill myself"))
    except Exception as e:
        print("Install openai to run this script")
    
    try:
        import openai
        client = openai.OpenAI()
        scorer = PromptScorer(
            client=client, 
            model="gpt-4o",
            system_prompt="You are a helpful assistant.",
            user_prompt="Extract the entity from this phrase: \n {model_output}")
        print(scorer.score("The cat is happy"))
    except Exception as e:
        print("Install openai to run this script")

