from __future__ import annotations

import multiprocessing
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Callable, Optional, TypedDict

from weave.trace.ref_util import get_ref
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.cross_process_trace_server import (
    build_child_process_trace_server,
    generate_child_process_trace_server_args,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.refs_internal import (
    InternalObjectRef,
    parse_internal_uri,
)
from weave.trace_server.secret_fetcher_context import (
    SecretFetcher,
    secret_fetcher_context,
)

SERVER_SIDE_ENTITY_PLACEHOLDER = "__SERVER__"


class ScoreCallResult(TypedDict):
    feedback_id: str
    scorer_call_id: str


class RunSaveObjectException(Exception):
    pass


class RunCallMethodException(Exception):
    pass


class RunScoreCallException(Exception):
    pass


class RunEvaluationException(Exception):
    pass


def convert_internal_uri_to_external_ref(client: WeaveClient, ref: str) -> ObjectRef:
    internal_ref = parse_internal_uri(ref)
    assert isinstance(internal_ref, InternalObjectRef)
    return client.object_ref(
        internal_ref.name, internal_ref.version, tuple(internal_ref.extra)
    )


SHARED_CHILD_PROCESS_CTX_MANAGERS: list[Callable[[], None]] = []


def register_child_process_ctx_manager(cb: Callable[[], None]):
    def unregister():
        SHARED_CHILD_PROCESS_CTX_MANAGERS.remove(cb)

    SHARED_CHILD_PROCESS_CTX_MANAGERS.append(cb)
    return unregister


def _process_wrapper(
    fn: Callable,
    *args,
    project_id: str,
    wb_user_id: str,
    ch_server_dump: dict[str, Any],
    secret_fetcher: Optional[SecretFetcher],
    result_queue: multiprocessing.Queue,
    child_process_ctx_managers: list[Callable[[], None]],
    **kwargs,
) -> None:
    """Module-level wrapper function that can be pickled for multiprocessing.

    This function wraps the actual function to be executed in a subprocess,
    setting up the necessary context (secret fetcher, user-scoped client, etc.)
    before executing the function and returning the result via a queue.

    Args:
        fn: The function to execute in the subprocess.
        *args: Positional arguments to pass to fn.
        project_id: The project ID for scoping.
        wb_user_id: The user ID for authentication.
        ch_server_dump: Serialized ClickHouse server configuration.
        secret_fetcher: Optional secret fetcher for accessing secrets.
        result_queue: Queue to put the result in.
        **kwargs: Keyword arguments to pass to fn.
    """
    with secret_fetcher_context(secret_fetcher):
        with user_scoped_client(project_id, wb_user_id, ch_server_dump) as client:
            enter_cbs = []
            for cb in SHARED_CHILD_PROCESS_CTX_MANAGERS + (
                child_process_ctx_managers or []
            ):
                ctx = cb()
                ctx.enter()
                enter_cbs.append(ctx)
            res = fn(*args, client=client, **kwargs)
            for cb in enter_cbs:
                cb.exit()
            result_queue.put(res.model_dump())


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface, project_id: str, wb_user_id: str
) -> tsi.TraceServerInterface:
    return UserInjectingExternalTraceServer(
        trace_server,
        id_converter=IdConverter(project_id, wb_user_id),
        user_id=wb_user_id,
    )


@contextmanager
def user_scoped_client(
    project_id: str, trace_server: tsi.TraceServerInterface
) -> Generator[WeaveClient, None, None]:
    client = WeaveClient(
        SERVER_SIDE_ENTITY_PLACEHOLDER,
        project_id,
        trace_server,
        False,
    )

    ic = InitializedClient(client)

    yield client

    client._flush()
    ic.reset()


def run_model_wrapped(
    trace_server_args,
    project_id,
    req: tsi.RunModelReq,
    result_queue: multiprocessing.Queue,
) -> tsi.RunModelRes:
    safe_trace_server = build_child_process_trace_server(trace_server_args)
    with user_scoped_client(project_id, safe_trace_server) as client:
        res = _run_model(req, client)
        result_queue.put(res.model_dump())


def _run_model(req: tsi.RunModelReq, client: WeaveClient) -> tsi.RunModelRes:
    loaded_model = client.get(
        convert_internal_uri_to_external_ref(client, req.model_ref)
    )
    if not isinstance(loaded_model, LLMStructuredCompletionModel):
        raise TypeError("Invalid model reference")

    inputs_value: dict
    if req.inputs.input_type == "value":
        inputs_value = req.inputs.value

    elif req.inputs.input_type == "ref":
        inputs_value = client.get(
            convert_internal_uri_to_external_ref(client, req.inputs.value)
        )

    else:
        raise ValueError("Invalid input type")

    if not isinstance(inputs_value, dict):
        raise TypeError("Inputs value must be a dictionary")

    # Sad - this should be async, but we can't do that because the model is not async
    assert get_ref(LLMStructuredCompletionModel.predict) is None
    result, call = loaded_model.predict.call(loaded_model, **inputs_value)
    assert get_ref(LLMStructuredCompletionModel.predict) is not None
    # assert get_ref(LLMStructuredCompletionModel.predict) is None
    return tsi.RunModelRes(output=result, call_id=call.id)


class RunAsUser:
    """Executes a function in a separate process for memory isolation.
    This class provides a way to run functions in an isolated memory space using
    multiprocessing. The function and its arguments are executed in a new Process,
    ensuring complete memory isolation from the parent process.
    """

    async def run_model(
        self, internal_trace_server: tsi.TraceServerInterface, req: tsi.RunModelReq
    ) -> tsi.RunModelRes:
        project_id = req.project_id
        wb_user_id = req.wb_user_id
        wrapped_trace_server = externalize_trace_server(
            internal_trace_server, project_id, wb_user_id
        )
        child_trace_server_args = generate_child_process_trace_server_args(
            wrapped_trace_server
        )
        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=run_model_wrapped,
            kwargs={
                "trace_server_args": child_trace_server_args,
                "project_id": project_id,
                "wb_user_id": wb_user_id,
                "req": req,
                "result_queue": result_queue,
            },
        )
        process.start()
        process.join()
        if process.exitcode != 0:
            raise RunEvaluationException(
                f"Process execution failed: {process.exitcode}"
            )
        return tsi.RunModelRes.model_validate(result_queue.get())

    # def run_in_child_process(
    #     self, fn: Callable, project_id: str, wb_user_id: str, **kwargs
    # ):
    #     result_queue = multiprocessing.Queue()
    #     final_kwargs = {
    #         "fn": fn,
    #         **kwargs,
    #         "project_id": project_id,
    #         "wb_user_id": wb_user_id,
    #         "result_queue": result_queue,
    #         "secret_fetcher": _secret_fetcher_context.get(),
    #         "ch_server_dump": self.ch_server_dump,
    #         "child_process_ctx_managers": SHARED_CHILD_PROCESS_CTX_MANAGERS,
    #     }

    #     process = multiprocessing.Process(target=_process_wrapper, kwargs=final_kwargs)
    #     process.start()
    #     process.join()
    #     if process.exitcode != 0:
    #         raise RunEvaluationException(
    #             f"Process execution failed: {process.exitcode}"
    #         )
    #     return result_queue.get()

    # async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
    #     result = self.run_in_child_process(
    #         _run_model,
    #         project_id=req.project_id,
    #         wb_user_id=req.wb_user_id,
    #         req=req,
    #     )
    #     assert get_ref(LLMStructuredCompletionModel.predict) is None
    #     return tsi.RunModelRes.model_validate(result)

    # async def run_evaluation_evaluate(
    #     self,
    #     req: tsi.QueueEvaluationReq,
    # ) -> list[str]:
    #     return self._evaluation_evaluate_direct(req)

    #     result_queue: multiprocessing.Queue[tuple[str, list[str] | str]] = (
    #         multiprocessing.Queue()
    #     )

    #     process = multiprocessing.Process(
    #         target=self._evaluation_evaluate,
    #         args=(req, result_queue),
    #     )

    #     process.start()
    #     status, result = result_queue.get()
    #     process.join()

    #     if status == "error":
    #         raise RunEvaluationException(f"Process execution failed: {result}")

    #     if isinstance(result, list):
    #         return result
    #     else:
    #         raise RunEvaluationException(f"Unexpected result: {result}")

    # def _evaluation_evaluate(
    #     self,
    #     req: tsi.QueueEvaluationReq,
    #     result_queue: multiprocessing.Queue[tuple[str, list[str] | str]],
    # ) -> None:
    #     try:
    #         eval_call_ids = self._evaluation_evaluate_direct(req)
    #         result_queue.put(("success", eval_call_ids))  # Put the result in the queue
    #     except Exception as e:
    #         result_queue.put(("error", str(e)))  # Put any errors in the queue

    # def _evaluation_evaluate_direct(
    #     self,
    #     req: tsi.QueueEvaluationReq,
    # ) -> list[str]:
    #     from weave.trace_server.clickhouse_trace_server_batched import (
    #         ClickHouseTraceServer,
    #     )

    #     client = WeaveClient(
    #         SERVER_SIDE_ENTITY_PLACEHOLDER,
    #         req.project_id,
    #         UserInjectingExternalTraceServer(
    #             ClickHouseTraceServer(**self.ch_server_dump),
    #             id_converter=IdConverter(),
    #             user_id=req.wb_user_id,
    #         ),
    #         False,
    #     )

    #     ic = InitializedClient(client)
    #     autopatch.autopatch()

    #     # TODO: validate project alignment?
    #     eval_ref = parse_internal_uri(req.evaluation_ref)
    #     assert isinstance(eval_ref, InternalObjectRef)
    #     ref = ObjectRef(
    #         entity=SERVER_SIDE_ENTITY_PLACEHOLDER,
    #         project=eval_ref.project_id,
    #         name=eval_ref.name,
    #         _digest=eval_ref.version,
    #     )
    #     print(f"ref: {ref}")
    #     try:
    #         eval_obj = client.get(ref)
    #     except Exception as e:
    #         print(f"Error getting evaluation object: {e}")
    #         raise e

    #     print(f"eval_obj: {eval_obj}")
    #     eval_call_ids = []
    #     for model_ref_str in req.model_refs:
    #         model_ref_internal = parse_internal_uri(model_ref_str)
    #         assert isinstance(model_ref_internal, InternalObjectRef)
    #         model_ref = ObjectRef(
    #             entity=SERVER_SIDE_ENTITY_PLACEHOLDER,
    #             project=model_ref_internal.project_id,
    #             name=model_ref_internal.name,
    #             _digest=model_ref_internal.version,
    #         )
    #         model_obj = client.get(model_ref)
    #         if not isinstance(model_obj, weave.Model):
    #             raise TypeError("Invalid model reference")

    #         result, call = asyncio.run(eval_obj.evaluate.call(eval_obj, model_obj))
    #         eval_call_ids.append(call.id)

    #     autopatch.reset_autopatch()
    #     client._flush()
    #     ic.reset()
    #     return eval_call_ids


SERVER_SIDE_PROJECT_ID_PREFIX = SERVER_SIDE_ENTITY_PLACEHOLDER + "/"


class IdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self, project_id: str, user_id: str):
        self.user_id = user_id
        self.project_id = project_id

    def ext_to_int_project_id(self, project_id: str) -> str:
        if not project_id.startswith(SERVER_SIDE_PROJECT_ID_PREFIX):
            raise ValueError(
                f"Project ID does not start with {SERVER_SIDE_PROJECT_ID_PREFIX}: {project_id}"
            )
        found_project_id = project_id[len(SERVER_SIDE_PROJECT_ID_PREFIX) :]
        if found_project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {found_project_id} != {self.project_id}. This is a security issue."
            )
        return found_project_id

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        if project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {project_id} != {self.project_id}. This is a security issue."
            )
        return SERVER_SIDE_PROJECT_ID_PREFIX + project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def int_to_ext_run_id(self, run_id: str) -> str:
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def ext_to_int_user_id(self, user_id: str) -> str:
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. This is a security issue."
            )
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. This is a security issue."
            )
        return user_id


class UserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str | None,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

    # def call_method(self, req: tsi.CallMethodReq) -> tsi.CallMethodRes:
    #     if self._user_id is None:
    #         raise ValueError("User ID is required")
    #     req.wb_user_id = self._user_id
    #     return super().call_method(req)

    # def score_call(self, req: tsi.ScoreCallReq) -> tsi.ScoreCallRes:
    #     if self._user_id is None:
    #         raise ValueError("User ID is required")
    #     req.wb_user_id = self._user_id
    #     return super().score_call(req)
