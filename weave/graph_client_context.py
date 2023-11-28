import contextvars
import typing

if typing.TYPE_CHECKING:
    from .graph_client import GraphClient

_graph_client: contextvars.ContextVar[
    typing.Optional["GraphClient"]
] = contextvars.ContextVar("graph_client", default=None)


def get_graph_client() -> typing.Optional["GraphClient"]:
    return _graph_client.get()


def require_graph_client() -> "GraphClient":
    client = get_graph_client()
    if not client:
        raise ValueError("You must call `weave.init(<project_name>)` first")
    return client
