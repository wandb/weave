import uuid
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
from weave.trace.settings import UserSettings
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
        if item in {"internal_trace_server", "lock", "resume", "pause"}:
            return super().__getattribute__(item)
        internal_trace_server = super().__getattribute__("internal_trace_server")

        if item in {"attribute_access_log", "remote_request_bytes_limit"}:
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


def _expected_client_init_log(
    enable_client_side_digests: bool, *, include_project_reresolution: bool = False
) -> list[str]:
    log = [
        "ensure_project_exists",
        "get_call_processor",
        "get_call_processor",
        "get_feedback_processor",
        "get_feedback_processor",
    ]
    # When client-side digests are enabled, the first operation that
    # needs _internal_project_id triggers lazy projects_info resolution.
    if include_project_reresolution and enable_client_side_digests:
        log.extend(["projects_info"])
    return log


def _expected_evaluation_counts(enable_client_side_digests: bool) -> Counter[str]:
    expected = Counter(
        {
            "ensure_project_exists": 1,
            "get_call_processor": 2,
            "get_feedback_processor": 2,
            "table_create": 2,  # dataset and score results
            "obj_create": 9,  # Evaluate Op, Score Op, Predict and Score Op, Summarize Op, predict Op, PIL Image Serializer, Eval Results DS, MainDS, Evaluation Object
            "file_create": 10,  # 4 images, 6 ops
            "call_start": 14,  # Eval, summary, 4 predict and score sequences of 3 calls each
            "call_end": 14,  # Eval, summary, 4 predict and score sequences of 3 calls each
            "feedback_create": 4,  # 4 predict feedbacks
        }
    )
    if enable_client_side_digests:
        expected["projects_info"] = 2  # lazy resolution after project change
    return expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enable_client_side_digests",
    [
        pytest.param(False, id="client_side_digests_off"),
        pytest.param(True, id="client_side_digests_on"),
    ],
)
async def test_evaluation_performance(client_creator, enable_client_side_digests):
    with client_creator(
        settings=UserSettings(enable_client_side_digests=enable_client_side_digests)
    ) as client:
        mode = "on" if enable_client_side_digests else "off"
        # This test asserts exact create counts, so it needs a fresh project
        # namespace instead of reusing objects from prior suite runs.
        client.project = f"test_evaluation_performance_{mode}_{uuid.uuid4().hex[:8]}"
        evaluation, predict = build_evaluation()

        # Warm the _internal_project_id cache for the new project so that the
        # paused_client block (which holds a non-reentrant lock on the server)
        # does not deadlock when create_call lazily resolves the project id.
        _ = client._internal_project_id

        log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

        gold_log = _expected_client_init_log(
            enable_client_side_digests,
            include_project_reresolution=True,
        )
        assert log == gold_log

        with paused_client(client) as paused_client_instance:
            res = await evaluation.evaluate(predict)
            assert res["score"]["true_count"] == 1
            log = [
                l
                for l in paused_client_instance.server.attribute_access_log
                if not l.startswith("_")
            ]
            assert log == gold_log

        log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

        counts = Counter(log)

        # Tim: This is very specific and intentional, please don't change
        # this unless you are sure that is the expected behavior.
        assert counts == _expected_evaluation_counts(enable_client_side_digests)

        calls = client.get_calls()
        objects = client._objects()

        assert (
            len(list(calls)) == 14
        )  # eval, summary, 4 predict_and_score, 4 predicts, 4 scores
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
    assert len(ag_res) == 2
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
    # With ThrowingServer, _internal_project_id resolves to None (projects_info
    # throws), so the client uses the fallback path.  In the fallback path,
    # obj_create failures propagate through Future-based digest chains, causing
    # send_start_call to fail at op_def_ref.uri() with an obj_create error
    # rather than a call_start error.  Similarly, feedback_create may not be
    # reached.  We therefore expect 4 error types.
    assert len(ag_res) == 4
    assert ag_res["Task failed: DummyTestException: ('FAILURE - call_end"] <= 14
    assert ag_res["Task failed: DummyTestException: ('FAILURE - obj_create"] <= 9
    assert ag_res["Task failed: DummyTestException: ('FAILURE - file_create"] <= 10
    assert ag_res["Task failed: DummyTestException: ('FAILURE - table_create"] <= 2
