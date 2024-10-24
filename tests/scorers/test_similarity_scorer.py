import pytest
from openai import OpenAI

import weave
from weave.scorers.llm_utils import OPENAI_DEFAULT_EMBEDDING_MODEL
from weave.scorers.similarity_scorer import EmbeddingSimilarityScorer


# mock the create function
@pytest.fixture
def mock_embed(monkeypatch):
    def _mock_embed(*args, **kwargs):
        import random

        return [[random.random() for _ in range(1024)] for _ in range(2)]

    monkeypatch.setattr("weave.scorers.similarity_scorer.embed", _mock_embed)


@pytest.fixture
def similarity_scorer(mock_embed):
    return EmbeddingSimilarityScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id=OPENAI_DEFAULT_EMBEDDING_MODEL,
        threshold=0.9,
    )


def test_similarity_scorer_score(similarity_scorer):
    output = "John's favorite cheese is cheddar."
    target = "John likes various types of cheese."
    similarity_scorer.threshold = 0.0
    result = similarity_scorer.score(output=output, target=target)
    assert result["similarity_score"] > 0.0
    assert result["is_similar"] is True


def test_similarity_scorer_not_similar(similarity_scorer):
    output = "John's favorite cheese is cheddar."
    target = "John likes various types of cheese."
    similarity_scorer.threshold = 0.99
    result = similarity_scorer.score(output=output, target=target)
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
        return "He's name is John"

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[similarity_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert 0 <= result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] <= 2


@pytest.mark.asyncio
async def test_similarity_scorer_eval2(similarity_scorer):
    dataset = [
        {
            "input": "He's name is John",
            "other_col": "John likes various types of cheese.",
        },
        {
            "input": "He's name is Pepe.",
            "other_col": "Pepe likes various types of cheese.",
        },
    ]

    @weave.op
    def model(input):
        return "John likes various types of cheese."

    similarity_scorer.column_map = {"target": "other_col"}

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[similarity_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["EmbeddingSimilarityScorer"]["similarity_score"]["mean"] > 0.0
    assert 0 <= result["EmbeddingSimilarityScorer"]["is_similar"]["true_count"] <= 2
