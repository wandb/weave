from weave.scorers.llm_as_a_judge_scorer import LLMAsAJudgeScorer
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import parse_uri
from weave.trace_server import trace_server_interface as tsi


async def apply_scorer(req: tsi.ApplyScorerReq) -> tsi.ApplyScorerRes:
    client = require_weave_client()

    loaded_scorer = client.get(parse_uri(req.scorer_ref))
    if not isinstance(loaded_scorer, LLMAsAJudgeScorer):
        raise TypeError(
            f"Invalid scorer reference: expected LLMAsAJudgeScorer, "
            f"got {type(loaded_scorer).__name__}"
        )

    call = client.get_call(req.target_call_id)
    if call is None:
        raise ValueError(f"Call {req.target_call_id} not found")

    additional_inputs = {}
    if req.additional_inputs is not None:
        if isinstance(req.additional_inputs, str):
            additional_inputs = client.get(parse_uri(req.additional_inputs))
        else:
            additional_inputs = req.additional_inputs
    if not isinstance(additional_inputs, dict):
        raise TypeError(
            f"Invalid additional inputs: expected dict, "
            f"got {type(additional_inputs).__name__}"
        )

    res = await call.apply_scorer(loaded_scorer, **additional_inputs)

    return tsi.ApplyScorerRes(output=res.result, call_id=res.score_call.id)
