"""Resolves external project IDs (entity/project) to internal project IDs.

This module encapsulates:
- Lazy resolution and caching of external-to-internal project ID mappings
- The "disabled" event that shuts down client-side digests for the session
- Digest validation error classification and the disable-on-mismatch safety net
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError as HTTPError

from weave.trace.settings import should_enable_client_side_digests
from weave.trace_server.errors import DigestMismatchError
from weave.trace_server.trace_server_interface import ProjectsInfoReq

if TYPE_CHECKING:
    from weave.trace_server_bindings.client_interface import TraceServerClientInterface

logger = logging.getLogger(__name__)


class ResolverDisabledError(Exception):
    """Raised when resolve() is called on a disabled ProjectIdResolver."""


class ProjectIdResolver:
    """Caches external-to-internal project ID mappings.

    Populated lazily: the first call to internal_project_id for a given
    external ID triggers a projects_info call to the server.  Subsequent
    accesses return the cached result.

    The resolver can be permanently disabled for the session via
    disable_after_validation_error or disable(), which sets a threading.Event
    so that all future lookups return None (forcing the fallback path).
    """

    def __init__(self, server: TraceServerClientInterface) -> None:
        self._server = server
        # Event is set when digests should be disabled; unset (default) = enabled.
        # Using an Event instead of a bare bool is thread-safe without the GIL.
        self._disabled_event = threading.Event()
        self._cache: dict[str, str] = {}

    def get_internal_project_id(self, ext_project_id: str) -> str | None:
        """Return the internal project ID for ext_project_id, or None.

        Returns None (forcing the fallback path) when:
        - The feature flag is off
        - The resolver has been disabled after a digest mismatch
        - Resolution failed (server doesn't support it, project not found, etc.)
        """
        if self._disabled_event.is_set():
            return None
        if not should_enable_client_side_digests():
            return None
        cached = self._cache.get(ext_project_id)
        if cached is not None:
            return cached
        logger.debug(
            "Client digest: resolving internal project ID for %s",
            ext_project_id,
        )
        return self.resolve(ext_project_id)

    def resolve(self, ext_project_id: str) -> str | None:
        """Resolve an external project ID to internal, with caching.

        Called directly by convert_cross_project_ref for foreign projects.

        Returns None when the project is not found or on transient errors.
        Transient errors are not cached so the next access retries.

        Raises ResolverDisabledError if the resolver has been disabled.
        """
        if self._disabled_event.is_set():
            raise ResolverDisabledError(
                "ProjectIdResolver is disabled; cannot resolve project IDs"
            )
        cached = self._cache.get(ext_project_id)
        if cached is not None:
            return cached
        try:
            results = self._server.projects_info(
                ProjectsInfoReq(project_ids=[ext_project_id])
            )
        except AttributeError:
            # Endpoint doesn't exist (e.g. bare SQLite) — disable entirely.
            logger.debug(
                "projects_info not available, disabling resolver",
            )
            self._disabled_event.set()
            return None
        except Exception:
            # Transient error (network, timeout) — don't cache, retry next time.
            logger.debug(
                "Failed to resolve internal project ID for %s, will retry next access",
                ext_project_id,
                exc_info=True,
            )
            return None
        else:
            if results:
                internal_id = results[0].internal_project_id
                self._cache[ext_project_id] = internal_id
                return internal_id
            # Empty result (project not found) — don't cache, could be transient.
            return None

    def invalidate(self, ext_project_id: str) -> None:
        """Force re-resolution of a project ID on next access."""
        self._cache.pop(ext_project_id, None)

    def disable(self) -> None:
        """Disable the resolver. All future lookups return None."""
        self._disabled_event.set()

    def enable(self) -> None:
        """Re-enable the resolver (primarily for testing)."""
        self._disabled_event.clear()

    # ------------------------------------------------------------------
    # Digest validation error handling
    # ------------------------------------------------------------------

    @staticmethod
    def is_digest_validation_error(exc: Exception) -> bool:
        """Return True if exc indicates a server-side digest mismatch."""
        if isinstance(exc, DigestMismatchError):
            return True
        return (
            isinstance(exc, HTTPError)
            and exc.response is not None
            and exc.response.status_code == 409
        )

    def disable_after_validation_error(self, exc: Exception, ref_uri: str) -> None:
        """Permanently disable client-side digests for this session.

        Called when the server rejects an expected_digest.  Idempotent —
        only warns on the first call.
        """
        if self._disabled_event.is_set():
            return
        self._cache.clear()
        self._disabled_event.set()
        logger.warning(
            "Client digest: server validation failed for %s; "
            "disabling fast path for this session",
            ref_uri,
            exc_info=exc,
        )

    def on_fire_and_forget_done(self, future: Future[Any], *, ref_uri: str) -> None:
        """Done-callback for fire-and-forget futures.

        If the future raised a digest validation error, disables the fast path.
        Non-digest errors are ignored here (FutureExecutor already logs them).
        """
        try:
            future.result()
        except Exception as exc:
            if self.is_digest_validation_error(exc):
                self.disable_after_validation_error(exc, ref_uri)

    @property
    def is_disabled(self) -> bool:
        return self._disabled_event.is_set()
