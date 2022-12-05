from .. import api as weave
from .. import weave_types as types
from . import pandas_ as op_pandas
import pandas as pd


def test_save_dataframe():
    data = [["cat", 10], ["dog", 3], ["cat", 1]]
    df = pd.DataFrame(data, columns=["class", "age"])
    ref = weave.save(df, "my-df")
    df2 = weave.use(ref)
    assert df.equals(df2)


def test_save_dataframe_table():
    data = [["cat", 10], ["dog", 3], ["cat", 1]]
    df = pd.DataFrame(data, columns=["class", "age"])
    # print("DF", op_pandas.DataFrameTable)
    df_table = op_pandas.DataFrameTable(df)
    ref = weave.save(df_table, "my-df-table")
    df_table2 = weave.use(ref)
    assert df_table._df.equals(df_table2._df)


def test_dataframe_type():
    data = [["cat", 10, 0.1], ["dog", 3, 0.2], ["cat", 1, 0.3]]
    df = pd.DataFrame(data, columns=["class", "age", "loss"])
    assert types.TypeRegistry.type_of(df).object_type == types.TypedDict(
        {
            "class": types.String(),
            "age": types.Int(),
            "loss": types.Float(),
        }
    )
