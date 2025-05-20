from collections.abc import Sequence
from typing import Any

import numpy as np
from pydantic import Field

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_EMBEDDING_MODEL
from weave.scorers.scorer_types import LLMScorer


class EmbeddingSimilarityScorer(LLMScorer):
    """
    Computes the cosine similarity between the embeddings of a model output and a target text.

    This scorer leverages the LLM's embedding capabilities (via litellm.aembedding) to generate vector
    representations for both the provided output and target. It then calculates the cosine similarity between
    these two vectors.

    Attributes:
        model_id (str): The embedding model identifier. Defaults to `OPENAI_DEFAULT_EMBEDDING_MODEL`.
        threshold (float): A float value (between -1 and 1) representing the minimum cosine similarity
            necessary to consider the two texts as similar.

    """

    model_id: str = OPENAI_DEFAULT_EMBEDDING_MODEL
    threshold: float = Field(0.5, description="The threshold for the similarity score")

    @weave.op
    async def score(self, *, output: str, target: str, **kwargs: Any) -> Any:
        # Ensure the threshold is within the valid range for cosine similarity.
        assert (
            self.threshold >= -1 and self.threshold <= 1
        ), "`threshold` should be between -1 and 1"

        model_embedding, target_embedding = await self._compute_embeddings(
            output, target
        )
        return self._cosine_similarity(model_embedding, target_embedding)

    async def _compute_embeddings(
        self, output: str, target: str
    ) -> tuple[list[float], list[float]]:
        embeddings = await self._aembedding(self.model_id, [output, target])
        return embeddings.data[0]["embedding"], embeddings.data[1]["embedding"]

    def _cosine_similarity(self, vec1: Sequence[float], vec2: Sequence[float]) -> dict:
        """Compute the cosine similarity between two vectors.

        Args:
            vec1: The first vector.
            vec2: The second vector.

        Returns:
            A dictionary containing:
                - "similarity_score": The cosine similarity as a float.
                - "is_similar": A boolean indicating if the similarity_score is greater than or equal to the threshold.
        """
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        cosine_sim = np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2))
        cosine_sim = float(cosine_sim)
        return {
            "similarity_score": cosine_sim,
            "is_similar": cosine_sim >= self.threshold,
        }
