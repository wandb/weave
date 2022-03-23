import contextvars
import contextlib
import typing

from . import client
from . import server
from . import util


_weave_client: contextvars.ContextVar[
    typing.Optional[client.Client]
] = contextvars.ContextVar("weave_client", default=None)


@contextlib.contextmanager
def in_process_client():
    wc = client.Client(server.InProcessServer())
    token = _weave_client.set(wc)
    yield wc
    _weave_client.reset(token)


def _make_default_client():
    if util.is_notebook():
        s = server.HttpServer()
        s.start()
        return server.HttpServerClient(s.url)
    else:
        return client.Client(server.InProcessServer())


def get_client():
    c = _weave_client.get()
    if c is None:
        c = _make_default_client()
        _weave_client.set(c)
    return c
