import pandas as pd

import weave


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
