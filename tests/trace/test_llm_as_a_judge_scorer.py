from unittest.mock import patch

import pytest

import weave
from weave.prompt.prompt import MessagesPrompt
from weave.scorers import LLMAsAJudgeScorer
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
)


def test_publish_and_load_scorer_with_prompt_ref(weave_active):
    """Test that LLMAsAJudgeScorer with a MessagesPrompt ref can be published and loaded.

    When the scorer is loaded via weave.get(), the scoring_prompt ref string
    is automatically resolved to the actual MessagesPrompt object.
    """
    # Create and publish a MessagesPrompt
    prompt = MessagesPrompt(
        messages=[
            {
                "role": "user",
                "content": "Inputs: {inputs}. Output: {output}. Is this correct?",
            }
        ]
    )
    prompt_ref = weave.publish(prompt)
    prompt_uri = str(prompt_ref.uri)

    # Create scorer with prompt URI string
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt=prompt_uri,
    )
    assert scorer.scoring_prompt == prompt_uri

    # Publish and retrieve - ref should be resolved
    scorer_ref = weave.publish(scorer)
    loaded_scorer = weave.get(scorer_ref.uri)

    assert isinstance(loaded_scorer, LLMAsAJudgeScorer)
    assert isinstance(loaded_scorer.scoring_prompt, MessagesPrompt)
    assert len(loaded_scorer.scoring_prompt.messages) == 1


# score() renders the scoring prompt (string or MessagesPrompt) into the
# message list passed to the model's predict, then returns predict's result.
@pytest.mark.parametrize(
    ("scoring_prompt", "score_kwargs", "mock_result", "expected_messages"),
    [
        (
            "Output: {output}",
            {"output": "hello"},
            {"score": 1.0},
            [{"role": "user", "content": "Output: hello"}],
        ),
        (
            MessagesPrompt(
                messages=[
                    {"role": "system", "content": "You are a {judge_type} judge."},
                    {"role": "user", "content": "Expected: {expected}, Got: {output}"},
                ]
            ),
            {"output": "4", "expected": "4", "judge_type": "math"},
            {"score": 0.95},
            [
                {"role": "system", "content": "You are a math judge."},
                {"role": "user", "content": "Expected: 4, Got: 4"},
            ],
        ),
    ],
    ids=["string-prompt", "messages-prompt-with-vars"],
)
def test_score_renders_prompt_into_predict_messages(
    scoring_prompt, score_kwargs, mock_result, expected_messages
):
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt=scoring_prompt,
    )
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        result = scorer.score(**score_kwargs)

    assert result == mock_result
    mock_predict.assert_called_once()
    assert mock_predict.call_args[0][0] == expected_messages
