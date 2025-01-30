import pandas as pd

import weave
from weave import Dataset


def test_op_save_with_global_df(client):
    df = pd.DataFrame({"a": ["a", "b", "c"]})

    @weave.op()
    def my_op(a: str) -> str:
        # modify df outside of op scope
        prev_val = df.loc[df.index[0], "a"]
        df.loc[df.index[0], "a"] = a
        return prev_val

    res = my_op("d")
    assert res == "a"
    assert df.loc[df.index[0], "a"] == "d"

    call = list(my_op.calls())[0]
    assert call.inputs == {"a": "d"}
    assert call.output == "a"


def test_dataset(client):
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
    ds = Dataset(rows=rows)
    df = ds.to_pandas()
    assert df["a"].tolist() == [1, 3, 5]
    assert df["b"].tolist() == [2, 4, 6]

    df2 = pd.DataFrame(rows)
    ds2 = Dataset.from_pandas(df2)
    assert ds2.rows == rows
    assert df.equals(df2)
    assert ds.rows == ds2.rows


def test_calls_to_dataframe(client):
    @weave.op
    def greet(name: str, age: int) -> str:
        return f"Hello, {name}! You are {age} years old."

    greet("Alice", 30)
    greet("Bob", 25)

    calls = greet.calls()
    dataset = Dataset.from_calls(calls)
    df = dataset.to_pandas()
    assert df["inputs"].tolist() == [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    assert df["output"].tolist() == [
        "Hello, Alice! You are 30 years old.",
        "Hello, Bob! You are 25 years old.",
    ]
