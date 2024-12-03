from typing import Any

import numpy as np
from pydantic import Field

import weave
from weave.scorers.llm_scorer import LLMScorer
from weave.scorers.llm_utils import OPENAI_DEFAULT_EMBEDDING_MODEL, embed


class EmbeddingSimilarityScorer(LLMScorer):
    """Check the cosine similarity distance between the model output and the target.

    The threshold is the minimum cosine similarity score that is considered similar.

    Args:
        threshold: The minimum cosine similarity score that is considered similar. Defaults to 0.5
    """

    threshold: float = Field(0.5, description="The threshold for the similarity score")
    model_id: str = OPENAI_DEFAULT_EMBEDDING_MODEL

    @weave.op
    def score(self, output: str, target: str) -> Any:
        assert (
            self.threshold >= -1 and self.threshold <= 1
        ), "`threshold` should be between -1 and 1"
        model_embedding, target_embedding = self._compute_embeddings(output, target)
        return self.cosine_similarity(model_embedding, target_embedding)

    def _compute_embeddings(
        self, output: str, target: str
    ) -> tuple[list[float], list[float]]:
        embeddings = embed(self.client, self.model_id, [output, target])
        return embeddings[0], embeddings[1]

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> dict:
        """Compute the cosine similarity between two vectors."""
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        cosine_sim = np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2))
        cosine_sim = float(cosine_sim)
        return {
            "similarity_score": cosine_sim,
            "is_similar": cosine_sim >= self.threshold,
        }
