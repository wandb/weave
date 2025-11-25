import weave
from weave.prompt.prompt import MessagesPrompt
from weave.scorers import LLMAsAJudgeScorer
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
)


def test_publish_and_load_evaluation(client):
    """This test just verifies the round trip for the evaluation.

    We do not actually run it here,
    """
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
        scoring_prompt="Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
    )
    dataset = [{"question": "what 2+2?"}]
    evaluation = weave.Evaluation(dataset=dataset, scorers=[scorer])
    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4o-mini",
        default_params=LLMStructuredCompletionModelDefaultParams(
            messages_template=[
                {"role": "system", "content": "You are a helpful assistant."}
            ],
            response_format="text",
        ),
    )

    published_eval_ref = weave.publish(evaluation)
    published_model_ref = weave.publish(model)

    gotten_eval = weave.get(published_eval_ref.uri())
    gotten_model = weave.get(published_model_ref.uri())
    assert isinstance(gotten_model, LLMStructuredCompletionModel)

    assert isinstance(gotten_eval, weave.Evaluation)
    assert isinstance(gotten_eval.dataset, weave.Dataset)
    for scorer in gotten_eval.scorers:
        assert isinstance(scorer, LLMAsAJudgeScorer)


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
