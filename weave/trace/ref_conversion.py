from __future__ import annotations

from typing import Any

from weave.trace.context.weave_client_context import get_weave_client


def _require_client(client=None):
    c = client or get_weave_client()
    if c is None:
        raise RuntimeError("weave.init must be called before converting refs")
    return c


def to_internal(obj: Any, client=None) -> Any:
    """Convert external weave refs in `obj` to internal refs using the client."""
    c = _require_client(client)
    return c.to_internal_refs(obj)


def to_external(obj: Any, client=None) -> Any:
    """Convert internal weave refs in `obj` to external refs using the client."""
    c = _require_client(client)
    return c.to_external_refs(obj)


def to_internal_project_id(project_id: str, client=None) -> str:
    c = _require_client(client)
    return c.to_internal_project_id(project_id)


def to_external_project_id(internal_project_id: str, client=None) -> str | None:
    c = _require_client(client)
    return c.to_external_project_id(internal_project_id)


def to_internal_run_id(run_id: str, client=None) -> str:
    c = _require_client(client)
    return c.to_internal_run_id(run_id)


def to_external_run_id(internal_run_id: str, client=None) -> str:
    c = _require_client(client)
    return c.to_external_run_id(internal_run_id)
