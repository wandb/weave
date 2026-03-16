"""V2 SQLite storage for calls (Tier 1).

Wraps the existing SqliteTraceServer to explicitly satisfy
CallsStorageInterface. In the future the storage logic would
live here directly; for now this is a typed composition wrapper.
"""

from __future__ import annotations

from weave.trace_server.sqlite_trace_server import SqliteTraceServer
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndRes,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
)


class SqliteCallsStorage:
    """Raw SQLite INSERT/UPDATE operations for calls.

    Delegates to the existing SqliteTraceServer implementation.
    No business logic, no ID translation — just database operations.
    """

    def __init__(self, server: SqliteTraceServer) -> None:
        self._server = server

    def call_start(self, req: CallStartReq) -> CallStartRes:
        return self._server.call_start(req)

    def call_end(self, req: CallEndReq) -> CallEndRes:
        return self._server.call_end(req)

    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res:
        return self._server.call_start_v2(req)

    def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes:
        return self._server.calls_complete(req)
