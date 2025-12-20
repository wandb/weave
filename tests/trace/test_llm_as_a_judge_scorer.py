from unittest.mock import patch

import weave
from weave.prompt.prompt import MessagesPrompt
from weave.scorers import LLMAsAJudgeScorer
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
)


def test_publish_and_load_scorer_with_prompt_ref(client):
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
    prompt_uri = str(prompt_ref.uri())

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
    loaded_scorer = weave.get(scorer_ref.uri())

    assert isinstance(loaded_scorer, LLMAsAJudgeScorer)
    assert isinstance(loaded_scorer.scoring_prompt, MessagesPrompt)
    assert len(loaded_scorer.scoring_prompt.messages) == 1


def test_score_with_string_prompt(client):
    """Test score() with a simple string prompt."""
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt="Output: {output}",
    )

    mock_result = {"score": 1.0}
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        result = scorer.score(output="hello")

        assert result == mock_result
        mock_predict.assert_called_once()
        messages = mock_predict.call_args[0][0]
        assert messages == [{"role": "user", "content": "Output: hello"}]


def test_score_with_messages_prompt(client):
    """Test score() with a MessagesPrompt and template variables."""
    prompt = MessagesPrompt(
        messages=[
            {"role": "system", "content": "You are a {judge_type} judge."},
            {"role": "user", "content": "Expected: {expected}, Got: {output}"},
        ]
    )

    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt=prompt,
    )

    mock_result = {"score": 0.95}
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        result = scorer.score(output="4", expected="4", judge_type="math")

        assert result == mock_result
        mock_predict.assert_called_once()
        messages = mock_predict.call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["content"] == "You are a math judge."
        assert messages[1]["content"] == "Expected: 4, Got: 4"
