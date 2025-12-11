"""Trace server client that delegates hot-path operations to a Go sidecar via Unix Domain Socket."""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
from typing import TYPE_CHECKING, Any, Iterator

from weave.trace_server_bindings.client_interface import TraceServerClientInterface

if TYPE_CHECKING:
    from weave.trace_server import trace_server_interface as tsi
    from weave.trace_server_bindings.models import ServerInfoRes

logger = logging.getLogger(__name__)

# Default socket path
DEFAULT_SOCKET_PATH = "/tmp/weave_sidecar.sock"


class SidecarConnection:
    """Manages a single connection to the sidecar via Unix Domain Socket."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._buffer = b""

    def _connect(self) -> socket.socket:
        """Create a new connection to the sidecar."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)  # 5 second timeout for operations
        sock.connect(self.socket_path)
        return sock

    def _ensure_connected(self) -> socket.socket:
        """Ensure we have a valid connection, reconnecting if needed."""
        if self._socket is None:
            self._socket = self._connect()
        return self._socket

    def _disconnect(self) -> None:
        """Close the current connection."""
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            self._buffer = b""

    def send_request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the sidecar and receive the response.

        Args:
            method: The method name (e.g., "call_start", "call_end")
            payload: The request payload as a dict

        Returns:
            The response dict from the sidecar

        Raises:
            SidecarError: If communication with the sidecar fails
        """
        request = {"method": method, "payload": payload}
        request_bytes = json.dumps(request).encode("utf-8") + b"\n"

        with self._lock:
            try:
                sock = self._ensure_connected()
                sock.sendall(request_bytes)

                # Read response (newline-delimited JSON)
                response = self._read_response(sock)
                return response
            except (OSError, socket.error, json.JSONDecodeError) as e:
                self._disconnect()
                raise SidecarError(f"Sidecar communication failed: {e}") from e

    def _read_response(self, sock: socket.socket) -> dict[str, Any]:
        """Read a single JSON response from the socket."""
        while True:
            # Check if we have a complete message in the buffer
            if b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                return json.loads(line.decode("utf-8"))

            # Read more data
            chunk = sock.recv(4096)
            if not chunk:
                raise SidecarError("Connection closed by sidecar")
            self._buffer += chunk

    def close(self) -> None:
        """Close the connection."""
        with self._lock:
            self._disconnect()


class SidecarError(Exception):
    """Error communicating with the sidecar."""

    pass


class SidecarTraceServer(TraceServerClientInterface):
    """Trace server that delegates call_start/call_end to a Go sidecar.

    All other methods are delegated to the backend server. If the sidecar
    is unavailable, operations fall back to the backend with a warning.
    """

    def __init__(
        self,
        backend_server: TraceServerClientInterface,
        socket_path: str = DEFAULT_SOCKET_PATH,
    ):
        """Initialize the sidecar trace server.

        Args:
            backend_server: The backend server to delegate non-sidecar operations to
            socket_path: Path to the Unix domain socket for the sidecar
        """
        self.backend_server = backend_server
        self.socket_path = socket_path
        self._connection: SidecarConnection | None = None
        self._sidecar_available = True
        self._sidecar_warned = False
        self._lock = threading.Lock()

    def _get_connection(self) -> SidecarConnection | None:
        """Get or create a connection to the sidecar."""
        if not self._sidecar_available:
            return None

        with self._lock:
            if self._connection is None:
                # Check if socket exists
                if not os.path.exists(self.socket_path):
                    self._mark_sidecar_unavailable("Socket file does not exist")
                    return None

                try:
                    self._connection = SidecarConnection(self.socket_path)
                except Exception as e:
                    self._mark_sidecar_unavailable(f"Failed to connect: {e}")
                    return None

            return self._connection

    def _mark_sidecar_unavailable(self, reason: str) -> None:
        """Mark the sidecar as unavailable and log a warning."""
        self._sidecar_available = False
        if not self._sidecar_warned:
            logger.warning(
                f"Weave sidecar unavailable ({reason}). "
                f"Falling back to direct backend communication. "
                f"To disable sidecar, unset WEAVE_USE_SIDECAR."
            )
            self._sidecar_warned = True

    def _send_to_sidecar(self, method: str, payload: dict[str, Any]) -> bool:
        """Try to send a request to the sidecar.

        Returns:
            True if sent successfully, False if fallback to backend is needed
        """
        conn = self._get_connection()
        if conn is None:
            return False

        try:
            response = conn.send_request(method, payload)
            if not response.get("success"):
                error = response.get("error", "Unknown error")
                logger.warning(f"Sidecar returned error: {error}")
                return False
            return True
        except SidecarError as e:
            logger.warning(f"Sidecar error: {e}. Falling back to backend.")
            with self._lock:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None
            return False

    def flush(self) -> bool:
        """Flush all pending items in the sidecar to the backend.

        This is a synchronous operation that blocks until all pending
        items have been sent to the backend.

        Returns:
            True if flush succeeded, False if sidecar unavailable
        """
        conn = self._get_connection()
        if conn is None:
            return False

        try:
            response = conn.send_request("flush", {})
            return response.get("success", False)
        except SidecarError as e:
            logger.warning(f"Sidecar flush error: {e}")
            return False

    # ==========================================================================
    # Hot-path methods: delegate to sidecar with fallback to backend
    # ==========================================================================

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Send call start to sidecar, falling back to backend if unavailable."""
        payload = req.model_dump(mode="json", by_alias=True)

        if self._send_to_sidecar("call_start", payload):
            # Sidecar accepted the request - return immediately
            # The sidecar will batch and forward to the backend
            from weave.trace_server import trace_server_interface as tsi

            return tsi.CallStartRes(
                id=req.start.id,
                trace_id=req.start.trace_id,
            )

        # Fall back to backend
        return self.backend_server.call_start(req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """Send call end to sidecar, falling back to backend if unavailable."""
        payload = req.model_dump(mode="json", by_alias=True)

        if self._send_to_sidecar("call_end", payload):
            # Sidecar accepted the request - return immediately
            from weave.trace_server import trace_server_interface as tsi

            return tsi.CallEndRes()

        # Fall back to backend
        return self.backend_server.call_end(req)

    # ==========================================================================
    # All other methods: delegate directly to backend
    # ==========================================================================

    @classmethod
    def from_env(cls, *args: Any, **kwargs: Any) -> SidecarTraceServer:
        raise NotImplementedError("Use constructor directly with backend_server")

    def server_info(self) -> ServerInfoRes:
        return self.backend_server.server_info()

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        return self.backend_server.ensure_project_exists(entity, project)

    # Call API (non-hot-path)
    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self.backend_server.call_start_batch(req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self.backend_server.call_read(req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self.backend_server.calls_query(req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self.backend_server.calls_query_stream(req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self.backend_server.calls_query_stats(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self.backend_server.calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self.backend_server.call_update(req)

    # Object API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self.backend_server.obj_create(req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self.backend_server.obj_read(req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self.backend_server.objs_query(req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self.backend_server.obj_delete(req)

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self.backend_server.table_create(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self.backend_server.table_update(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self.backend_server.table_query(req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self.backend_server.table_query_stream(req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self.backend_server.table_query_stats(req)

    # Refs API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self.backend_server.refs_read_batch(req)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self.backend_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self.backend_server.file_content_read(req)

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self.backend_server.feedback_create(req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self.backend_server.feedback_query(req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self.backend_server.feedback_purge(req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self.backend_server.feedback_replace(req)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self.backend_server.cost_create(req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self.backend_server.cost_query(req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self.backend_server.cost_purge(req)

    # Actions API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self.backend_server.actions_execute_batch(req)

    # Completions API
    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self.backend_server.completions_create(req)

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self.backend_server.otel_export(req)

    # Object interface methods (V2)
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self.backend_server.op_create(req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self.backend_server.op_read(req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self.backend_server.ops_query(req)

    def obj_schema_create(self, req: tsi.ObjSchemaCreateReq) -> tsi.ObjSchemaCreateRes:
        return self.backend_server.obj_schema_create(req)

    def obj_schema_read(self, req: tsi.ObjSchemaReadReq) -> tsi.ObjSchemaReadRes:
        return self.backend_server.obj_schema_read(req)
