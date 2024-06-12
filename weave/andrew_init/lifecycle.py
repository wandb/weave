from contextlib import contextmanager
from typing import Optional

from weave.trace_server.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server.trace_server_interface import TraceServerInterface

from ..andrew_client.client import Client
from ..andrew_init import global_state, utils


def init(entity: str, project: str, server: Optional[TraceServerInterface] = None) -> Client:
    # server = RemoteHTTPTraceServer.from_env()
    client = Client(entity, project, server)

    global_state.set_global_client(client)
    # TODO: move gc context to this new global to re-enable
    # autopatch.autopatch()
    utils.sentry_configure_scope(entity, project)

    return client


def finish():
    ...
    # zero out global state
    utils.sentry_reset_scope()

    # TODO: move gc context to this new global to re-enable
    # autopatch.reset_autopatch()
    global_state.set_global_client(None)

    # flush any messages stuck in the queue
    ...


@contextmanager
def temp_weave_context(entity: str, project: str, *, server: Optional[TraceServerInterface] = None):
    client = init(entity, project, server)
    try:
        yield client
    finally:
        finish()
