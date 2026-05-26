"""HTTP transport for the BYOB storage resolver.

POSTs `{ "project_id": ... }` to gorilla's internal resolve endpoint and
materializes the typed `ResolvedStorageTarget`. Auth is by service identity
token (header) - gorilla authorizes the named identity, not just header
presence.

The transport raises plain exceptions on failure; the resolver applies the
fail-closed truth table.
"""

from __future__ import annotations

import logging

import ddtrace
import requests

from weave.trace_server.byob.models import ResolvedStorageTarget

logger = logging.getLogger(__name__)

DEFAULT_GORILLA_RESOLVE_TIMEOUT_MS = 500
GORILLA_RPC_RETRY_ATTEMPTS = 2
RESOLVE_PATH = "/internal/weave-trace/storage/resolve"


class GorillaTransportError(Exception):
    """Wraps any gorilla-side failure (HTTP, parse, auth)."""


class GorillaHttpClient:
    def __init__(
        self,
        base_url: str,
        service_identity_token: str,
        timeout_ms: int = DEFAULT_GORILLA_RESOLVE_TIMEOUT_MS,
        retries: int = GORILLA_RPC_RETRY_ATTEMPTS,
        session: requests.Session | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + RESOLVE_PATH
        self._token = service_identity_token
        self._timeout_s = timeout_ms / 1000.0
        self._retries = retries
        self._session = session or requests.Session()

    @ddtrace.tracer.wrap(name="weave.byob.gorilla.resolve")
    def resolve(self, project_id: str) -> ResolvedStorageTarget:
        attempt = 0
        last_error: Exception | None = None
        while attempt < self._retries:
            attempt += 1
            try:
                return self._resolve_once(project_id)
            except Exception as e:
                last_error = e
                if attempt >= self._retries:
                    break
        assert last_error is not None
        raise GorillaTransportError(
            f"gorilla resolve failed for project {project_id} "
            f"({self._url}) after {attempt} attempts: {last_error!s}"
        ) from last_error

    def _resolve_once(self, project_id: str) -> ResolvedStorageTarget:
        response = self._session.post(
            self._url,
            json={"project_id": project_id},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout_s,
        )
        if response.status_code == 404:
            raise GorillaTransportError(f"unknown project_id {project_id}")
        response.raise_for_status()
        return ResolvedStorageTarget.model_validate(response.json())
