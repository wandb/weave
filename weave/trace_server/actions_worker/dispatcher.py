import inspect
from typing import Any, Callable

from pydantic import BaseModel

from weave.trace_server.actions_worker.actions.contains_words import (
    do_contains_words_action,
)
from weave.trace_server.actions_worker.actions.llm_judge import do_llm_judge_action
from weave.trace_server.builtin_object_class_util import deserialize_obj
from weave.trace_server.interface.base_object_classes.actions import (
    ActionConfigType,
    ActionSpec,
    ContainsWordsActionConfig,
    LlmJudgeActionConfig,
)
from weave.trace_server.interface.feedback_types import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    RunnablePayloadSchema,
)
from weave.trace_server.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    InternalOpRef,
    parse_internal_uri,
)
from weave.trace_server.trace_server_interface import (
    ActionsExecuteBatchReq,
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    FeedbackCreateReq,
    FeedbackCreateRes,
    ObjReadReq,
    TraceServerInterface,
)

ActionFnType = Callable[[str, ActionSpec, CallSchema, TraceServerInterface], Any]


dispatch_map: dict[type[ActionConfigType], ActionFnType] = {
    LlmJudgeActionConfig: do_llm_judge_action,
    ContainsWordsActionConfig: do_contains_words_action,
}


class ActionResult(BaseModel):
    result: Any
    feedback_res: FeedbackCreateRes


def execute_batch(
    batch_req: ActionsExecuteBatchReq,
    trace_server: TraceServerInterface,
) -> list[ActionResult]:
    project_id = batch_req.project_id
    wb_user_id = batch_req.wb_user_id
    if wb_user_id is None:
        # We should probably relax this for online evals
        raise ValueError("wb_user_id cannot be None")

    # 1. Lookup the action definition
    parsed_ref = parse_internal_uri(batch_req.runnable_ref)
    if parsed_ref.project_id != project_id:
        raise TypeError(
            f"Action ref {batch_req.runnable_ref} does not match project_id {project_id}"
        )
    if not isinstance(parsed_ref, InternalObjectRef):
        raise TypeError(f"Action ref {batch_req.runnable_ref} is not an object ref")

    runnable_ref_read = trace_server.obj_read(
        ObjReadReq(
            project_id=project_id,
            object_id=parsed_ref.name,
            digest=parsed_ref.version,
        )
    )

    runnable = deserialize_obj(runnable_ref_read.obj)

    # Lookup the calls
    calls_query = trace_server.calls_query(
        CallsQueryReq(
            project_id=project_id,
            filter=CallsFilter(call_ids=batch_req.call_ids),
        )
    )
    calls = calls_query.calls

    # 2. Dispatch the action to each call
    # FUTURE: Some actions may be able to be batched together
    results = []

    # TODO: Generalize
    from weave.scorers.test_scorer import TestScorer

    if isinstance(runnable, TestScorer):
        # action_type = type(action_def.config)
        # action_fn = dispatch_map[action_type]
        # TODO: Generalize from _apply_scorer

        # COPY:
        self_val = runnable
        scorer_op = runnable.score
        scorer_signature = inspect.signature(scorer_op)
        scorer_arg_names = list(scorer_signature.parameters.keys())
        for call in calls:
            score_args = {k: v for k, v in call.inputs.items() if k in scorer_arg_names}
            if "output" in scorer_arg_names:
                score_args["output"] = call.output
            # Any way to do this more generically?
            if self_val is not None:
                score_args["self"] = self_val
            score_results, score_call = scorer_op.call(**score_args)
            # scorer_op_ref = batch_req.runnable_ref
            # call_ref = 'idk'
            # score_call_ref = 'idk'
            feedback_res = publish_results_as_feedback(
                call,
                batch_req.runnable_ref,
                score_results,
                wb_user_id,
                trace_server,
            )
            results.append(
                ActionResult(result=score_results, feedback_res=feedback_res)
            )

        return results

    raise ValueError(f"Unknown action type: {type(runnable)}")


# def dispatch_action(
#     project_id: str,
#     runnable_ref: str,
#     action_def: ActionSpec,
#     target_call: CallSchema,
#     wb_user_id: str,
#     trace_server: TraceServerInterface,
# ) -> ActionResult:
#     action_type = type(action_def.config)
#     action_fn = dispatch_map[action_type]
#     result = action_fn(project_id, action_def.config, target_call, trace_server)
#     feedback_res = publish_results_as_feedback(
#         target_call, runnable_ref, result, wb_user_id, trace_server
#     )
#     return ActionResult(result=result, feedback_res=feedback_res)


def publish_results_as_feedback(
    target_call: CallSchema,
    runnable_ref: str,
    result: Any,
    wb_user_id: str,
    # runnable_call:
    trace_server: TraceServerInterface,
) -> FeedbackCreateRes:
    project_id = target_call.project_id
    call_id = target_call.id
    weave_ref = InternalCallRef(project_id, call_id).uri()
    parsed_runnable_ref = parse_internal_uri(runnable_ref)
    if not isinstance(parsed_runnable_ref, (InternalObjectRef, InternalOpRef)):
        raise TypeError(f"Invalid action ref: {runnable_ref}")
    action_name = parsed_runnable_ref.name
    return trace_server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=RUNNABLE_FEEDBACK_TYPE_PREFIX + "." + action_name,
            runnable_ref=runnable_ref,
            payload=RunnablePayloadSchema(output=result).model_dump(),
            wb_user_id=wb_user_id,
        )
    )
