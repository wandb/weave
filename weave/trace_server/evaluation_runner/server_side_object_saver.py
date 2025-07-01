from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, TypedDict

import weave
from weave.trace import autopatch
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.refs_internal import (
    InternalObjectRef,
    parse_internal_uri,
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


class RunAsUser:
    """Executes a function in a separate process for memory isolation.
    This class provides a way to run functions in an isolated memory space using
    multiprocessing. The function and its arguments are executed in a new Process,
    ensuring complete memory isolation from the parent process.
    """

    def __init__(self, ch_server_dump: dict[str, Any]):
        self.ch_server_dump = ch_server_dump

    @contextmanager
    def user_scoped_client(
        self, project_id: str, wb_user_id: str
    ) -> Generator[WeaveClient, None, None]:
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        client = WeaveClient(
            SERVER_SIDE_ENTITY_PLACEHOLDER,
            project_id,
            UserInjectingExternalTraceServer(
                ClickHouseTraceServer(**self.ch_server_dump),
                id_converter=IdConverter(),
                user_id=wb_user_id,
            ),
            False,
        )

        ic = InitializedClient(client)

        yield client

        client._flush()
        ic.reset()

    async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
        wb_user_id = req.wb_user_id
        if wb_user_id is None:
            raise ValueError("wb_user_id is required")

        with self.user_scoped_client(req.project_id, wb_user_id) as client:
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
            result, call = loaded_model.predict.call(loaded_model, **inputs_value)

            return tsi.RunModelRes(output=result, call_id=call.id)

    async def run_evaluation_evaluate(
        self,
        req: tsi.QueueEvaluationReq,
    ) -> list[str]:
        return self._evaluation_evaluate_direct(req)

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

    def _evaluation_evaluate_direct(
        self,
        req: tsi.QueueEvaluationReq,
    ) -> list[str]:
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        client = WeaveClient(
            SERVER_SIDE_ENTITY_PLACEHOLDER,
            req.project_id,
            UserInjectingExternalTraceServer(
                ClickHouseTraceServer(**self.ch_server_dump),
                id_converter=IdConverter(),
                user_id=req.wb_user_id,
            ),
            False,
        )

        ic = InitializedClient(client)
        autopatch.autopatch()

        # TODO: validate project alignment?
        eval_ref = parse_internal_uri(req.evaluation_ref)
        assert isinstance(eval_ref, InternalObjectRef)
        ref = ObjectRef(
            entity=SERVER_SIDE_ENTITY_PLACEHOLDER,
            project=eval_ref.project_id,
            name=eval_ref.name,
            _digest=eval_ref.version,
        )
        print(f"ref: {ref}")
        try:
            eval_obj = client.get(ref)
        except Exception as e:
            print(f"Error getting evaluation object: {e}")
            raise e

        print(f"eval_obj: {eval_obj}")
        eval_call_ids = []
        for model_ref_str in req.model_refs:
            model_ref_internal = parse_internal_uri(model_ref_str)
            assert isinstance(model_ref_internal, InternalObjectRef)
            model_ref = ObjectRef(
                entity=SERVER_SIDE_ENTITY_PLACEHOLDER,
                project=model_ref_internal.project_id,
                name=model_ref_internal.name,
                _digest=model_ref_internal.version,
            )
            model_obj = client.get(model_ref)
            if not isinstance(model_obj, weave.Model):
                raise TypeError("Invalid model reference")

            result, call = asyncio.run(eval_obj.evaluate.call(eval_obj, model_obj))
            eval_call_ids.append(call.id)

        autopatch.reset_autopatch()
        client._flush()
        ic.reset()
        return eval_call_ids


SERVER_SIDE_PROJECT_ID_PREFIX = SERVER_SIDE_ENTITY_PLACEHOLDER + "/"


class IdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def ext_to_int_project_id(self, project_id: str) -> str:
        assert project_id.startswith(SERVER_SIDE_PROJECT_ID_PREFIX)
        return project_id[len(SERVER_SIDE_PROJECT_ID_PREFIX) :]

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return SERVER_SIDE_PROJECT_ID_PREFIX + project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
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
