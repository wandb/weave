from contextlib import contextmanager
from threading import Lock
from typing import Any, Generator

import PIL
import pytest

import weave
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

    def __getattr__(self, item: str) -> Any:
        inner_attr = getattr(self.internal_trace_server, item)
        if callable(inner_attr):

            def wrapper(*args, **kwargs):
                print(f"Calling {item} with args: {args}, kwargs: {kwargs}")
                with self.lock:
                    result = inner_attr(*args, **kwargs)
                    print(f"Result: {result}")
                return result

            return wrapper
        else:
            return inner_attr


@contextmanager
def paused_client(client: WeaveClient) -> Generator[WeaveClient, None, None]:
    original_server = client.server
    blocking_server = BlockingTraceServer(original_server)
    client.server = blocking_server
    blocking_server.pause()
    try:
        yield client
    finally:
        blocking_server.resume()
        client.server = original_server


@pytest.mark.asyncio
async def test_evaluation_performance(client: WeaveClient):
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

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    assert log == ["ensure_project_exists"]

    # TODO: Client.pause "network" traffic
    with paused_client(client) as client:
        res = await evaluation.evaluate(predict)
        assert res["score"]["true_count"] == 1
        log = [l for l in client.server.attribute_access_log if not l.startswith("_")]
        assert log == ["ensure_project_exists"]

    client._flush()

    log = [l for l in client.server.attribute_access_log if not l.startswith("_")]

    assert log == ["ensure_project_exists"]

    # assert "something interesting about the results" == False
