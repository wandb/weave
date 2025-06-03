from unittest.mock import AsyncMock, patch

import jsonschema
import pydantic
import pytest
from litellm import ModelResponse
from pydantic import BaseModel

from weave import publish
from weave.scorers.llm_as_a_judge_scorer import LLMAsAJudgeScorer
from weave.trace.context.call_context import tracing_disabled
from weave.trace.weave_client import WeaveClient


@pytest.fixture(scope="module")
def disable_tracing():
    with tracing_disabled():
        yield


@pytest.fixture
def mock_acompletion():
    mock_response_data = {"choices": [{"message": {"content": '{"score": 0.9}'}}]}

    expected_model_response_object = ModelResponse.model_validate(mock_response_data)

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = expected_model_response_object
        yield mock_acompletion


class ResponseFormat(BaseModel):
    score: float


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_format",
    [{"type": "object", "properties": {"score": {"type": "number"}}}, ResponseFormat],
)
async def test_response_format(mock_acompletion, response_format):
    scorer = LLMAsAJudgeScorer(
        system_prompt="You are a judge that scores the output of a model.",
        scorer_prompt="Score the output of the model. {input} {output}",
        model="gpt-4o-mini",
        response_format=response_format,
    )

    score = await scorer.score(
        input="The input data.", output="The output of the model."
    )
    mock_acompletion.assert_called_once()

    assert score == {"score": 0.9}


class IncorrectResponseFormat(BaseModel):
    foo: float


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_format, expected_exception_type",
    [
        (
            {"type": "object", "properties": {"score": {"type": "string"}}},
            jsonschema.ValidationError,
        ),
        (IncorrectResponseFormat, pydantic.ValidationError),
    ],
)
async def test_incorrect_response_format(
    mock_acompletion, response_format, expected_exception_type
):
    scorer = LLMAsAJudgeScorer(
        system_prompt="You are a judge that scores the output of a model.",
        scorer_prompt="Score the output of the model. {input} {output}",
        model="gpt-4o-mini",
        response_format=response_format,
    )

    with pytest.raises(expected_exception_type):
        await scorer.score(input="The input data.", output="The output of the model.")


@pytest.mark.asyncio
async def test_publish_get(client: WeaveClient, mock_acompletion):
    scorer = LLMAsAJudgeScorer(
        system_prompt="You are a judge that scores the output of a model.",
        scorer_prompt="Score the output of the model. {input} {output}",
        model="gpt-4o-mini",
        response_format=ResponseFormat,
    )

    object_ref = publish(scorer)
    assert object_ref.name == "LLMAsAJudgeScorer"
    assert object_ref._digest is not None

    saved_scorer = client.get(object_ref)
    # assert saved_scorer.name == "LLMAsAJudgeScorer"
    assert (
        saved_scorer.system_prompt
        == "You are a judge that scores the output of a model."
    )
    assert saved_scorer.model == "gpt-4o-mini"
    # assert saved_scorer.response_format == ResponseFormat

    result = await saved_scorer.score(
        input="The input data.", output="The output of the model."
    )
    assert result == {"score": 0.9}
