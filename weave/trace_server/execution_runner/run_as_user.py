from __future__ import annotations

import multiprocessing
from collections.abc import Generator
from contextlib import contextmanager

from weave.trace.ref_util import get_ref
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
    convert_internal_uri_to_external_ref,
    externalize_trace_server,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


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


def run_model_wrapped(
    trace_server_args: CrossProcessTraceServerArgs,
    project_id: str,
    req: tsi.RunModelReq,
    result_queue: multiprocessing.Queue[tsi.RunModelRes],
) -> None:
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


class RunModelException(Exception):
    pass


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
        if wb_user_id is None:
            raise ValueError("wb_user_id is required")
        wrapped_trace_server = externalize_trace_server(
            internal_trace_server, project_id, wb_user_id
        )
        # Generate args in parent process (starts worker thread here)
        trace_server_args = generate_child_process_trace_server_args(
            wrapped_trace_server
        )
        result_queue: multiprocessing.Queue[tsi.RunModelRes] = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=run_model_wrapped,
            kwargs={
                "trace_server_args": trace_server_args,
                "project_id": project_id,
                "req": req,
                "result_queue": result_queue,
            },
        )
        process.start()
        process.join()
        if process.exitcode != 0:
            raise RunModelException(f"Process execution failed: {process.exitcode}")
        return tsi.RunModelRes.model_validate(result_queue.get())
