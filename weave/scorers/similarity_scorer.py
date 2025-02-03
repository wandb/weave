from typing import Any, TypedDict

import numpy as np
from litellm import aembedding
from pydantic import Field

import weave
from weave.flow.scorer import Scorer
from weave.scorers.llm_utils import OPENAI_DEFAULT_EMBEDDING_MODEL


class EmbeddingSimilarityScorerOutput(TypedDict):
    """Output type for EmbeddingSimilarityScorer."""

    similarity_score: float
    is_similar: bool


class EmbeddingSimilarityScorer(Scorer):
    """Check the cosine similarity distance between the model output and the target.

    The threshold is the minimum cosine similarity score that is considered similar.

    Args:
        model_id: The model to use for embedding. Defaults to `text-embedding-3-small`.
        threshold: The minimum cosine similarity score that is considered similar. Defaults to 0.5
    """

    model_id: str = OPENAI_DEFAULT_EMBEDDING_MODEL
    threshold: float = Field(0.5, description="The threshold for the similarity score")

    @weave.op
    async def score(self, output: Any, target: str) -> EmbeddingSimilarityScorerOutput:
        assert (
            self.threshold >= -1 and self.threshold <= 1
        ), "`threshold` should be between -1 and 1"
        model_embedding, target_embedding = await self._compute_embeddings(
            output, target
        )
        return self.cosine_similarity(model_embedding, target_embedding)

    async def _compute_embeddings(
        self, output: Any, target: str
    ) -> tuple[list[float], list[float]]:
        embeddings = await aembedding(self.model_id, [output, target])
        return embeddings.data[0]["embedding"], embeddings.data[1]["embedding"]

    def cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> EmbeddingSimilarityScorerOutput:
        """Compute the cosine similarity between two vectors."""
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        cosine_sim = np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2))
        cosine_sim = float(cosine_sim)
        return {
            "similarity_score": cosine_sim,
            "is_similar": cosine_sim >= self.threshold,
        }
