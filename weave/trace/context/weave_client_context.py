from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

# Thread-local storage for per-thread clients
_thread_local = threading.local()


def set_weave_client_global(client: WeaveClient | None) -> None:
    """Sets the client for the current thread.
    
    Note: Despite the name, this now sets a thread-local client.
    The name is kept for backwards compatibility.
    Each thread must call weave.init() to get its own client.
    """
    _thread_local.client = client


# This is no longer a concept, but should be
# def set_weave_client_context(client: Optional["WeaveClient"]) -> None:
#     context_state._graph_client.set(client)


def get_weave_client() -> WeaveClient | None:
    """Gets the WeaveClient for the current thread.
    
    Returns the thread-local client if set, otherwise returns None.
    Each thread must have its own client.
    """
    return getattr(_thread_local, 'client', None)




class WeaveInitError(Exception): ...


def require_weave_client() -> WeaveClient:
    if (client := get_weave_client()) is None:
        raise WeaveInitError("You must call `weave.init(<project_name>)` in this thread first")
    return client


@contextmanager
def with_weave_client(
    entity: str | None, project: str | None, required: bool = True
) -> Generator[WeaveClient | None, None, None]:
    """Context manager that returns a WeaveClient for a given entity and project.

    Restores any active WeaveClient after the context manager exits.

    Args:
        entity: Entity name or None to use the current entity if there is one
        project: Project name or None to use the current project if there is one
        required: If True, raises WeaveInitError when no client exists and entity/project are None

    Yields:
        A WeaveClient to use for the duration of the context manager or None if no client exists
        and required=False
    """
    current_client = get_weave_client()
    if entity is None and project is None:
        if required and current_client is None:
            raise WeaveInitError("You must call `weave.init(<project_name>)` in this thread first")
        yield current_client
    else:
        from weave.trace.weave_init import init_weave

        scoped_name = f"{entity}/{project}"
        try:
            client = init_weave(scoped_name, ensure_project_exists=False)
            yield client
        finally:
            # Restore the previous thread-local client
            _thread_local.client = current_client
