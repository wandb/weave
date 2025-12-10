"""Go-based trace server implementation using the weave-sender sidecar.

This module wraps the RemoteHTTPTraceServer and redirects call_start/call_end
operations through the Go sidecar for improved batching performance.
"""

from __future__ import annotations

import atexit
import json
import logging
from typing import TYPE_CHECKING

from typing_extensions import Self

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import go_sender_max_batch_size, go_sender_socket_path
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server_bindings.weave_sender_client import WeaveSenderClient

if TYPE_CHECKING:
    from weave.trace_server_bindings.models import ServerInfoRes

logger = logging.getLogger(__name__)


class GoSenderTraceServer(RemoteHTTPTraceServer):
    """Trace server that uses Go sidecar for call_start/call_end batching.

    This class extends RemoteHTTPTraceServer and overrides call_start and call_end
    to use the Go-based weave-sender sidecar for improved performance. All other
    operations are delegated to the parent class.

    The Go sidecar provides:
    - Efficient batching with configurable size and interval
    - Non-blocking enqueue (Python doesn't wait for HTTP)
    - Automatic retries with exponential backoff
    - Shared queue across multiple Python processes (via UDS)
    """

    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = True,
        *,
        remote_request_bytes_limit: int | None = None,
        auth: tuple[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        # Initialize parent without batching - Go handles that
        super().__init__(
            trace_server_url,
            should_batch=False,  # Disable Python batching
            remote_request_bytes_limit=remote_request_bytes_limit
            or (31 * 1024 * 1024),
            auth=auth,
            extra_headers=extra_headers,
        )

        self._go_sender: WeaveSenderClient | None = None
        self._go_sender_initialized = False
        self._should_use_go_sender = should_batch  # Only use Go sender if batching enabled
        self._auth = auth
        self._extra_headers = extra_headers

        # Register cleanup
        atexit.register(self._cleanup)

    def _ensure_go_sender(self) -> WeaveSenderClient:
        """Lazily initialize the Go sender client."""
        if self._go_sender is None:
            socket_path = go_sender_socket_path()
            self._go_sender = WeaveSenderClient(socket_path=socket_path)

        if not self._go_sender_initialized:
            auth_param = None
            if self._auth:
                auth_param = (self._auth[0], self._auth[1])

            config = {}
            max_batch = go_sender_max_batch_size()
            if max_batch is not None:
                config["max_batch_size"] = max_batch

            self._go_sender.init(
                server_url=self.trace_server_url,
                auth=auth_param,
                headers=self._extra_headers,
                config=config if config else None,
            )
            self._go_sender_initialized = True
            logger.debug("Go sender initialized successfully")

        return self._go_sender

    def _cleanup(self) -> None:
        """Clean up Go sender on exit."""
        if self._go_sender is not None:
            try:
                self._go_sender.disconnect()
            except Exception:
                pass

    @classmethod
    def from_env(cls, should_batch: bool = True) -> Self:
        return cls(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str]) -> None:
        """Set authentication credentials."""
        super().set_auth(auth)
        self._auth = auth

        # Re-initialize Go sender with new auth if already initialized
        if self._go_sender_initialized and self._go_sender is not None:
            self._go_sender_initialized = False
            self._ensure_go_sender()

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call, using Go sender."""
        if not self._should_use_go_sender:
            return super().call_start(req)

        sender = self._ensure_go_sender()

        # Ensure we have IDs
        if req.start.id is None or req.start.trace_id is None:
            raise ValueError("CallStartReq must have id and trace_id")

        # Serialize the request
        payload = json.loads(req.model_dump_json(by_alias=True))

        # Enqueue to Go sender (fire-and-forget for speed)
        sender.enqueue_async([{
            "type": "start",
            "payload": payload,
        }])

        return tsi.CallStartRes(id=req.start.id, trace_id=req.start.trace_id)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """End a call, using Go sender."""
        if not self._should_use_go_sender:
            return super().call_end(req)

        sender = self._ensure_go_sender()

        # Serialize the request
        payload = json.loads(req.model_dump_json(by_alias=True))

        # Enqueue to Go sender (fire-and-forget for speed)
        sender.enqueue_async([{
            "type": "end",
            "payload": payload,
        }])

        return tsi.CallEndRes()

    def flush(self) -> None:
        """Flush pending items in Go sender."""
        if self._go_sender is not None and self._go_sender_initialized:
            self._go_sender.flush()

    def wait_queue_empty(self) -> None:
        """Wait until the queue is empty.

        This flushes any pending items and blocks until all items have been
        picked up by the batcher. HTTP requests may still be in flight.
        """
        if self._go_sender is not None and self._go_sender_initialized:
            self._go_sender.wait_queue_empty()

    def wait_idle(self) -> None:
        """Wait until all items have been sent to the server.

        This flushes any pending items and blocks until all in-flight
        HTTP requests complete. Use this for accurate benchmarking.
        """
        if self._go_sender is not None and self._go_sender_initialized:
            self._go_sender.wait_idle()

    def stats(self) -> dict[str, int] | None:
        """Get Go sender statistics."""
        if self._go_sender is not None and self._go_sender_initialized:
            try:
                return self._go_sender.stats()
            except Exception:
                return None
        return None
