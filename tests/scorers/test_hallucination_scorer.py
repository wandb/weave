import pytest
from openai import OpenAI

from weave.flow.scorers.hallucination_scorer import (
    HallucinationReasoning,
    HallucinationResponse,
)
from weave.scorers import (
    HallucinationFreeScorer,
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
            hallucination_free=True,
        )

    monkeypatch.setattr("weave.flow.scorers.hallucination_scorer.create", _mock_create)


@pytest.fixture
def hallucination_scorer(mock_create):
    return HallucinationFreeScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )


def test_hallucination_scorer_initialization(hallucination_scorer):
    assert isinstance(hallucination_scorer, HallucinationFreeScorer)
    assert hallucination_scorer.model_id == "gpt-4o"
    assert hallucination_scorer.temperature == 0.7
    assert hallucination_scorer.max_tokens == 4096


def test_hallucination_scorer_score(hallucination_scorer, mock_create):
    output = "John's favorite cheese is cheddar."
    context = "John likes various types of cheese."
    result = hallucination_scorer.score(output=output, context=context)
    # we should be able to do this validation
    _ = HallucinationResponse.model_validate(result)
