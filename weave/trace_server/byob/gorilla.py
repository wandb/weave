"""One-shot helper that fetches a `ResolvedStorageTarget` from gorilla.

Single function, single HTTP call, no retries. 404 maps to a specific
not-found error so the resolver can apply the §4.3 truth table; any other
error bubbles up to be wrapped by the resolver's fail-closed handler.
"""

from __future__ import annotations

import requests

from weave.trace_server.byob.types import ResolvedStorageTarget

DEFAULT_TIMEOUT_S = 0.5
RESOLVE_PATH = "/internal/weave-trace/storage/resolve"


class GorillaResolveError(Exception):
    pass


class GorillaUnknownProjectError(GorillaResolveError):
    pass


def fetch_storage_target(
    base_url: str, project_id: str, timeout_s: float = DEFAULT_TIMEOUT_S
) -> ResolvedStorageTarget:
    response = requests.post(
        base_url.rstrip("/") + RESOLVE_PATH,
        json={"project_id": project_id},
        timeout=timeout_s,
    )
    if response.status_code == 404:
        raise GorillaUnknownProjectError(project_id)
    response.raise_for_status()
    return ResolvedStorageTarget.model_validate(response.json())
