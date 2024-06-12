from contextlib import contextmanager
from typing import Optional

from weave import trace_sentry
from weave.trace_server.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server.trace_server_interface import TraceServerInterface

from ..andrew_client.client import Client
from ..andrew_init import utils
from ..andrew_state import global_state


def init(entity: str, project: str, server: Optional[TraceServerInterface] = None) -> Client:
    # server = RemoteHTTPTraceServer.from_env()
    client = Client(entity, project, server)

    global_state.set_client(client)
    # TODO: move gc context to this new global to re-enable
    # autopatch.autopatch()
    utils.sentry_configure_scope(entity, project)

    return client


def finish():
    ...
    # zero out global state
    # utils.sentry_reset_scope()
    trace_sentry.global_trace_sentry.end_session()

    # TODO: move gc context to this new global to re-enable
    # autopatch.reset_autopatch()
    global_state.set_client(None)

    # flush any messages stuck in the queue
    ...


@contextmanager
def temp_weave_context(entity: str, project: str, *, server: Optional[TraceServerInterface] = None):
    client = init(entity, project, server)
    try:
        yield client
    finally:
        finish()
