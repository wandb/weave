import pytest
import random
from pydantic import BaseModel

import weave
from weave.scorers.llm_utils import OPENAI_DEFAULT_EMBEDDING_MODEL
from weave.scorers.similarity_scorer import (
    EmbeddingSimilarityScorer,
)

# mock the aembedding function
@pytest.fixture
def mock_aembedding(monkeypatch):
    async def _mock_aembedding(*args, **kwargs):
        class Response(weave.Model):
            data: list[dict]

        return Response(data=[
                {"embedding": [random.random() for _ in range(1024)]}
                for _ in range(2)
            ])

    monkeypatch.setattr("weave.scorers.similarity_scorer.aembedding", _mock_aembedding)


@pytest.fixture
def similarity_scorer(mock_aembedding):
    return EmbeddingSimilarityScorer(
        model_id=OPENAI_DEFAULT_EMBEDDING_MODEL,
        threshold=0.5,
    )


@pytest.mark.asyncio
async def test_similarity_scorer_score(similarity_scorer):
    output = "John's favorite cheese is cheddar."
    target = "John likes various types of cheese."
    similarity_scorer.threshold = 0.0
    result = await similarity_scorer.score(output=output, target=target)
    # TypedDict ensures type safety
    assert isinstance(result, dict)
    assert isinstance(result["similarity_score"], float)
    assert isinstance(result["is_similar"], bool)
    assert result["similarity_score"] > 0.0
    assert result["is_similar"] is True


@pytest.mark.asyncio
async def test_similarity_scorer_not_similar(similarity_scorer):
    output = "John's favorite cheese is cheddar."
    target = "John likes various types of cheese."
    similarity_scorer.threshold = 0.99
    result = await similarity_scorer.score(output=output, target=target)
    # TypedDict ensures type safety
    assert isinstance(result, dict)
    assert isinstance(result["similarity_score"], float)
    assert isinstance(result["is_similar"], bool)
    assert result["similarity_score"] < 0.99
    assert result["is_similar"] is False


@pytest.mark.asyncio
async def test_similarity_scorer_eval(similarity_scorer):
    dataset = [
        {"target": "John likes various types of cheese."},
        {"target": "Pepe likes various types of cheese."},
    ]

    @weave.op
    def model():
        return "John's favorite cheese is cheddar."

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[similarity_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] == 2
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_fraction"] == 1.0


@pytest.mark.asyncio
async def test_similarity_scorer_eval2(similarity_scorer):
    dataset = [
        {
            "input": "John likes various types of cheese.",
            "other_col": "John's favorite cheese is cheddar.",
        },
        {
            "input": "Pepe likes various types of cheese.",
            "other_col": "Pepe's favorite cheese is gouda.",
        },
    ]

    @weave.op
    def model(input):
        return "The person's favorite cheese is cheddar."

    similarity_scorer.column_map = {"target": "input", "output": "other_col"}

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[similarity_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] == 2
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_fraction"] == 1.0