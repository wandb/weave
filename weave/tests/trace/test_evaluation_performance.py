from collections import Counter
from contextlib import contextmanager
from threading import Lock
from typing import Any, Generator

import PIL
import pytest

import weave
from weave.conftest import TestException
from weave.trace.context import raise_on_captured_errors
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

        if item == "attribute_access_log":
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
            "img": PIL.Image.new("RGB", (100, 100)),
        },
        {
            "question": "Who wrote 'To Kill a Mockingbird'?",
            "expected": "Harper Lee",
            "img": PIL.Image.new("RGB", (100, 100)),
        },
        {
            "question": "What is the square root of 64?",
            "expected": "8",
            "img": PIL.Image.new("RGB", (100, 100)),
        },
        {
            "question": "What is the thing you say when you don't know something?",
            "expected": "I don't know",
            "img": PIL.Image.new("RGB", (100, 100)),
        },
    ]

    @weave.op()
    def predict(question: str):
        return "I don't know"

    @weave.op()
    def score(question: str, expected: str, model_output: str):
        return model_output == expected

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

    assert log == ["ensure_project_exists"]

    with paused_client(client) as client:
        res = await evaluation.evaluate(predict)
        assert res["score"]["true_count"] == 1
        log = [l for l in client.server.attribute_access_log if not l.startswith("_")]
        assert log == ["ensure_project_exists"]

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    counts = Counter(log)

    assert (
        counts
        == {
            "ensure_project_exists": 1,
            "table_create": 2,  # dataset and score results
            "obj_create": 9,  # Evaluate Op, Score Op, Predict and Score Op, Summarize Op, predict Op, PIL Image Serializer, Eval Results DS, MainDS, Evaluation Object
            "file_create": 10,  # 4 images, 6 ops
            "call_start": 14,
            "call_end": 14,
        }
    )

    calls = client.calls()
    objects = client._objects()

    assert (
        len(list(calls)) == 14
    )  # eval, summary, 4 predict_and_score, 4 predicts, 4 scores
    assert len(list(objects)) == 3  # model, dataset, evaluation


@pytest.mark.asyncio
async def test_evaluation_resilience(client_with_throwing_server: WeaveClient):
    client_with_throwing_server.project = "test_evaluation_performance"
    evaluation, predict = build_evaluation()

    # We should gracefully handle the error and return a value
    with raise_on_captured_errors(False):
        res = await evaluation.evaluate(predict)
        assert res["score"]["true_count"] == 1

    with pytest.raises(TestException):
        res = await evaluation.evaluate(predict)