import contextlib
import contextvars
import typing

if typing.TYPE_CHECKING:
    from .run import Run
    from .graph_client import GraphClient

_graph_client: contextvars.ContextVar[
    typing.Optional["GraphClient[Run]"]
] = contextvars.ContextVar("graph_client", default=None)


@contextlib.contextmanager
def set_graph_client(
    client: typing.Optional["GraphClient[Run]"],
) -> typing.Iterator[typing.Optional["GraphClient[Run]"]]:
    client_token = _graph_client.set(client)
    try:
        yield client
    finally:
        _graph_client.reset(client_token)


def get_graph_client() -> typing.Optional["GraphClient[Run]"]:
    return _graph_client.get()


def require_graph_client() -> "GraphClient[Run]":
    client = get_graph_client()
    if not client:
        raise ValueError("You must call `weave.init(<project_name>)` first")
    return client
