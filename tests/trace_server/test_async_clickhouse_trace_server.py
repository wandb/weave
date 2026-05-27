"""Tests for `AsyncClickHouseTraceServer.acompletions_create`."""

import asyncio
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.clickhouse_trace_server_batched import CompletionPrepResult
from weave.trace_server.datadog import _db_insert_path
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
    IdConverter,
)

LITELLM_ACOMPLETION_PATCH = (
    "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion"
)
CONCURRENT_LLM_CALL_TARGET = 50


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
    # Async fixtures + ContextVars don't mix under pytest-asyncio: the
    # fixture's task context is separate from the test's, and
    # `asyncio.to_thread` snapshots the test task's context — so a fetcher
    # set inside the fixture is invisible on the executor thread. Patch the
    # module-level bindings every reader (`clickhouse_trace_server_batched`
    # and `llm_completion`) imports from `secret_fetcher_context` instead.
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
async def test_no_tracking_returns_passthrough_response(
    server: AsyncClickHouseTraceServer,
) -> None:
    with patch(
        LITELLM_ACOMPLETION_PATCH,
        new=AsyncMock(return_value=tsi.CompletionsCreateRes(response={"ok": True})),
    ):
        res = await server.acompletions_create(_make_req(track_llm_call=False))
    assert res.response == {"ok": True}
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
    # signature is (req, prep, res, start_time, end_time)
    forwarded_res = log_mock.call_args.args[2]
    assert forwarded_res is llm_res


@pytest.mark.asyncio
async def test_litellm_error_propagates_as_response_error(
    server: AsyncClickHouseTraceServer,
) -> None:
    with patch(
        LITELLM_ACOMPLETION_PATCH,
        new=AsyncMock(
            return_value=tsi.CompletionsCreateRes(response={"error": "rate-limited"})
        ),
    ):
        res = await server.acompletions_create(_make_req(track_llm_call=False))
    assert res.response == {"error": "rate-limited"}


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
async def test_prep_runs_off_the_event_loop_thread(
    server: AsyncClickHouseTraceServer,
) -> None:
    loop_thread_id = threading.get_ident()
    captured = {"thread_id": None}

    def _capture_prep(req: object) -> CompletionPrepResult:
        captured["thread_id"] = threading.get_ident()
        return CompletionPrepResult(
            [{"role": "user", "content": "hi"}], MagicMock(api_key="k")
        )

    with (
        patch.object(server, "_prepare_completion_request", side_effect=_capture_prep),
        patch(
            LITELLM_ACOMPLETION_PATCH,
            new=AsyncMock(return_value=tsi.CompletionsCreateRes(response={"ok": True})),
        ),
    ):
        await server.acompletions_create(_make_req(track_llm_call=False))

    assert captured["thread_id"] != loop_thread_id


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
    # The async path's correctness rests on prep's blocking I/O (`self.obj_read`)
    # running off-loop. Two real-world shapes force obj_read inside prep:
    # (1) custom:: provider lookup, (2) prompt resolution. Stub obj_read to
    # capture the executing thread id and short-circuit prep, then assert
    # obj_read actually ran on a non-loop thread — proving asyncio.to_thread
    # wrapped real prep, not just a stub.
    loop_tid = threading.get_ident()
    obj_read_tids: list[int] = []

    def _stub_obj_read(_req: object) -> tsi.ObjReadRes:
        obj_read_tids.append(threading.get_ident())
        # Short-circuiting via exception is fine: prep catches it and returns
        # a CompletionsCreateRes error response (see _prepare_completion_request).
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
    # prep returned a short-circuit error response, litellm was never invoked.
    assert "error" in res.response
    assert acompletion.await_count == 0


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_log_completion_call_runs_on_executor_thread() -> None:
    # The whole point of the async path: CH insert hops to the executor so the
    # loop thread is free during the LLM wait. Assert _log_completion_call
    # actually executes on a thread from ch_executor, not the caller's thread.
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
        # @tag_db_insert_path + contextvars.copy_context propagation: the
        # path tag must be visible on the executor thread.
        assert observed["path"] == "completions_create"
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_many_in_flight_with_one_thread_ch_executor() -> None:
    """A 1-thread CH executor must not gate LLM-call concurrency."""
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-ch")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    try:
        peak = {"in_flight": 0, "current": 0}
        entry_event = asyncio.Event()
        release_event = asyncio.Event()

        async def slow_llm(**_kwargs: object) -> tsi.CompletionsCreateRes:
            peak["current"] += 1
            peak["in_flight"] = max(peak["in_flight"], peak["current"])
            if peak["current"] >= CONCURRENT_LLM_CALL_TARGET:
                entry_event.set()
            await release_event.wait()
            peak["current"] -= 1
            return tsi.CompletionsCreateRes(response={"ok": True})

        with patch(LITELLM_ACOMPLETION_PATCH, new=slow_llm):
            tasks = [
                asyncio.create_task(
                    srv.acompletions_create(_make_req(track_llm_call=False))
                )
                for _ in range(CONCURRENT_LLM_CALL_TARGET)
            ]
            await asyncio.wait_for(entry_event.wait(), timeout=5)
            assert peak["in_flight"] == CONCURRENT_LLM_CALL_TARGET
            release_event.set()
            await asyncio.gather(*tasks)
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_cancellation_during_acompletion_propagates(
    server: AsyncClickHouseTraceServer,
) -> None:
    # Codifies the docstring claim: cancelling the asyncio task while we're
    # parked inside `await lite_llm_acompletion(...)` raises CancelledError
    # out of acompletions_create. This is the only branch where cancellation
    # is meaningful — prep and the CH insert run on threads and aren't
    # cancellable mid-execution.
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


class _IdentityConverter(IdConverter):
    def ext_to_int_project_id(self, project_id: str) -> str:
        return project_id

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


@pytest.mark.asyncio
async def test_external_adapter_routes_to_async_backend() -> None:
    inner = AsyncClickHouseTraceServer(host="test_host")
    adapter = ExternalTraceServer(inner, _IdentityConverter(), username_resolver=None)

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
        sync_inner, _IdentityConverter(), username_resolver=None
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
