import random

import pytest

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_EMBEDDING_MODEL
from weave.scorers.similarity_scorer import (
    EmbeddingSimilarityScorer,
)


# mock the aembedding function
@pytest.fixture
def mock_aembedding(monkeypatch):
    async def _mock_aembedding(*args, **kwargs):
        class Response(weave.Model):
            data: list[dict]

        return Response(
            data=[
                {"embedding": [random.random() for _ in range(1024)]} for _ in range(2)
            ]
        )

    monkeypatch.setattr(
        "weave.scorers.similarity_scorer.EmbeddingSimilarityScorer._aembedding",
        _mock_aembedding,
    )


@pytest.fixture
def similarity_scorer(mock_aembedding):
    return EmbeddingSimilarityScorer(
        model_id=OPENAI_DEFAULT_EMBEDDING_MODEL,
        threshold=0.5,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("threshold", "expected_is_similar"),
    [(0.0, True), (0.99, False)],
)
async def test_similarity_scorer_score(
    similarity_scorer, threshold, expected_is_similar
):
    output = "John's favorite cheese is cheddar."
    target = "John likes various types of cheese."
    similarity_scorer.threshold = threshold
    result = await similarity_scorer.score(output=output, target=target)
    # TypedDict ensures type safety
    assert isinstance(result, dict)
    assert isinstance(result["similarity_score"], float)
    assert isinstance(result["is_similar"], bool)
    if expected_is_similar:
        assert result["similarity_score"] > threshold
    else:
        assert result["similarity_score"] < threshold
    assert result["is_similar"] is expected_is_similar


@pytest.mark.asyncio
async def test_similarity_scorer_eval(similarity_scorer):
    """Covers both the default `target` column and a remapped column via column_map."""
    dataset = [
        {"target": "John likes various types of cheese."},
        {"target": "Pepe likes various types of cheese."},
    ]

    @weave.op
    def model():
        return "John's favorite cheese is cheddar."

    evaluation = weave.Evaluation(dataset=dataset, scorers=[similarity_scorer])
    result = await evaluation.evaluate(model)
    assert result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] == 2
    assert result["EmbeddingSimilarityScorer"]["is_similar"]["true_fraction"] == 1.0

    mapped_dataset = [
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
    def mapped_model(input):
        return "The person's favorite cheese is cheddar."

    similarity_scorer.column_map = {"target": "other_col"}

    mapped_evaluation = weave.Evaluation(
        dataset=mapped_dataset, scorers=[similarity_scorer]
    )
    mapped_result = await mapped_evaluation.evaluate(mapped_model)
    assert mapped_result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert mapped_result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] == 2
    assert (
        mapped_result["EmbeddingSimilarityScorer"]["is_similar"]["true_fraction"] == 1.0
    )
