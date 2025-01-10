import pytest
from openai import OpenAI

import weave
from weave.scorers import (
    HallucinationFreeScorer,
)
from weave.scorers.hallucination_scorer import (
    HallucinationReasoning,
    HallucinationResponse,
)


# mock the create function
@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        return HallucinationResponse(
            chain_of_thought="The output is consistent with the input data.",
            reasonings=[
                HallucinationReasoning(
                    observation="My observation for this is that the output is consistent with the input data.",
                    hallucination_type="No Hallucination",
                )
            ],
            conclusion="The output is consistent with the input data.",
            has_hallucination=True,
        )

    monkeypatch.setattr("weave.scorers.hallucination_scorer.create", _mock_create)


@pytest.fixture
def hallucination_scorer(mock_create):
    return HallucinationFreeScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )


def test_hallucination_scorer_score(hallucination_scorer, mock_create):
    output = "John's favorite cheese is cheddar."
    context = "John likes various types of cheese."
    result = hallucination_scorer.score(output=output, context=context)
    # we should be able to do this validation
    _ = HallucinationResponse.model_validate(result)

    assert result["has_hallucination"] == True
    assert result["conclusion"] == "The output is consistent with the input data."
    assert len(result["reasonings"]) == 1
    assert result["reasonings"][0]["hallucination_type"] == "No Hallucination"


@pytest.mark.asyncio
async def test_hallucination_scorer_eval(hallucination_scorer):
    dataset = [
        {"context": "John likes various types of cheese."},
        {"context": "Pepe likes various types of cheese."},
    ]

    @weave.op
    def model():
        return "John's favorite cheese is cheddar."

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["HallucinationFreeScorer"]["has_hallucination"]["true_count"] == 2
    assert (
        result["HallucinationFreeScorer"]["has_hallucination"]["true_fraction"] == 1.0
    )


@pytest.mark.asyncio
async def test_hallucination_scorer_eval2(hallucination_scorer):
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

    hallucination_scorer.column_map = {"context": "input", "output": "other_col"}

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["HallucinationFreeScorer"]["has_hallucination"]["true_count"] == 2
    assert (
        result["HallucinationFreeScorer"]["has_hallucination"]["true_fraction"] == 1.0
    )
