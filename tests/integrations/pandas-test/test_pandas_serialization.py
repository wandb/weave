import pandas as pd

import weave
from weave.flow.dataset import WeaveTable
from weave.trace.refs import TableRef, parse_uri
from weave.trace_server.trace_server_interface import CallsQueryReq


def test_df_io(client):
    @weave.op
    def df_io(df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    df = pd.DataFrame({"a": [1, 2, 3]})
    df = df_io(df)
    assert df.equals(pd.DataFrame({"a": [1, 2, 3]}))

    calls = df_io.calls()
    assert len(calls) == 1
    assert calls[0].output == calls[0].inputs["df"]
    assert isinstance(calls[0].output, WeaveTable)
    calls_server = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
            call_ids=[calls[0].id],
        )
    )
    assert len(calls_server.calls) == 1
    assert calls_server.calls[0].inputs["df"] == calls_server.calls[0].output
    assert isinstance(calls_server.calls[0].inputs["df"], str)
    assert isinstance(parse_uri(calls_server.calls[0].inputs["df"]), TableRef)
