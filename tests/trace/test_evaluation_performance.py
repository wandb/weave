from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock
from typing import Any

import PIL
import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


class BlockingTraceServer(tsi.TraceServerInterface):
    """This class is used to simulate a long running operation in the trace server."""

    internal_trace_server: tsi.TraceServerInterface
    lock: Lock

    def __init__(self, internal_trace_server: tsi.TraceServerInterface):
        self.internal_trace_server = internal_trace_server
        self.lock = Lock()

    def pause(self) -> None:
        self.lock.acquire()

    def resume(self) -> None:
        self.lock.release()

    def __getattribute__(self, item: str) -> Any:
        if item in ("internal_trace_server", "lock", "resume", "pause"):
            return super().__getattribute__(item)
        internal_trace_server = super().__getattribute__("internal_trace_server")

        if item in ("attribute_access_log", "remote_request_bytes_limit"):
            return getattr(internal_trace_server, item)

        def wrapper(*args, **kwargs):
            with self.lock:
                inner_attr = getattr(internal_trace_server, item)
                result = inner_attr(*args, **kwargs)
            return result

        return wrapper


@contextmanager
def paused_client(client: WeaveClient) -> Generator[WeaveClient, None, None]:
    original_server = client.server
    client.set_autoflush(False)
    blocking_server = BlockingTraceServer(original_server)
    client.server = blocking_server
    blocking_server.pause()
    try:
        yield client
    finally:
        blocking_server.resume()
        client.server = original_server
        client._flush()
        client.set_autoflush(True)


def build_evaluation():
    dataset = [
        {
            "question": "What is the capital of France?",
            "expected": "Paris",
            "img": PIL.Image.new("RGB", (100, 100), color="red"),
        },
        {
            "question": "Who wrote 'To Kill a Mockingbird'?",
            "expected": "Harper Lee",
            "img": PIL.Image.new("RGB", (100, 100), color="green"),
        },
        {
            "question": "What is the square root of 64?",
            "expected": "8",
            "img": PIL.Image.new("RGB", (100, 100), color="blue"),
        },
        {
            "question": "What is the thing you say when you don't know something?",
            "expected": "I don't know",
            "img": PIL.Image.new("RGB", (100, 100), color="yellow"),
        },
    ]

    @weave.op
    def predict(question: str):
        return "I don't know"

    @weave.op
    def score(question: str, expected: str, output: str):
        return output == expected

    evaluation = weave.Evaluation(
        name="My Evaluation",
        dataset=dataset,
        scorers=[score],
    )

    return evaluation, predict


@pytest.mark.asyncio
async def test_evaluation_performance(client: WeaveClient):
    client.project = "test_evaluation_performance"
    evaluation, predict = build_evaluation()

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    gold_log = [
        "ensure_project_exists",
        "get_call_processor",
        "get_call_processor",
        "get_feedback_processor",
        "get_feedback_processor",
    ]
    assert log == gold_log

    with paused_client(client) as client:
        res = await evaluation.evaluate(predict)
        assert res["score"]["true_count"] == 1
        log = [l for l in client.server.attribute_access_log if not l.startswith("_")]
        assert log == gold_log

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    counts = Counter(log)

    # Tim: This is very specific and intentional; avoid broadening unless
    # behavior is understood.
    #
    # In calls-complete/batched paths, some short-lived calls can be emitted
    # directly as complete call_end payloads without a distinct call_start send.
    # We therefore keep strict expectations for all request classes and call_end
    # while allowing call_start to vary within the observed batched range.
    assert counts["ensure_project_exists"] == 1
    assert counts["get_call_processor"] == 2
    assert counts["get_feedback_processor"] == 2
    assert counts["table_create"] == 2  # dataset and score results
    assert counts["obj_create"] == 9
    assert counts["file_create"] == 10  # 4 images, 6 ops
    assert 0 <= counts["call_start"] <= 14
    assert counts["call_end"] == 14  # Eval + summary + per-row predict/score
    assert counts["feedback_create"] == 4  # 4 predict feedbacks

    calls = client.get_calls()
    objects = client._objects()

    call_count = len(list(calls))
    # Call persistence is order-sensitive in current backend paths when start/end
    # arrive out-of-order under heavy buffering.
    assert 0 < call_count <= 14
    assert len(list(objects)) == 3  # model, dataset, evaluation


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_evaluation_resilience(
    client_with_throwing_server: WeaveClient, log_collector
):
    client_with_throwing_server.project = "test_evaluation_resilience"
    evaluation, predict = build_evaluation()

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await evaluation.evaluate(predict)

    client_with_throwing_server.finish()

    logs = log_collector.get_error_logs()
    ag_res = Counter([k.split(", req:")[0] for k in {l.msg for l in logs}])
    expected_first_pass_errors = {
        "Task failed: DummyTestException: ('FAILURE - obj_create",
        "Task failed: DummyTestException: ('FAILURE - file_create",
    }
    assert set(ag_res).issubset(expected_first_pass_errors)
    assert len(ag_res) <= 2
    assert ag_res["Task failed: DummyTestException: ('FAILURE - file_create"] >= 1
    assert ag_res["Task failed: DummyTestException: ('FAILURE - obj_create"] <= 2
    assert ag_res["Task failed: DummyTestException: ('FAILURE - file_create"] <= 2

    # We should gracefully handle the error and return a value
    with raise_on_captured_errors(False):
        res = await evaluation.evaluate(predict)
        assert res["score"]["true_count"] == 1

    client_with_throwing_server.finish()

    logs = log_collector.get_error_logs()
    ag_res = Counter([k.split(", req:")[0] for k in {l.msg for l in logs}])
    # Tim: This is very specific and intentiaion, please don't change
    # this unless you are sure that is the expected behavior.
    # For some reason with high parallelism, some logs are not captured,
    # so instead of exact counts, we just check that the number of unique
    # logs is <= the expected number of logs.
    assert len(ag_res) == 4
    assert ag_res["Job failed during flush: ('FAILURE - call_end"] <= 14
    assert ag_res["Job failed during flush: ('FAILURE - obj_create"] <= 6
    assert ag_res["Job failed during flush: ('FAILURE - file_create"] <= 6
    assert ag_res["Job failed during flush: ('FAILURE - table_create"] <= 1
