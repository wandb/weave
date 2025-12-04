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


def test_publish_and_load_llm_as_judge_scorer_with_scoring_prompt_ref(client):
    """Test that LLMAsAJudgeScorer with scoring_prompt_ref can be published and loaded.

    This tests the new scoring_prompt_ref feature which allows referencing a
    published MessagesPrompt instead of inline scoring_prompt string.

    When the scorer is loaded via weave.get(), the scoring_prompt_ref string
    is automatically resolved to the actual MessagesPrompt object by weave's
    deserialization. The scorer accepts both string refs and resolved objects.
    """
    # First, create and publish a MessagesPrompt
    scoring_prompt = MessagesPrompt(
        messages=[
            {
                "role": "user",
                "content": "Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
            }
        ]
    )
    published_prompt_ref = weave.publish(scoring_prompt)
    prompt_uri = str(published_prompt_ref.uri())

    # Create scorer using scoring_prompt_ref instead of scoring_prompt string
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                messages_template=[
                    {
                        "role": "system",
                        "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                    }
                ],
                response_format="json_object",
            ),
        ),
        scoring_prompt_ref=prompt_uri,
    )

    # Verify the scorer was created with the ref string
    assert scorer.scoring_prompt_ref == prompt_uri
    assert scorer.scoring_prompt is None

    # Publish and retrieve the scorer - weave.get() auto-resolves the ref
    published_scorer_ref = weave.publish(scorer)
    gotten_scorer = weave.get(published_scorer_ref.uri())

    # Verify the round-trip works - scoring_prompt_ref is now the resolved MessagesPrompt
    assert isinstance(gotten_scorer, LLMAsAJudgeScorer)
    assert isinstance(gotten_scorer.scoring_prompt_ref, MessagesPrompt)
    assert gotten_scorer.scoring_prompt is None
    # Verify the resolved prompt has the expected messages
    assert len(gotten_scorer.scoring_prompt_ref.messages) == 1

    # Test that build_scoring_messages works with the resolved prompt
    # This is the method the scoring worker calls directly
    template_vars = {"inputs": "2+2", "output": "4"}
    messages = gotten_scorer.build_scoring_messages(template_vars)

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert "2+2" in messages[0].content
    assert "4" in messages[0].content


def test_build_scoring_messages_with_string_prompt(client):
    """Test build_scoring_messages with a simple string prompt."""
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt="Score this output: {output}. Input was: {inputs}.",
    )

    messages = scorer.build_scoring_messages({"output": "hello", "inputs": "greeting"})

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Score this output: hello. Input was: greeting."


def test_build_scoring_messages_with_resolved_messages_prompt(client):
    """Test build_scoring_messages when scoring_prompt_ref is already a MessagesPrompt object."""
    # Create a MessagesPrompt directly (simulating what happens after weave.get() resolves a ref)
    prompt = MessagesPrompt(
        messages=[
            {"role": "system", "content": "You are a judge."},
            {"role": "user", "content": "Evaluate: {output}"},
        ]
    )

    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt_ref=prompt,  # Pass the resolved prompt directly
    )

    messages = scorer.build_scoring_messages({"output": "test result"})

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[0].content == "You are a judge."
    assert messages[1].role == "user"
    assert messages[1].content == "Evaluate: test result"


def test_score_with_messages_prompt_ref_and_template_vars(client):
    """Test the full score() flow with a MessagesPrompt ref and multiple template vars.

    This tests calling score() with a scorer that uses scoring_prompt_ref,
    verifying the complete flow from template vars through to model prediction.
    The score() method takes output as a required arg plus any additional kwargs
    which become template variables for the prompt.
    """
    # Create a MessagesPrompt with multiple template variables
    prompt = MessagesPrompt(
        messages=[
            {"role": "system", "content": "You are a {judge_type} judge."},
            {
                "role": "user",
                "content": "Question: {question}\nExpected: {expected}\nActual Output: {output}\n\nIs this correct?",
            },
        ]
    )

    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4o-mini",
        default_params=LLMStructuredCompletionModelDefaultParams(
            response_format="json_object",
        ),
    )

    scorer = LLMAsAJudgeScorer(
        model=model,
        scoring_prompt_ref=prompt,
    )

    # Mock the model's predict method on the class to avoid actual LLM calls
    mock_result = {"score": 0.95, "reasoning": "The output is correct."}
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        # Call score() with output + multiple template vars as kwargs
        # These kwargs become template variables: {question}, {expected}, {judge_type}
        result = scorer.score(
            output="4",
            question="What is 2+2?",
            expected="4",
            judge_type="math",
        )

        # Verify the result
        assert result == mock_result

        # Verify predict was called with the correctly formatted messages
        mock_predict.assert_called_once()
        # Get the messages argument (first positional arg after self)
        call_args, call_kwargs = mock_predict.call_args
        # Messages could be in args[0] (after self) or in kwargs
        messages = call_args[0] if call_args else call_kwargs.get("user_input", [])
        assert len(messages) == 2

        # Verify system message has template var substituted
        assert messages[0].role == "system"
        assert messages[0].content == "You are a math judge."

        # Verify user message has all template vars substituted
        assert messages[1].role == "user"
        assert "What is 2+2?" in messages[1].content
        assert "Expected: 4" in messages[1].content
        assert "Actual Output: 4" in messages[1].content
