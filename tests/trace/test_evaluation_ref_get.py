import weave
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
