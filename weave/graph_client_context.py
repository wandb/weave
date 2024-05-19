import contextlib
import typing

from . import context_state
from . import errors

if typing.TYPE_CHECKING:
    from .weave_client import WeaveClient


@contextlib.contextmanager
def set_graph_client(
    client: typing.Optional["WeaveClient"],
) -> typing.Iterator[typing.Optional["WeaveClient"]]:
    client_token = context_state._graph_client.set(client)
    try:
        yield client
    finally:
        context_state._graph_client.reset(client_token)


def get_graph_client() -> typing.Optional["WeaveClient"]:
    return context_state._graph_client.get()


def require_graph_client() -> "WeaveClient":
    client = get_graph_client()
    if not client:
        raise errors.WeaveInitError("You must call `weave.init(<project_name>)` first")
    return client
