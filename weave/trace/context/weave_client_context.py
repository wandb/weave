from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

_global_weave_client: WeaveClient | None = None
lock = threading.Lock()

# Context variable for project_id set during weave.init()
_project_id: ContextVar[str | None] = ContextVar("project_id", default=None)


class WeaveInitError(Exception): ...


def set_weave_client_global(client: WeaveClient | None) -> None:
    global _global_weave_client

    # These outer guards are to avoid expensive lock acquisition
    if client is not None and _global_weave_client is None:
        with lock:
            if _global_weave_client is None:
                _global_weave_client = client

    elif client is None and _global_weave_client is not None:
        with lock:
            if _global_weave_client is not None:
                _global_weave_client = client


# This is no longer a concept, but should be
# def set_weave_client_context(client: Optional["WeaveClient"]) -> None:
#     context_state._graph_client.set(client)


def get_weave_client() -> WeaveClient | None:
    # if (context_client := context_state._graph_client.get()) is not None:
    #     return context_client
    return _global_weave_client


def require_weave_client() -> WeaveClient:
    if (client := get_weave_client()) is None:
        raise WeaveInitError("You must call `weave.init(<project_name>)` first")
    return client


def set_project_id(project_id: str | None) -> None:
    """Set the project_id in the current context.

    Args:
        project_id: The project_id to set (format: "entity/project").
    """
    _project_id.set(project_id)


def get_project_id() -> str | None:
    """Get the current project_id from context.

    Returns:
        The current project_id if set, None otherwise.
    """
    return _project_id.get()


def require_project_id() -> str:
    """Get the current project_id from context, raising if not set.

    Returns:
        The current project_id.

    Raises:
        WeaveInitError: If project_id is not set.
    """
    project_id = _project_id.get()
    if project_id is None:
        raise WeaveInitError("You must call `weave.init(<project_name>)` first")
    return project_id


@contextmanager
def with_weave_client(
    entity: str | None, project: str | None, required: bool = True
) -> Generator[WeaveClient | None]:
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
    current_project_id = get_project_id()
    if entity is None and project is None:
        if required and current_client is None:
            raise WeaveInitError("You must call `weave.init(<project_name>)` first")
        yield current_client
    else:
        from weave.trace.weave_init import init_weave

        scoped_name = f"{entity}/{project}"
        try:
            client = init_weave(scoped_name, ensure_project_exists=False)
            yield client
        finally:
            set_weave_client_global(current_client)
            set_project_id(current_project_id)
