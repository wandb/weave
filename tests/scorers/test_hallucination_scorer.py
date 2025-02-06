import json

import pytest
from pydantic import BaseModel

from weave.scorers import (
    HallucinationFreeScorer,
)
from weave.scorers.hallucination_scorer import (
    HallucinationResponse,
)


@pytest.fixture
def hallucination_scorer(monkeypatch):
    async def _mock_acompletion(*args, **kwargs):
        content = {
            "chain_of_thought": "The output is consistent with the input data.",
            "reasonings": [
                {
                    "hallucination_type": "No Hallucination",
                    "observation": "My observation for this is that the output is consistent with the input data.",
                }
            ],
            "conclusion": "The output is consistent with the input data.",
            "has_hallucination": True,
        }

        class Message(BaseModel):
            content: str

        class Choice(BaseModel):
            message: Message

        class Response(BaseModel):
            choices: list[Choice]

        return Response(choices=[Choice(message=Message(content=json.dumps(content)))])

    monkeypatch.setattr(
        "weave.scorers.hallucination_scorer.acompletion", _mock_acompletion
    )

    return HallucinationFreeScorer(
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )
    return scorer


@pytest.mark.asyncio
async def test_hallucination_scorer_score(hallucination_scorer):
    output = "John's favorite cheese is cheddar."
    context = "John likes various types of cheese."
    result = await hallucination_scorer.score(output=output, context=context)
    # we should be able to do this validation
    _ = HallucinationResponse.model_validate(result)

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "pass" in result, "Result should contain 'pass' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert result["pass"] is True, "Matching context/output should not be flagged"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"


def test_weave_hallucination_scorer_long_input(weave_hallucination_scorer):
    """Test that the scorer can handle a longer context/output without errors."""
    query = "What is the text about?"
    context, output = generate_context_and_output(
        total_tokens=5000  # moderately large for a test
    )
    result = weave_hallucination_scorer.score(
        query=query, context=context, output=output
    )

    # We only check that the result structure is valid;
    # the actual flagged/score value depends on how the model scores the content.
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "pass" in result, "Result should contain 'pass' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"
