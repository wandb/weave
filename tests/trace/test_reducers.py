from __future__ import annotations

from dataclasses import dataclass

import weave


def test_basic_reducer(client):
    def concat(val: str, acc: str = "") -> str:
        return acc + val

    @weave.op(reducers=[concat])
    def generator():
        yield "the "
        yield "quick "
        yield "brown "
        yield "fox"

    for _ in generator():
        pass

    calls = client.get_calls()
    call = calls[0]

    assert call.output == "the quick brown fox"


def test_complex_reducer(client):
    @dataclass(frozen=True)
    class CompletionChunk:
        id: int
        delta: str

    @dataclass(frozen=True)
    class Completion:
        text: str = ""

    def reducer(val: CompletionChunk, acc: Completion | None = None) -> Completion:
        if acc is None:
            acc = Completion()

        return Completion(text=acc.text + val.delta)

    @weave.op(reducers=[reducer])
    def generator():
        yield CompletionChunk(id=1, delta="the ")
        yield CompletionChunk(id=2, delta="quick ")
        yield CompletionChunk(id=3, delta="brown ")
        yield CompletionChunk(id=4, delta="fox")

    for _ in generator():
        pass

    calls = client.get_calls()
    call = calls[0]

    assert call.output == Completion(text="the quick brown fox")


def test_generator_as_default_reducer(client):
    @weave.op
    def generator():
        yield "the"
        yield "quick"
        yield "brown"
        yield "fox"

    for _ in generator():
        pass

    calls = client.get_calls()
    call = calls[0]

    assert call.output == ["the", "quick", "brown", "fox"]
