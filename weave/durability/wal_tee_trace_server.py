"""WAL tee middleware — records API writes to a JSONL WAL alongside normal dispatch.

Sits in the trace server middleware chain and intercepts write operations.
Each intercepted method:

    1. Serializes the request and appends it to the WAL (fire-and-forget).
    2. Delegates to the underlying trace server.
    3. Returns the response from the underlying server.

The WAL write never blocks or fails the real request — if WAL I/O errors,
the failure is logged and the request proceeds normally.
"""

from __future__ import annotations

import base64
import datetime
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel

from weave.durability.wal import WALWriter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.delegating_trace_server import (
    DelegatingTraceServerMixin,
)

logger = logging.getLogger(__name__)


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable values.

    Handles bytes → base64, datetime → isoformat, Enum → value,
    and traverses dicts/lists/tuples.
    """
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    return obj


def _req_to_dict(req: BaseModel) -> dict:
    """Convert a pydantic request to a JSON-serializable dict.

    Uses model_dump() then converts bytes → base64 and datetime → isoformat
    to ensure full JSON serializability.
    """
    return _make_json_safe(req.model_dump())


class WALTeeTraceServer(DelegatingTraceServerMixin, TraceServerClientInterface):
    """Middleware that tees write operations to a JSONL WAL.

    The WAL records every write intent so that a future consumer can replay
    them for crash recovery or offline sync.  Read operations pass straight
    through to the delegate without touching the WAL.
    """

    _next_trace_server: TraceServerClientInterface
    _wal_writer: WALWriter

    optional_delegated_methods = frozenset(
        {
            "get_call_processor",
            "get_feedback_processor",
            "projects_info",
        }
    )

    def __init__(
        self,
        next_trace_server: TraceServerClientInterface,
        wal_writer: WALWriter,
    ) -> None:
        self._next_trace_server = next_trace_server
        self._wal_writer = wal_writer

    def _tee(self, method_name: str, req: BaseModel) -> None:
        """Append a write request to the WAL.  Never raises."""
        try:
            self._wal_writer.write(
                {
                    "type": method_name,
                    "req": _req_to_dict(req),
                }
            )
        except Exception:
            logger.exception("Failed to write %s to WAL", method_name)

    def close(self) -> None:
        self._wal_writer.close()
        if hasattr(self._next_trace_server, "close"):
            self._next_trace_server.close()

    # -- Call write methods ------------------------------------------------

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        self._tee("call_start", req)
        return self._next_trace_server.call_start(req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        self._tee("call_end", req)
        return self._next_trace_server.call_end(req)

    def call_start_batch(
        self, req: tsi.CallCreateBatchReq
    ) -> tsi.CallCreateBatchRes:
        self._tee("call_start_batch", req)
        return self._next_trace_server.call_start_batch(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        self._tee("call_update", req)
        return self._next_trace_server.call_update(req)

    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        self._tee("calls_complete", req)
        return self._next_trace_server.calls_complete(req)

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        self._tee("call_start_v2", req)
        return self._next_trace_server.call_start_v2(req)

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
        self._tee("call_end_v2", req)
        return self._next_trace_server.call_end_v2(req)

    # -- Object write methods ----------------------------------------------

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        self._tee("obj_create", req)
        return self._next_trace_server.obj_create(req)

    # -- Table write methods -----------------------------------------------

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        self._tee("table_create", req)
        return self._next_trace_server.table_create(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        self._tee("table_update", req)
        return self._next_trace_server.table_update(req)

    # -- File write methods ------------------------------------------------

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        self._tee("file_create", req)
        return self._next_trace_server.file_create(req)

    # -- Feedback write methods --------------------------------------------

    def feedback_create(
        self, req: tsi.FeedbackCreateReq
    ) -> tsi.FeedbackCreateRes:
        self._tee("feedback_create", req)
        return self._next_trace_server.feedback_create(req)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        self._tee("feedback_create_batch", req)
        return self._next_trace_server.feedback_create_batch(req)

    def feedback_replace(
        self, req: tsi.FeedbackReplaceReq
    ) -> tsi.FeedbackReplaceRes:
        self._tee("feedback_replace", req)
        return self._next_trace_server.feedback_replace(req)

    # -- Cost write methods ------------------------------------------------

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        self._tee("cost_create", req)
        return self._next_trace_server.cost_create(req)
