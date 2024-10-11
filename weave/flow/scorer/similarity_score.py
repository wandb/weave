from typing import Any

from pydantic import Field
import numpy as np

import weave
from weave.flow.scorer.llm_scorer import LLMScorer
from weave.flow.scorer.llm_utils import embed


class EmbeddingSimilarityScorer(LLMScorer):
    """Check the cosine similarity distance between the model output and the target.
    
    The threshold is the minimum cosine similarity score that is considered similar.
    
    Args:
        target_column: The column to compare the model output to. Defaults to "text".
        threshold: The minimum cosine similarity score that is considered similar. Defaults to 0.5
    """
    target_column: str = Field(..., description="The column to compare the model output to")
    threshold: float = Field(0.5, description="The threshold for the similarity score")

    @weave.op
    def score(self, output: Any, dataset_row: dict) -> Any:
        if self.target_column not in dataset_row:
            raise ValueError(f"Target column {self.target_column} not found in dataset_row")
        
        target = str(dataset_row[self.target_column])  # TODO: handle if it is not a string
        model_embedding, target_embedding = self._compute_embeddings(
            output, target
        )
        return self.cosine_similarity(model_embedding, target_embedding)

    def _compute_embeddings(self, output: str, target: str) -> tuple[list[float], list[float]]:
        embeddings = embed(self.client, self.model_id, [output, target])
        return embeddings[0], embeddings[1]

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute the cosine similarity between two vectors."""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        cosine_sim = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)) 
        # TODO: check if this can be negative

        # cast to float
        score = float(cosine_sim)
        return {"similarity_score": score, "is_similar": score >= self.threshold}


if __name__ == "__main__":
    try:
        import openai, os

        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        scorer = EmbeddingSimilarityScorer(
            client=client, model_id="text-embedding-3-small", target_column="text"
        )

        dataset_row = {"text": "Whales are mammals that live in the ocean."}
        print(scorer.score(output="Dolphins are animals that live in the sea.", dataset_row=dataset_row))
    except Exception as e:
        print("Error running script:", e)