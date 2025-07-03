from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, Generic, TypedDict, TypeVar

from pydantic import BaseModel

from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.execution_runner.cross_process_trace_server import (
    CrossProcessTraceServerArgs,
    build_child_process_trace_server,
    generate_child_process_trace_server_args,
)
from weave.trace_server.execution_runner.trace_server_adapter import (
    SERVER_SIDE_ENTITY_PLACEHOLDER,
    externalize_trace_server,
    make_externalize_ref_converter,
)
from weave.trace_server.execution_runner.user_scripts.run_model import run_model


@contextmanager
def user_scoped_client(
    project_id: str, trace_server: tsi.TraceServerInterface
) -> Generator[WeaveClient, None, None]:
    client = WeaveClient(
        SERVER_SIDE_ENTITY_PLACEHOLDER, project_id, trace_server, False
    )

    ic = InitializedClient(client)

    yield client

    client._flush()
    ic.reset()


T = TypeVar("T")
TReq = TypeVar("TReq", bound=BaseModel)
TRes = TypeVar("TRes", bound=BaseModel)


class RunAsUserContext(TypedDict, Generic[T]):
    trace_server_args: CrossProcessTraceServerArgs
    project_id: str
    result_queue: multiprocessing.Queue[T]


def _generic_wrapper(
    wrapper_context: RunAsUserContext[dict],
    func: Callable[[Any], Any],
    req: Any,
) -> None:
    """Generic wrapper that executes any function in the child process with user-scoped client."""
    safe_trace_server = build_child_process_trace_server(
        wrapper_context["trace_server_args"]
    )
    with user_scoped_client(wrapper_context["project_id"], safe_trace_server):
        res = func(req)
        # Assume the result has a model_dump method (Pydantic model)
        wrapper_context["result_queue"].put(res.model_dump())


class RunAsUserException(Exception):
    """Exception raised when a user-scoped function execution fails."""

    pass


class RunAsUser:
    """Executes functions in a separate process for memory isolation.

    This class provides a way to run functions in an isolated memory space using
    multiprocessing. The function and its arguments are executed in a new Process,
    ensuring complete memory isolation from the parent process.
    """

    async def _run_user_scoped_function(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        func: Callable[[TReq], TRes],
        req: TReq,
        project_id: str,
        wb_user_id: str | None,
        response_type: type[TRes],
    ) -> TRes:
        """Generic method to run any function in an isolated process with user-scoped client.

        Args:
            internal_trace_server: The trace server interface.
            func: Function to execute in the isolated context.
            req: Request object to pass to the function.
            project_id: Project ID for the execution context.
            wb_user_id: User ID for the execution context.
            response_type: Type of the response for validation.

        Returns:
            The response from the executed function.

        Raises:
            ValueError: If wb_user_id is None.
            RunAsUserException: If process execution fails.
        """
        if wb_user_id is None:
            raise ValueError("wb_user_id is required")

        wrapped_trace_server = externalize_trace_server(
            internal_trace_server, project_id, wb_user_id
        )
        # Generate args in parent process (starts worker thread here)
        trace_server_args = generate_child_process_trace_server_args(
            wrapped_trace_server
        )
        externalize_refs = make_externalize_ref_converter(project_id)
        externalized_req = externalize_refs(req)
        result_queue: multiprocessing.Queue[dict] = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_generic_wrapper,
            kwargs={
                "wrapper_context": {
                    "trace_server_args": trace_server_args,
                    "project_id": project_id,
                    "result_queue": result_queue,
                },
                "func": func,
                "req": externalized_req,
            },
        )
        process.start()
        process.join()
        if process.exitcode != 0:
            raise RunAsUserException(f"Process execution failed: {process.exitcode}")
        return response_type.model_validate(result_queue.get())

    async def run_model(
        self, internal_trace_server: tsi.TraceServerInterface, req: tsi.RunModelReq
    ) -> tsi.RunModelRes:
        """Execute a model in an isolated process.

        Args:
            internal_trace_server: The trace server interface.
            req: Model execution request.

        Returns:
            Model execution response.
        """
        return await self._run_user_scoped_function(
            internal_trace_server,
            run_model,
            req,
            req.project_id,
            req.wb_user_id,
            tsi.RunModelRes,
        )

