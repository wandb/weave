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

    df2 = pd.DataFrame(rows)
    ds2 = Dataset.from_pandas(df2)

    assert df.equals(df2)
    assert ds.rows == ds2.rows
