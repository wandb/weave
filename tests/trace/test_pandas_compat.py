import pandas as pd

from weave import Dataset


def test_dataset(client):
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
    ds = Dataset(rows=rows)
    df = ds.to_pandas()

    df2 = pd.DataFrame(rows)
    ds2 = Dataset.from_pandas(df2)

    assert df.equals(df2)
    assert ds.rows == ds2.rows
