"""V2 ClickHouse storage for calls (Tier 1).

Wraps the existing ClickHouseTraceServer to explicitly satisfy
CallsStorageInterface. In the future the storage logic would
live here directly; for now this is a typed composition wrapper.
"""

from __future__ import annotations

from weave.trace_server.clickhouse_trace_server_batched import (
    ClickHouseTraceServer,
)
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


class ClickHouseCallsStorage:
    """Raw ClickHouse INSERT operations for calls.

    Delegates to the existing ClickHouseTraceServer implementation.
    No business logic, no ID translation — just database operations.
    """

    def __init__(self, server: ClickHouseTraceServer) -> None:
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
