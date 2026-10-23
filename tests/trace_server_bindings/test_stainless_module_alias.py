import importlib
import sys

import pytest

import weave.trace_server_bindings
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer

_OLD_PATH = "weave.trace_server_bindings.stainless_remote_http_trace_server"


def test_stainless_module_path_warns_and_is_the_remote_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, _OLD_PATH, raising=False)
    monkeypatch.delitem(
        vars(weave.trace_server_bindings),
        "stainless_remote_http_trace_server",
        raising=False,
    )

    with pytest.warns(FutureWarning) as record:
        module = importlib.import_module(_OLD_PATH)

    assert module.StainlessRemoteHTTPTraceServer is RemoteHTTPTraceServer
    assert [
        str(w.message) for w in record if issubclass(w.category, FutureWarning)
    ] == [
        "weave.trace_server_bindings.stainless_remote_http_trace_server is deprecated "
        "and will be removed in a future release; import RemoteHTTPTraceServer from "
        "weave.trace_server_bindings.remote_http_trace_server instead."
    ]
