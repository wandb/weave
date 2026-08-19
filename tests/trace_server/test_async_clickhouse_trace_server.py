"""Tests for `AsyncClickHouseTraceServer.acompletions_create`."""

import asyncio
import base64
import datetime
import random
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import pytest_asyncio

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
)
from tests.trace_server.helpers import make_project_id
from weave.shared import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.types import AgentSpansQueryReq
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.datadog import _db_insert_path
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
)
from weave.trace_server.ids import generate_id

LITELLM_ACOMPLETION_PATCH = (
    "weave.trace_server.async_clickhouse_trace_server.lite_llm_acompletion"
)


def _make_req(
    *,
    track_llm_call: bool,
    model: str = "gpt-4o-mini",
    prompt: str | None = None,
    project_id: str = "p1",
) -> tsi.CompletionsCreateReq:
    inputs_kwargs: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
    }
    if prompt is not None:
        inputs_kwargs["prompt"] = prompt
    return tsi.CompletionsCreateReq(
        project_id=project_id,
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
async def test_deferred_returns_real_span_without_inserting() -> None:
    """The deferred path builds a real, fully populated span and returns it for
    the caller to bulk-insert; nothing is written per call. An untracked call
    returns no span.
    """
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    try:
        with (
            patch(
                LITELLM_ACOMPLETION_PATCH,
                new=AsyncMock(
                    return_value=tsi.CompletionsCreateRes(
                        response={"choices": [{"x": 1}]}
                    )
                ),
            ),
            # The project-retention lookup is the only CH read in the build; stub
            # it (and the client it reads through) so a real span is built
            # without a live ClickHouse.
            patch(
                "weave.trace_server.clickhouse_trace_server_batched.get_project_retention_days",
                return_value=0,
            ),
            patch.object(
                ClickHouseTraceServer,
                "ch_client",
                new_callable=PropertyMock,
                return_value=MagicMock(),
            ),
            patch.object(srv, "_log_completion_call") as log_mock,
        ):
            result, span = await srv.acompletions_create_deferred(
                _make_req(track_llm_call=True, project_id="p1")
            )
            untracked = await srv.acompletions_create_deferred(
                _make_req(track_llm_call=False)
            )
        assert isinstance(span, AgentSpanCHInsertable)
        assert span.project_id == "p1"
        assert span.span_id == result.span_id == result.weave_call_id
        assert untracked.span is None
        assert log_mock.call_count == 0
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_ainsert_completion_spans_bulk_writes_on_executor() -> None:
    """Collected spans are bulk-written once via the CH executor, tagged with the
    `completions_create_batch` insert path; empty input no-ops.
    """
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(host="test_host", ch_executor=ch_executor)
    spans = [object(), object()]
    observed = {"thread_id": None, "path": None}

    def _capture_insert(_spans: object) -> None:
        observed["thread_id"] = threading.get_ident()
        observed["path"] = _db_insert_path.get()

    try:
        with patch.object(
            srv, "_insert_spans_sync", side_effect=_capture_insert
        ) as insert_mock:
            await srv.ainsert_completion_spans([])
            await srv.ainsert_completion_spans(spans)
        insert_mock.assert_called_once_with(spans)
        assert observed["thread_id"] != threading.get_ident()
        assert observed["path"] == "completions_create_batch"
    finally:
        ch_executor.shutdown(wait=True)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_secret_fetcher")
async def test_deferred_span_flow_lands_queryable_spans(ch_server) -> None:
    """End-to-end: two traced completions go through the deferred path, the spans
    they return bulk-insert via `ainsert_completion_spans`, and both read back
    from ClickHouse by the call ids the deferred path returned.
    """
    project_id = make_project_id("deferred_flow")
    ch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ch-pool")
    srv = AsyncClickHouseTraceServer(
        host=ch_server._host,
        port=ch_server._port,
        database=ch_server._database,
        ch_executor=ch_executor,
    )
    try:
        with patch(
            LITELLM_ACOMPLETION_PATCH,
            new=AsyncMock(
                return_value=tsi.CompletionsCreateRes(response={"choices": [{"x": 1}]})
            ),
        ):
            d1 = await srv.acompletions_create_deferred(
                _make_req(track_llm_call=True, project_id=project_id)
            )
            d2 = await srv.acompletions_create_deferred(
                _make_req(track_llm_call=True, project_id=project_id)
            )
            spans = [d.span for d in (d1, d2) if d.span is not None]
            assert len(spans) == 2  # built, not yet inserted
            await srv.ainsert_completion_spans(spans)
    finally:
        ch_executor.shutdown(wait=True)

    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    assert res.total_count == 2
    assert {d1.result.span_id, d2.result.span_id} == {s.span_id for s in res.spans}


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


# ---- calls_query_stream_async -------------------------------------------


def _seed_calls(server: ClickHouseTraceServer, project_id: str, n: int) -> list[str]:
    call_ids = []
    for i in range(n):
        call_id = generate_id()
        call_ids.append(call_id)
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=generate_id(),
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    op_name=f"op-{i % 3}",
                    attributes={"i": i},
                    inputs={"x": i, "nested": {"y": [i, i + 1]}},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    exception=None if i % 4 else "ValueError: boom",
                    output={"result": i * 2},
                    summary={"usage": {"model-a": {"total_tokens": i, "requests": 1}}},
                )
            )
        )
    return call_ids


def _make_async_twin(ch_server: ClickHouseTraceServer) -> AsyncClickHouseTraceServer:
    return AsyncClickHouseTraceServer(
        host=ch_server._host,
        port=ch_server._port,
        user=ch_server._user,
        password=ch_server._password,
        database=ch_server._database,
    )


@pytest.mark.asyncio
async def test_calls_query_stream_async_matches_sync(ch_server):
    # token_costs validation requires ids decoding to "ProjectInternalId:<n>".
    project_id = base64.b64encode(
        f"ProjectInternalId:{random.randrange(10**8)}".encode()
    ).decode()
    _seed_calls(ch_server, project_id, 25)
    aserver = _make_async_twin(ch_server)

    reqs = [
        tsi.CallsQueryReq(project_id=project_id),
        tsi.CallsQueryReq(project_id=project_id, columns=["id", "op_name", "inputs"]),
        tsi.CallsQueryReq(
            project_id=project_id,
            sort_by=[tsi.SortBy(field="started_at", direction="desc")],
            limit=10,
        ),
        tsi.CallsQueryReq(project_id=project_id, include_costs=True, limit=10),
    ]
    for req in reqs:
        sync_calls = [c.model_dump() for c in ch_server.calls_query_stream(req)]
        async_calls = [
            c.model_dump() async for c in aserver.calls_query_stream_async(req)
        ]
        assert len(sync_calls) > 0
        assert async_calls == sync_calls


@pytest.mark.asyncio
async def test_calls_query_stream_async_matches_sync_with_feedback(ch_server):
    project_id = make_project_id("async_stream_feedback")
    call_ids = _seed_calls(ch_server, project_id, 12)
    for call_id in call_ids[:5]:
        ch_server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=ri.InternalCallRef(project_id=project_id, id=call_id).uri,
                feedback_type="wandb.reaction.1",
                payload={"emoji": "👍", "alias": ":thumbs_up:"},
                wb_user_id="u1",
            )
        )
    aserver = _make_async_twin(ch_server)

    req = tsi.CallsQueryReq(project_id=project_id, include_feedback=True)
    sync_calls = [c.model_dump() for c in ch_server.calls_query_stream(req)]
    async_calls = [c.model_dump() async for c in aserver.calls_query_stream_async(req)]
    assert len(sync_calls) == 12
    assert async_calls == sync_calls
    # The hydrated feedback must actually be present, not merely equal-and-empty.
    with_feedback = [
        c
        for c in async_calls
        if c["summary"] and c["summary"].get("weave", {}).get("feedback")
    ]
    assert len(with_feedback) == 5


@pytest.mark.asyncio
async def test_calls_query_stream_async_matches_sync_with_expand_columns(ch_server):
    project_id = make_project_id("async_stream_expand")
    created = ch_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id, object_id="target", val={"greeting": "hello"}
            )
        )
    )
    ref = ri.InternalObjectRef(
        project_id=project_id, name="target", version=created.digest
    ).uri
    for i in range(6):
        call_id = generate_id()
        ch_server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=generate_id(),
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    op_name=f"op-{i}",
                    attributes={},
                    inputs={"obj": ref},
                )
            )
        )
    aserver = _make_async_twin(ch_server)

    req = tsi.CallsQueryReq(
        project_id=project_id,
        expand_columns=["inputs.obj"],
        return_expanded_column_values=True,
    )
    sync_calls = [c.model_dump() for c in ch_server.calls_query_stream(req)]
    async_calls = [c.model_dump() async for c in aserver.calls_query_stream_async(req)]
    assert len(sync_calls) == 6
    assert async_calls == sync_calls
    # Refs must be expanded to values, not left as ref strings.
    assert all(c["inputs"]["obj"]["greeting"] == "hello" for c in async_calls)


@pytest.mark.asyncio
async def test_calls_query_stream_async_concurrent_streams(ch_server):
    project_id = make_project_id("async_stream_conc")
    _seed_calls(ch_server, project_id, 20)
    aserver = _make_async_twin(ch_server)

    async def collect() -> list[str]:
        req = tsi.CallsQueryReq(project_id=project_id)
        return [c.id async for c in aserver.calls_query_stream_async(req)]

    results = await asyncio.gather(*[collect() for _ in range(8)])
    assert all(len(r) == 20 for r in results)
    assert all(r == results[0] for r in results)


@pytest.mark.asyncio
async def test_calls_query_stream_async_abandoned_stream_keeps_client_usable(
    ch_server,
):
    project_id = make_project_id("async_stream_abandon")
    _seed_calls(ch_server, project_id, 20)
    aserver = _make_async_twin(ch_server)

    req = tsi.CallsQueryReq(project_id=project_id)
    agen = aserver.calls_query_stream_async(req)
    got = 0
    async for _ in agen:
        got += 1
        if got >= 3:
            break
    await agen.aclose()

    remaining = [c.id async for c in aserver.calls_query_stream_async(req)]
    assert len(remaining) == 20
