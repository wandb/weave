import pandas as pd
import pytest

import weave


@weave.op
def func(name: str, age: int) -> str:
    return f"Hello, {name}! You are {age} years old."


@weave.op
def raising_func(name: str, age: int) -> str:
    raise ValueError("This is a test error")


@pytest.fixture
def logging_example(client):
    func("Alice", 30)

    with weave.attributes({"tag": "test", "version": "1.0"}):
        func("Bob", 25)

    try:
        raising_func("Claire", 35)
    except:
        pass


def test_calls_to_pandas_basic(logging_example, client):
    calls = client.get_calls()
    df = calls.to_pandas()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3  # The three calls we made

    dictified = df.to_dict(orient="records")
    calls_as_dicts = [c.to_dict() for c in calls]

    for d1, d2 in zip(dictified, calls_as_dicts):
        assert d1 == d2


def test_calls_to_pandas_with_limit(logging_example, client):
    calls = client.get_calls(limit=1)
    df = calls.to_pandas()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1

    dictified = df.to_dict(orient="records")

    # Maintains insertion order
    d = dictified[0]
    assert d["inputs"]["name"] == "Alice"
    assert d["inputs"]["age"] == 30


@pytest.mark.asyncio
async def test_calls_to_pandas_with_evaluations(client):
    @weave.op
    def model(x: int, y: int) -> int:
        return x + y

    ev = weave.Evaluation(
        dataset=[
            {"x": 1, "y": 2},
            {"x": 3, "y": 4},
            {"x": 5, "y": 6},
        ]
    )
    res = await ev.evaluate(model)

    calls = client.get_calls().to_pandas()
    assert len(calls) == (
        1  # evaluate
        + 3 * 2  # predict and score + model
        + 1  # summarize
    )
