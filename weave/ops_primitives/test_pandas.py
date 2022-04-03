import pytest

from .. import api as weave
from . import pandas_ as op_pandas
import pandas as pd


def test_save_dataframe():
    data = [["cat", 10], ["dog", 3], ["cat", 1]]
    df = pd.DataFrame(data, columns=["class", "age"])
    ref = weave.save(df, "my-df")
    df2 = weave.use(ref)
    assert df.equals(df2)


@pytest.mark.skip("not working yet.")
def test_save_dataframe_table():
    data = [["cat", 10], ["dog", 3], ["cat", 1]]
    df = pd.DataFrame(data, columns=["class", "age"])
    print("DF", op_pandas.DataFrameTable)
    df_table = op_pandas.DataFrameTable(df)
    ref = weave.save(df_table, "my-df-table")
    df2 = weave.use(ref)
    assert 1 == 2
    assert df.equals(df2)
