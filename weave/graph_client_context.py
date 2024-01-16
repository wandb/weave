import contextlib
import typing

from . import context_state
from . import errors

if typing.TYPE_CHECKING:
    from .graph_client import GraphClient


@contextlib.contextmanager
def set_graph_client(
    client: typing.Optional["GraphClient"],
) -> typing.Iterator[typing.Optional["GraphClient"]]:
    client_token = context_state._graph_client.set(client)
    try:
        yield client
    finally:
        context_state._graph_client.reset(client_token)


def get_graph_client() -> typing.Optional["GraphClient"]:
    return context_state._graph_client.get()


def require_graph_client() -> "GraphClient":
    client = get_graph_client()
    if not client:
        raise errors.WeaveInitError("You must call `weave.init(<project_name>)` first")
    return client
