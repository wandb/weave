"""Tests for `AsyncClickHouseTraceServer.acompletions_create`."""

import asyncio
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.datadog import _db_insert_path
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
)

LITELLM_ACOMPLETION_PATCH = (
    "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion"
)


def _make_req(
    *, track_llm_call: bool, model: str = "gpt-4o-mini", prompt: str | None = None
) -> tsi.CompletionsCreateReq:
    inputs_kwargs: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
    }
    if prompt is not None:
        inputs_kwargs["prompt"] = prompt
    return tsi.CompletionsCreateReq(
        project_id="p1",
        wb_user_id="u1",
        track_llm_call=track_llm_call,
        inputs=tsi.CompletionsCreateRequestInputs(**inputs_kwargs),
    )


@pytest.fixture
def _mock_secret_fetcher() -> AsyncIterator[MagicMock]:
    # Patch module-level `_secret_fetcher_context` bindings: a contextvar set in
    # an async fixture is invisible to `asyncio.to_thread`'s context snapshot.
    mock = MagicMock()
    mock.fetch.return_value = {"secrets": {"OPENAI_API_KEY": "k"}}
    fake_var = MagicMock()
    fake_var.get.return_value = mock
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched._secret_fetcher_context",
            fake_var,
        ),
        patch(
            "weave.trace_server.llm_completion._secret_fetcher_context",
            fake_var,
        ),
    ):
        yield mock


@pytest_asyncio.fixture
async def server(
    _mock_secret_fetcher: MagicMock,
) -> AsyncIterator[AsyncClickHouseTraceServer]:
    yield AsyncClickHouseTraceServer(host="test_host")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", [{"ok": True}, {"error": "rate-limited"}], ids=["success", "error"]
)
async def test_untracked_returns_litellm_response_verbatim(
    server: AsyncClickHouseTraceServer, response: dict[str, object]
) -> None:
    with patch(
        LITELLM_ACOMPLETION_PATCH,
        new=AsyncMock(return_value=tsi.CompletionsCreateRes(response=response)),
    ):
        res = await server.acompletions_create(_make_req(track_llm_call=False))
    assert res.response == response
    assert res.weave_call_id is None


@pytest.mark.asyncio
async def test_tracking_routes_through_log_completion_call(
    server: AsyncClickHouseTraceServer,
) -> None:
    llm_res = tsi.CompletionsCreateRes(response={"choices": [{"x": 1}]})
    log_res = tsi.CompletionsCreateRes(
        response=llm_res.response, weave_call_id="call-xyz"
    )
    with (
        patch(LITELLM_ACOMPLETION_PATCH, new=AsyncMock(return_value=llm_res)),
        patch.object(server, "_log_completion_call", return_value=log_res) as log_mock,
    ):
        res = await server.acompletions_create(_make_req(track_llm_call=True))
    assert res.weave_call_id == "call-xyz"
    assert log_mock.call_count == 1
    forwarded_res = log_mock.call_args.args[2]
    assert forwarded_res is llm_res


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_span_sink_defers_insert_to_caller() -> None:
    """With a `span_sink`, the traced-call span is appended for a later bulk
    insert instead of inserted per call; the per-call insert path is skipped.
    """
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    fake_span = object()
    buffered = tsi.CompletionsCreateRes(response={"ok": True}, weave_call_id="call-1")
    sink: list[object] = []
    try:
        with (
            patch(
                LITELLM_ACOMPLETION_PATCH,
                new=AsyncMock(
                    return_value=tsi.CompletionsCreateRes(response={"ok": True})
                ),
            ),
            patch.object(
                srv, "_build_completion_call_span", return_value=(fake_span, buffered)
            ) as build_mock,
            patch.object(srv, "_log_completion_call") as log_mock,
        ):
            res = await srv.acompletions_create(
                _make_req(track_llm_call=True), span_sink=sink
            )
        assert res is buffered
        assert sink == [fake_span]
        assert build_mock.call_count == 1
        assert log_mock.call_count == 0
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_ainsert_completion_spans_bulk_writes_on_executor() -> None:
    """Collected spans are bulk-written once via the CH executor; empty no-ops."""
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    spans = [object(), object()]
    try:
        with patch.object(srv, "_insert_spans_sync") as insert_mock:
            await srv.ainsert_completion_spans([])
            await srv.ainsert_completion_spans(spans)
        insert_mock.assert_called_once_with(spans)
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_prep_short_circuit_returns_without_calling_litellm(
    server: AsyncClickHouseTraceServer,
) -> None:
    short_circuit = tsi.CompletionsCreateRes(response={"error": "no model"})
    acompletion = AsyncMock()
    with (
        patch.object(server, "_prepare_completion_request", return_value=short_circuit),
        patch(LITELLM_ACOMPLETION_PATCH, new=acompletion),
    ):
        res = await server.acompletions_create(_make_req(track_llm_call=True))
    assert res is short_circuit
    assert acompletion.await_count == 0


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("model", "prompt"),
    [
        ("custom::myprovider::mymodel", None),
        ("gpt-4o-mini", "my_prompt:v1"),
    ],
    ids=["custom_provider", "prompt_request"],
)
async def test_real_prep_blocking_calls_run_off_loop(
    server: AsyncClickHouseTraceServer,
    model: str,
    prompt: str | None,
) -> None:
    # Real prep's blocking `obj_read` (custom:: lookup, prompt resolution) must
    # run off-loop; assert it executes on a non-loop thread, not a stub.
    loop_tid = threading.get_ident()
    obj_read_tids: list[int] = []

    def _stub_obj_read(_req: object) -> tsi.ObjReadRes:
        obj_read_tids.append(threading.get_ident())
        raise RuntimeError("intentional - test only proves off-loop execution")

    acompletion = AsyncMock()
    with (
        patch.object(server, "obj_read", side_effect=_stub_obj_read),
        patch(LITELLM_ACOMPLETION_PATCH, new=acompletion),
    ):
        res = await server.acompletions_create(
            _make_req(track_llm_call=False, model=model, prompt=prompt)
        )

    assert obj_read_tids, (
        "obj_read was never called - prep did not exercise blocking shape"
    )
    assert all(tid != loop_tid for tid in obj_read_tids)
    assert "error" in res.response
    assert acompletion.await_count == 0


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_log_completion_call_runs_on_executor_thread() -> None:
    # CH insert must hop to ch_executor (freeing the loop), with the insert-path
    # tag propagated across the thread boundary via contextvars.copy_context.
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    caller_thread_id = threading.get_ident()
    observed = {"thread_id": None, "thread_name": None, "path": None}

    def _capture_log(
        req: object,
        prep: object,
        res: object,
        start_time: object,
        end_time: object,
    ) -> tsi.CompletionsCreateRes:
        observed["thread_id"] = threading.get_ident()
        observed["thread_name"] = threading.current_thread().name
        observed["path"] = _db_insert_path.get()
        return tsi.CompletionsCreateRes(response={"ok": True}, weave_call_id="call-1")

    try:
        with (
            patch(
                LITELLM_ACOMPLETION_PATCH,
                new=AsyncMock(
                    return_value=tsi.CompletionsCreateRes(response={"ok": True})
                ),
            ),
            patch.object(srv, "_log_completion_call", side_effect=_capture_log),
        ):
            await srv.acompletions_create(_make_req(track_llm_call=True))

        assert observed["thread_id"] != caller_thread_id
        assert observed["thread_name"].startswith("ch-pool")
        assert observed["path"] == "completions_create"
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_many_in_flight_with_one_thread_ch_executor() -> None:
    """A 1-thread CH executor must not gate LLM-call concurrency."""
    target = 50
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-ch")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    try:
        peak = {"in_flight": 0, "current": 0}
        entry_event = asyncio.Event()
        release_event = asyncio.Event()

        async def slow_llm(**_kwargs: object) -> tsi.CompletionsCreateRes:
            peak["current"] += 1
            peak["in_flight"] = max(peak["in_flight"], peak["current"])
            if peak["current"] >= target:
                entry_event.set()
            await release_event.wait()
            peak["current"] -= 1
            return tsi.CompletionsCreateRes(response={"ok": True})

        with patch(LITELLM_ACOMPLETION_PATCH, new=slow_llm):
            tasks = [
                asyncio.create_task(
                    srv.acompletions_create(_make_req(track_llm_call=False))
                )
                for _ in range(target)
            ]
            await asyncio.wait_for(entry_event.wait(), timeout=5)
            assert peak["in_flight"] == target
            release_event.set()
            await asyncio.gather(*tasks)
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_cancellation_during_acompletion_propagates(
    server: AsyncClickHouseTraceServer,
) -> None:
    # Cancelling while parked in `await lite_llm_acompletion` raises
    # CancelledError out; the thread-run prep/insert branches aren't cancellable.
    entered = asyncio.Event()

    async def _hanging_llm(**_kwargs: object) -> tsi.CompletionsCreateRes:
        entered.set()
        await asyncio.sleep(60)
        return tsi.CompletionsCreateRes(response={"ok": True})  # pragma: no cover

    with patch(LITELLM_ACOMPLETION_PATCH, new=_hanging_llm):
        task = asyncio.create_task(
            server.acompletions_create(_make_req(track_llm_call=False))
        )
        await asyncio.wait_for(entered.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_external_adapter_routes_to_async_backend() -> None:
    inner = AsyncClickHouseTraceServer(host="test_host")
    adapter = ExternalTraceServer(inner, DummyIdConverter(), username_resolver=None)

    expected = tsi.CompletionsCreateRes(response={"ok": True}, weave_call_id="abc")
    with patch.object(
        inner, "acompletions_create", new=AsyncMock(return_value=expected)
    ) as a_mock:
        res = await adapter.acompletions_create(_make_req(track_llm_call=False))

    assert res.response == {"ok": True}
    assert a_mock.await_count == 1


@pytest.mark.asyncio
async def test_external_adapter_falls_back_for_sync_backend() -> None:
    # Non-async backend: adapter must hop to a thread so the loop stays free.
    sync_inner = MagicMock(spec=tsi.FullTraceServerInterface)
    sync_inner.completions_create.return_value = tsi.CompletionsCreateRes(
        response={"ok": True}
    )
    adapter = ExternalTraceServer(
        sync_inner, DummyIdConverter(), username_resolver=None
    )

    loop_tid = threading.get_ident()
    captured = {"tid": None}

    def _capture(_req: object) -> tsi.CompletionsCreateRes:
        captured["tid"] = threading.get_ident()
        return tsi.CompletionsCreateRes(response={"ok": True})

    sync_inner.completions_create.side_effect = _capture
    res = await adapter.acompletions_create(_make_req(track_llm_call=False))
    assert res.response == {"ok": True}
    assert captured["tid"] != loop_tid
