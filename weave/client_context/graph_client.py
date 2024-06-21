import threading
from typing import TYPE_CHECKING, Optional

from weave.errors import WeaveInitError
from weave.legacy import context_state

if TYPE_CHECKING:
    from weave.weave_client import WeaveClient

_global_graph_client: Optional["WeaveClient"] = None
lock = threading.Lock()


def set_graph_client_global(client: Optional["WeaveClient"]) -> None:
    global _global_graph_client

    # These outer guards are to avoid expensive lock acquisition
    if client is not None and _global_graph_client is None:
        with lock:
            if _global_graph_client is None:
                _global_graph_client = client

    elif client is None and _global_graph_client is not None:
        with lock:
            if _global_graph_client is not None:
                _global_graph_client = client


def set_graph_client_context(client: Optional["WeaveClient"]) -> None:
    context_state._graph_client.set(client)


def get_graph_client() -> Optional["WeaveClient"]:
    if (context_client := context_state._graph_client.get()) is not None:
        return context_client
    return _global_graph_client


def require_graph_client() -> "WeaveClient":
    if (client := get_graph_client()) is None:
        raise WeaveInitError("You must call `weave.init(<project_name>)` first")
    return client
