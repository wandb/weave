from __future__ import annotations

import multiprocessing
from typing import Any, Callable, TypedDict

import weave
from weave.trace import autopatch
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    parse_internal_uri,
)


class ScoreCallResult(TypedDict):
    feedback_id: str
    scorer_call_id: str


class RunSaveObjectException(Exception):
    pass


class RunCallMethodException(Exception):
    pass


class RunScoreCallException(Exception):
    pass


class RunAsUser:
    """Executes a function in a separate process for memory isolation.

    This class provides a way to run functions in an isolated memory space using
    multiprocessing. The function and its arguments are executed in a new Process,
    ensuring complete memory isolation from the parent process.
    """

    def __init__(self, ch_server_dump: dict[str, Any]):
        self.ch_server_dump = ch_server_dump

    @staticmethod
    def _process_runner(
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        result_queue: multiprocessing.Queue,
    ) -> None:
        """Execute the function and put its result in the queue.

        Args:
            func: The function to execute
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            result_queue: Queue to store the function's result
        """
        try:
            result = func(*args, **kwargs)
            result_queue.put(("success", result))
        except Exception as e:
            result_queue.put(("error", str(e)))

    def run_save_object(
        self,
        new_obj: Any,
        project_id: str,
        object_name: str | None,
        user_id: str | None,
    ) -> str:
        """Run the save_object operation in a separate process.

        Args:
            new_obj: The object to save
            project_id: The project identifier
            user_id: The user identifier

        Returns:
            str: The digest of the saved object

        Raises:
            Exception: If the save operation fails in the child process
        """
        result_queue: multiprocessing.Queue[tuple[str, str]] = multiprocessing.Queue()

        process = multiprocessing.Process(
            target=self._save_object,
            args=(
                new_obj,
                project_id,
                object_name,
                user_id,
                result_queue,
            ),  # Pass result_queue here
        )

        process.start()
        status, result = result_queue.get()
        process.join()

        if status == "error":
            raise RunSaveObjectException(f"Process execution failed: {result}")

        return result

    def _save_object(
        self,
        new_obj: Any,
        project_id: str,
        object_name: str | None,
        user_id: str | None,
        result_queue: multiprocessing.Queue,
    ) -> None:
        """Save an object in a separate process.

        Args:
            new_obj: The object to save
            project_id: The project identifier
            object_name: The name of the object
            user_id: The user identifier
            result_queue: Queue to store the operation's result
        """
        try:
            from weave.trace_server.clickhouse_trace_server_batched import (
                ClickHouseTraceServer,
            )

            client = WeaveClient(
                "_SERVER_",
                project_id,
                UserInjectingExternalTraceServer(
                    ClickHouseTraceServer(**self.ch_server_dump),
                    id_converter=IdConverter(),
                    user_id=user_id,
                ),
                False,
            )

            ic = InitializedClient(client)
            autopatch.autopatch()

            res = weave.publish(new_obj, name=object_name).digest
            autopatch.reset_autopatch()
            client._flush()
            ic.reset()
            result_queue.put(("success", res))  # Put the result in the queue
        except Exception as e:
            result_queue.put(("error", str(e)))  # Put any errors in the queue

    def run_call_method(
        self,
        obj_ref: str,
        project_id: str,
        user_id: str,
        method_name: str,
        args: dict[str, Any],
    ) -> str:
        result_queue: multiprocessing.Queue[tuple[str, Any]] = multiprocessing.Queue()

        process = multiprocessing.Process(
            target=self._call_method,
            args=(obj_ref, project_id, user_id, method_name, args, result_queue),
        )

        process.start()
        status, result = result_queue.get()
        process.join()

        if status == "error":
            raise RunCallMethodException(f"Process execution failed: {result}")

        return result

    def _call_method(
        self,
        obj_ref: str,
        project_id: str,
        user_id: str,
        method_name: str,
        args: dict[str, Any],
        result_queue: multiprocessing.Queue,
    ) -> None:
        try:
            from weave.trace_server.clickhouse_trace_server_batched import (
                ClickHouseTraceServer,
            )

            client = WeaveClient(
                "_SERVER_",
                project_id,
                UserInjectingExternalTraceServer(
                    ClickHouseTraceServer(**self.ch_server_dump),
                    id_converter=IdConverter(),
                    user_id=user_id,
                ),
                False,
            )

            ic = InitializedClient(client)
            autopatch.autopatch()

            # TODO: validate project alignment?
            int_ref = parse_internal_uri(obj_ref)
            assert isinstance(int_ref, InternalObjectRef)
            ref = ObjectRef(
                entity="_SERVER_",
                project=int_ref.project_id,
                name=int_ref.name,
                _digest=int_ref.version,
            )
            obj = client.get(ref)
            method = getattr(obj, method_name)
            # TODO: Self might be wrong
            res, call = method.call(self=obj, **args)
            autopatch.reset_autopatch()
            client._flush()
            ic.reset()
            result_queue.put(
                ("success", {"output": res, "call_id": call.id})
            )  # Put the result in the queue
        except Exception as e:
            result_queue.put(("error", str(e)))  # Put any errors in the queue

    def run_score_call(self, req: tsi.ScoreCallReq) -> ScoreCallResult:
        result_queue: multiprocessing.Queue[tuple[str, ScoreCallResult | str]] = (
            multiprocessing.Queue()
        )

        process = multiprocessing.Process(
            target=self._score_call,
            args=(req, result_queue),
        )

        process.start()
        status, result = result_queue.get()
        process.join()

        if status == "error":
            raise RunScoreCallException(f"Process execution failed: {result}")

        if isinstance(result, dict):
            return result
        else:
            raise RunScoreCallException(f"Unexpected result: {result}")

    def _score_call(
        self,
        req: tsi.ScoreCallReq,
        result_queue: multiprocessing.Queue[tuple[str, ScoreCallResult | str]],
    ) -> None:
        try:
            from weave.trace.weave_client import Call
            from weave.trace_server.clickhouse_trace_server_batched import (
                ClickHouseTraceServer,
            )

            client = WeaveClient(
                "_SERVER_",
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

            target_call_ref = parse_internal_uri(req.call_ref)
            if not isinstance(target_call_ref, InternalCallRef):
                raise TypeError("Invalid call reference")
            target_call = client.get_call(target_call_ref.id)._val
            if not isinstance(target_call, Call):
                raise TypeError("Invalid call reference")
            scorer_ref = parse_internal_uri(req.scorer_ref)
            if not isinstance(scorer_ref, InternalObjectRef):
                raise TypeError("Invalid scorer reference")
            scorer = weave.ref(
                ObjectRef(
                    entity="_SERVER_",
                    project=scorer_ref.project_id,
                    name=scorer_ref.name,
                    _digest=scorer_ref.version,
                ).uri()
            ).get()
            if not isinstance(scorer, weave.Scorer):
                raise TypeError("Invalid scorer reference")
            apply_scorer_res = target_call._apply_scorer(scorer)

            autopatch.reset_autopatch()
            client._flush()
            ic.reset()
            scorer_call_id = apply_scorer_res["score_call"].id
            if not scorer_call_id:
                raise ValueError("Scorer call ID is required")
            result_queue.put(
                (
                    "success",
                    ScoreCallResult(
                        feedback_id=apply_scorer_res["feedback_id"],
                        scorer_call_id=scorer_call_id,
                    ),
                )
            )  # Put the result in the queue
        except Exception as e:
            result_queue.put(("error", str(e)))  # Put any errors in the queue


class IdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def ext_to_int_project_id(self, project_id: str) -> str:
        assert project_id.startswith("_SERVER_/")
        return project_id[len("_SERVER_/") :]

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return "_SERVER_/" + project_id

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

    def call_method(self, req: tsi.CallMethodReq) -> tsi.CallMethodRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().call_method(req)

    def score_call(self, req: tsi.ScoreCallReq) -> tsi.ScoreCallRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().score_call(req)
