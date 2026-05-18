"""Tests for `AsyncClickHouseTraceServer.acompletions_create`."""

import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context


class TestAcompletionsCreate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # asyncSetUp runs inside the test's event-loop context; a sync setUp
        # would leave the ContextVar set on the wrong context.
        self.server = AsyncClickHouseTraceServer(host="test_host")
        mock_ch_client = MagicMock()
        mock_ch_client.query.return_value = MagicMock(result_rows=[[0, 0]])
        self.server._thread_local.ch_client = mock_ch_client

        mock_secret_fetcher = MagicMock()
        mock_secret_fetcher.fetch.return_value = {"secrets": {"OPENAI_API_KEY": "k"}}
        self.token = _secret_fetcher_context.set(mock_secret_fetcher)

    async def asyncTearDown(self) -> None:
        _secret_fetcher_context.reset(self.token)

    def _make_req(self, *, track_llm_call: bool) -> tsi.CompletionsCreateReq:
        return tsi.CompletionsCreateReq(
            project_id="p1",
            wb_user_id="u1",
            track_llm_call=track_llm_call,
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "hi"}],
            ),
        )

    async def test_no_tracking_skips_ch_insert(self) -> None:
        with (
            patch(
                "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion",
                new=AsyncMock(
                    return_value=tsi.CompletionsCreateRes(response={"ok": True})
                ),
            ),
            patch.object(self.server, "_insert_call_complete") as insert_mock,
            patch.object(self.server, "_insert_call_batch") as batch_mock,
        ):
            res = await self.server.acompletions_create(
                self._make_req(track_llm_call=False)
            )
        assert res.response == {"ok": True}
        assert res.weave_call_id is None
        insert_mock.assert_not_called()
        batch_mock.assert_not_called()

    async def test_tracking_routes_through_log_completion_call(self) -> None:
        llm_res = tsi.CompletionsCreateRes(response={"choices": [{"x": 1}]})
        log_res = tsi.CompletionsCreateRes(
            response=llm_res.response, weave_call_id="call-xyz"
        )
        with (
            patch(
                "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion",
                new=AsyncMock(return_value=llm_res),
            ),
            patch.object(
                self.server, "_log_completion_call", return_value=log_res
            ) as log_mock,
        ):
            res = await self.server.acompletions_create(
                self._make_req(track_llm_call=True)
            )
        assert res.weave_call_id == "call-xyz"
        assert log_mock.call_count == 1
        forwarded_res = log_mock.call_args.args[3]
        assert forwarded_res is llm_res

    async def test_litellm_error_propagates_as_response_error(self) -> None:
        with patch(
            "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion",
            new=AsyncMock(
                return_value=tsi.CompletionsCreateRes(
                    response={"error": "rate-limited"}
                )
            ),
        ):
            res = await self.server.acompletions_create(
                self._make_req(track_llm_call=False)
            )
        assert res.response == {"error": "rate-limited"}


class TestAcompletionsCreateConcurrency(unittest.IsolatedAsyncioTestCase):
    """A 1-thread CH executor must not gate LLM-call concurrency."""

    async def test_many_in_flight_with_one_thread_ch_executor(self) -> None:
        server = AsyncClickHouseTraceServer(host="test_host")
        ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-ch")
        server.set_ch_executor(ch_executor)

        mock_ch_client = MagicMock()
        mock_ch_client.query.return_value = MagicMock(result_rows=[[0, 0]])
        server._thread_local.ch_client = mock_ch_client
        mock_secret_fetcher = MagicMock()
        mock_secret_fetcher.fetch.return_value = {"secrets": {"OPENAI_API_KEY": "k"}}
        token = _secret_fetcher_context.set(mock_secret_fetcher)
        try:
            peak = {"in_flight": 0, "current": 0}
            entry_event = asyncio.Event()
            release_event = asyncio.Event()

            async def slow_llm(**_kwargs: object) -> tsi.CompletionsCreateRes:
                peak["current"] += 1
                peak["in_flight"] = max(peak["in_flight"], peak["current"])
                if peak["current"] >= 50:
                    entry_event.set()
                await release_event.wait()
                peak["current"] -= 1
                return tsi.CompletionsCreateRes(response={"ok": True})

            with patch(
                "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion",
                new=slow_llm,
            ):
                tasks = [
                    asyncio.create_task(
                        server.acompletions_create(
                            tsi.CompletionsCreateReq(
                                project_id="p",
                                wb_user_id="u",
                                track_llm_call=False,
                                inputs=tsi.CompletionsCreateRequestInputs(
                                    model="gpt-4o-mini",
                                    messages=[{"role": "user", "content": "hi"}],
                                ),
                            )
                        )
                    )
                    for _ in range(50)
                ]
                await asyncio.wait_for(entry_event.wait(), timeout=5)
                assert peak["in_flight"] == 50
                release_event.set()
                await asyncio.gather(*tasks)
        finally:
            _secret_fetcher_context.reset(token)
            ch_executor.shutdown(wait=True)
