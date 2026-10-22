"""Canonical location is ``weave.trace_server_bindings.remote_http_trace_server``."""

import warnings

from weave.trace_server_bindings.remote_http_trace_server import *  # noqa: F403
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer

# TODO: delete this alias in a future release.
warnings.warn(
    "weave.trace_server_bindings.stainless_remote_http_trace_server is deprecated "
    "and will be removed in a future release; import RemoteHTTPTraceServer from "
    "weave.trace_server_bindings.remote_http_trace_server instead.",
    FutureWarning,
    stacklevel=2,
)

StainlessRemoteHTTPTraceServer = RemoteHTTPTraceServer
