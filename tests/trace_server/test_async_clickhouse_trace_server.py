"""Tests for `AsyncClickHouseTraceServer.acompletions_create`.

These cover:
  * response shape parity with the sync `completions_create`
  * CH insert is invoked when `track_llm_call` is true and skipped otherwise
  * the LLM wait does NOT hold a thread - the central design goal of this
    class. We assert this by giving the server a bounded 1-thread executor
    for the CH-insert step and counting how many concurrent `acompletions_create`
    coroutines we can have in flight during a slow `litellm.acompletion`.
"""

import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context


def _make_litellm_response(content: str = "ok") -> MagicMock:
    """Match the `.model_dump()` shape `lite_llm_acompletion` calls into."""
    res = MagicMock()
    res.model_dump.return_value = {
        "id": "id-1",
        "model": "gpt-test",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    return res


class TestAcompletionsCreate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # asyncSetUp runs inside the test's event-loop context, so ContextVar
        # values set here propagate to the test method (a sync setUp would
        # leave the ContextVar in the wrong context).
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
        """`track_llm_call=False` returns the response without persisting."""
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
        """`track_llm_call=True` dispatches `_log_completion_call` on the executor.

        We don't reproduce the full CH write path here; that's covered by the
        existing sync `completions_create` tests. We assert the contract:
        post-LLM logging is invoked exactly once with the LLM response and
        request, and the result it returns flows back to the caller.
        """
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
        # Sanity: the LLM result we synthesized is what got forwarded.
        forwarded_res = log_mock.call_args.args[3]
        assert forwarded_res is llm_res

    async def test_litellm_error_propagates_as_response_error(self) -> None:
        """Provider errors come back as `{"error": ...}` per existing contract."""
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
    """Asserts the design promise: no thread held during the LLM wait.

    A 1-thread CH executor means at most one CH insert in flight at a time.
    But we should still see 50 `acompletions_create` coroutines all parked in
    `lite_llm_acompletion` simultaneously, because nothing about the LLM wait
    occupies the CH executor or any other thread.
    """

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
            # Track peak concurrency inside the awaited LLM call.
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
                # 50 LLM awaits in flight, but only one thread in the CH pool.
                # The promise of the design: thread count does not gate
                # LLM-call concurrency.
                assert peak["in_flight"] == 50
                release_event.set()
                await asyncio.gather(*tasks)
        finally:
            _secret_fetcher_context.reset(token)
            ch_executor.shutdown(wait=True)
