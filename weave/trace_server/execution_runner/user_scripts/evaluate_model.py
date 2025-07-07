from weave.flow.eval import Evaluation
from weave.scorers.llm_as_a_judge_scorer import LLMAsAJudgeScorer
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import parse_uri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


async def evaluate_model(req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
    client = require_weave_client()

    loaded_evaluation = client.get(parse_uri(req.evaluation_ref))

    if not isinstance(loaded_evaluation, Evaluation):
        raise TypeError(
            f"Invalid evaluation reference: expected Evaluation, "
            f"got {type(loaded_evaluation).__name__}"
        )

    scorers = loaded_evaluation.scorers
    if scorers:
        for scorer in scorers:
            if not isinstance(scorer, LLMAsAJudgeScorer):
                raise TypeError(
                    f"Invalid scorer reference: expected LLMAsAJudgeScorer, "
                    f"got {type(scorer).__name__}"
                )

    loaded_model = client.get(parse_uri(req.model_ref))

    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError(
            f"Invalid model reference: expected LLMStructuredCompletionModel, "
            f"got {type(loaded_model).__name__}"
        )

    result, call = loaded_evaluation.evaluate.call(loaded_evaluation, loaded_model)

    return tsi.EvaluateModelRes(output=result, call_id=call.id)
