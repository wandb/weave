from typing import Any, Callable

from pydantic import BaseModel

from weave.actions_worker.actions.contains_words import (
    do_contains_words_action,
)
from weave.actions_worker.actions.llm_judge import do_llm_judge_action
from weave.trace_server.interface.base_object_classes.actions import (
    ActionDefinition,
    ActionSpecType,
    ContainsWordsActionSpec,
    LlmJudgeActionSpec,
)
from weave.trace_server.interface.feedback_types import RunnablePayloadSchema
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

ActionFnType = Callable[[ActionDefinition, CallSchema, TraceServerInterface], Any]

# TODO: Nail down this typing
dispatch_map: dict[type[ActionSpecType], ActionFnType] = {
    LlmJudgeActionSpec: do_llm_judge_action,
    ContainsWordsActionSpec: do_contains_words_action,
}


class ActionResult(BaseModel):
    result: Any
    feedback_res: FeedbackCreateRes


def execute_batch(
    batch_req: ActionsExecuteBatchReq,
    trace_server: TraceServerInterface,
) -> list[ActionResult]:
    # 1. Lookup the action definition
    parsed_ref = parse_internal_uri(batch_req.action_ref)
    if parsed_ref.project_id != batch_req.project_id:
        raise ValueError(
            f"Action ref {batch_req.action_ref} does not match project_id {batch_req.project_id}"
        )
    if not isinstance(parsed_ref, InternalObjectRef):
        raise ValueError(f"Action ref {batch_req.action_ref} is not an object ref")

    action_def_read = trace_server.obj_read(
        ObjReadReq(
            project_id=batch_req.project_id,
            object_id=parsed_ref.name,
            digest=parsed_ref.version,
        )
    )
    action_def = ActionDefinition.model_validate(action_def_read.obj.val)

    # Lookup the calls
    calls_query = trace_server.calls_query(
        CallsQueryReq(
            project_id=batch_req.project_id,
            filter=CallsFilter(call_ids=batch_req.call_ids),
        )
    )
    calls = calls_query.calls

    # 2. Dispatch the action to each call
    # TODO: Some actions may be able to be batched together
    results = []
    for call in calls:
        result = dispatch_action(batch_req.action_ref, action_def, call, trace_server)
        results.append(result)
    return results


def dispatch_action(
    action_ref: str,
    action_def: ActionDefinition,
    target_call: CallSchema,
    trace_server: TraceServerInterface,
) -> ActionResult:
    action_type = type(action_def.spec)
    action_fn = dispatch_map[action_type]
    result = action_fn(action_def.spec, target_call, trace_server)
    feedback_res = publish_results_as_feedback(
        target_call, action_ref, result, trace_server
    )
    return ActionResult(result=result, feedback_res=feedback_res)


def publish_results_as_feedback(
    target_call: CallSchema,
    action_ref: str,
    result: Any,
    trace_server: TraceServerInterface,
) -> FeedbackCreateRes:
    project_id = target_call.project_id
    call_id = target_call.id
    weave_ref = InternalCallRef(project_id, call_id).uri()
    parsed_action_ref = parse_internal_uri(action_ref)
    if not isinstance(parsed_action_ref, (InternalObjectRef, InternalOpRef)):
        raise ValueError(f"Invalid action ref: {action_ref}")
    action_name = parsed_action_ref.name
    return trace_server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type="wandb.runnable." + action_name,
            runnable_ref=action_ref,
            payload=RunnablePayloadSchema(output=result).model_dump(),
            # TODO: Make `wb_user_id` optional.
            wb_user_id="",
        )
    )
