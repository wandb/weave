"""Tests for annotation queue span items APIs.

These tests cover the span-based annotation queue extensions for agent observability.
"""

import datetime
import uuid

import pytest

from tests.trace.server_utils import find_server_layer
from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.common_interface import AnnotationQueueSpanItemsFilter
from weave.trace_server.http_service_interface import SpanRef


def _skip_if_sqlite(client):
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")


def _get_ch_server(client) -> ClickHouseTraceServer:
    return find_server_layer(client.server, ClickHouseTraceServer)


def _make_span(project_id: str, **overrides) -> AgentSpanCHInsertable:
    """Create a span with sensible defaults."""
    defaults = {
        "project_id": project_id,
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "invoke_agent",
        "agent_name": "test-agent",
        "provider_name": "openai",
        "request_model": "gpt-4o",
        "input_tokens": 100,
        "output_tokens": 50,
        "conversation_id": "conv-1",
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_server: ClickHouseTraceServer, spans: list[AgentSpanCHInsertable]):
    """Insert spans into the ClickHouse spans table."""
    rows = [genai_span_to_row(s) for s in spans]
    ch_server.ch_client.insert(
        "spans",
        data=rows,
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


def _create_span_queue(client, name="Test Span Queue", scorer_refs=None) -> str:
    """Create a span-type annotation queue and return its ID."""
    if scorer_refs is None:
        scorer_refs = ["weave:///entity/project/scorer/test:abc123"]

    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client.project_id,
        name=name,
        description="A test span annotation queue",
        queue_type="span",
        scorer_refs=scorer_refs,
        wb_user_id="test_user",
    )
    res = client.server.annotation_queue_create(create_req)
    return res.id


# ============================================================================
# Queue creation with queue_type
# ============================================================================


def test_annotation_queue_create_span_type(client):
    """Test creating a queue with queue_type='span'."""
    _skip_if_sqlite(client)

    queue_id = _create_span_queue(client, name="Span Review Queue")

    read_res = client.server.annotation_queue_read(
        tsi.AnnotationQueueReadReq(
            project_id=client.project_id,
            queue_id=queue_id,
        )
    )
    assert read_res.queue.queue_type == "span"
    assert read_res.queue.name == "Span Review Queue"


def test_annotation_queue_create_default_type(client):
    """Test that default queue_type is 'call'."""
    _skip_if_sqlite(client)

    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client.project_id,
        name="Default Queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        wb_user_id="test_user",
    )
    res = client.server.annotation_queue_create(create_req)

    read_res = client.server.annotation_queue_read(
        tsi.AnnotationQueueReadReq(
            project_id=client.project_id,
            queue_id=res.id,
        )
    )
    assert read_res.queue.queue_type == "call"


def test_annotation_queue_query_includes_queue_type(client):
    """Test that querying queues returns queue_type for both types."""
    _skip_if_sqlite(client)

    # Create one of each type
    _create_span_queue(client, name="Span Queue")

    create_call_req = tsi.AnnotationQueueCreateReq(
        project_id=client.project_id,
        name="Call Queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        queue_type="call",
        wb_user_id="test_user",
    )
    client.server.annotation_queue_create(create_call_req)

    # Query all queues
    queues = list(
        client.server.annotation_queues_query_stream(
            tsi.AnnotationQueuesQueryReq(project_id=client.project_id)
        )
    )

    types = {q.queue_type for q in queues}
    assert "span" in types
    assert "call" in types


# ============================================================================
# Add spans to queue
# ============================================================================


def test_annotation_queue_add_spans_basic(client):
    """Test adding spans to a span queue."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span1 = _make_span(client.project_id, agent_name="agent-A")
    span2 = _make_span(client.project_id, agent_name="agent-B")
    _insert_spans(ch_server, [span1, span2])

    # Add spans to queue
    res = client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[
                SpanRef(trace_id=span1.trace_id, span_id=span1.span_id),
                SpanRef(trace_id=span2.trace_id, span_id=span2.span_id),
            ],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    assert res.added_count == 2
    assert res.duplicates == 0


def test_annotation_queue_add_spans_duplicate_prevention(client):
    """Test that adding the same (trace_id, span_id) twice is deduplicated."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span = _make_span(client.project_id)
    _insert_spans(ch_server, [span])

    span_ref = SpanRef(trace_id=span.trace_id, span_id=span.span_id)

    # First add
    res1 = client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[span_ref],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )
    assert res1.added_count == 1
    assert res1.duplicates == 0

    # Second add (duplicate)
    res2 = client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[span_ref],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )
    assert res2.added_count == 0
    assert res2.duplicates == 1


def test_annotation_queue_add_spans_same_trace_different_spans(client):
    """Test that different spans from the same trace can coexist in a queue."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    trace_id = uuid.uuid4().hex
    span1 = _make_span(
        client.project_id,
        trace_id=trace_id,
        operation_name="invoke_agent",
    )
    span2 = _make_span(
        client.project_id,
        trace_id=trace_id,
        operation_name="execute_tool",
    )
    _insert_spans(ch_server, [span1, span2])

    res = client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[
                SpanRef(trace_id=span1.trace_id, span_id=span1.span_id),
                SpanRef(trace_id=span2.trace_id, span_id=span2.span_id),
            ],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    assert res.added_count == 2
    assert res.duplicates == 0


def test_annotation_queue_add_spans_nonexistent(client):
    """Test that adding spans that don't exist in the spans table adds 0."""
    _skip_if_sqlite(client)

    queue_id = _create_span_queue(client)

    res = client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[
                SpanRef(trace_id="nonexistent-trace", span_id="nonexistent-span"),
            ],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    assert res.added_count == 0
    assert res.duplicates == 0


# ============================================================================
# Query span items
# ============================================================================


def test_annotation_queue_span_items_query_basic(client):
    """Test basic querying of span queue items."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span = _make_span(client.project_id, agent_name="my-agent")
    _insert_spans(ch_server, [span])

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[SpanRef(trace_id=span.trace_id, span_id=span.span_id)],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    # Query items
    res = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
        )
    )

    assert len(res.items) == 1
    item = res.items[0]
    assert item.trace_id == span.trace_id
    assert item.span_id == span.span_id
    assert item.agent_name == "my-agent"
    assert item.operation_name == "invoke_agent"
    assert item.annotation_state == "unstarted"


def test_annotation_queue_span_items_query_with_pagination(client):
    """Test querying span items with limit and offset."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    spans = [
        _make_span(
            client.project_id,
            agent_name=f"agent-{i}",
            started_at=now + datetime.timedelta(seconds=i),
        )
        for i in range(5)
    ]
    _insert_spans(ch_server, spans)

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[SpanRef(trace_id=s.trace_id, span_id=s.span_id) for s in spans],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    # Get first page
    res1 = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
            limit=2,
            offset=0,
        )
    )
    assert len(res1.items) == 2

    # Get second page
    res2 = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
            limit=2,
            offset=2,
        )
    )
    assert len(res2.items) == 2

    # Ensure no overlap
    ids1 = {item.id for item in res1.items}
    ids2 = {item.id for item in res2.items}
    assert ids1.isdisjoint(ids2)


def test_annotation_queue_span_items_query_filter_by_agent_name(client):
    """Test filtering span queue items by agent_name."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span_a = _make_span(client.project_id, agent_name="agent-A")
    span_b = _make_span(client.project_id, agent_name="agent-B")
    _insert_spans(ch_server, [span_a, span_b])

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[
                SpanRef(trace_id=span_a.trace_id, span_id=span_a.span_id),
                SpanRef(trace_id=span_b.trace_id, span_id=span_b.span_id),
            ],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    # Filter by agent-A
    res = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
            filter=AnnotationQueueSpanItemsFilter(agent_name="agent-A"),
        )
    )

    assert len(res.items) == 1
    assert res.items[0].agent_name == "agent-A"


def test_annotation_queue_span_items_query_filter_by_operation_name(client):
    """Test filtering span queue items by operation_name."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span_agent = _make_span(client.project_id, operation_name="invoke_agent")
    span_tool = _make_span(client.project_id, operation_name="execute_tool")
    _insert_spans(ch_server, [span_agent, span_tool])

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[
                SpanRef(trace_id=span_agent.trace_id, span_id=span_agent.span_id),
                SpanRef(trace_id=span_tool.trace_id, span_id=span_tool.span_id),
            ],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    res = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
            filter=AnnotationQueueSpanItemsFilter(operation_name="execute_tool"),
        )
    )

    assert len(res.items) == 1
    assert res.items[0].operation_name == "execute_tool"


def test_annotation_queue_span_items_query_with_position(client):
    """Test querying span items with position tracking."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    spans = [
        _make_span(
            client.project_id,
            started_at=now + datetime.timedelta(seconds=i),
        )
        for i in range(3)
    ]
    _insert_spans(ch_server, spans)

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[SpanRef(trace_id=s.trace_id, span_id=s.span_id) for s in spans],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    res = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
            include_position=True,
        )
    )

    assert len(res.items) == 3
    positions = [item.position_in_queue for item in res.items]
    assert positions == [1, 2, 3]


# ============================================================================
# Stats for span queues
# ============================================================================


def test_annotation_queues_stats_span_queue(client):
    """Test that stats work for span-type queues."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span = _make_span(client.project_id)
    _insert_spans(ch_server, [span])

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[SpanRef(trace_id=span.trace_id, span_id=span.span_id)],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    stats_res = client.server.annotation_queues_stats(
        tsi.AnnotationQueuesStatsReq(
            project_id=client.project_id,
            queue_ids=[queue_id],
        )
    )

    assert len(stats_res.stats) == 1
    assert stats_res.stats[0].queue_id == queue_id
    assert stats_res.stats[0].total_items == 1
    assert stats_res.stats[0].completed_items == 0


# ============================================================================
# Progress tracking on span items
# ============================================================================


def test_span_item_progress_update_completed(client):
    """Test updating a span queue item to 'completed'."""
    _skip_if_sqlite(client)

    ch_server = _get_ch_server(client)
    queue_id = _create_span_queue(client)

    span = _make_span(client.project_id)
    _insert_spans(ch_server, [span])

    client.server.annotation_queue_add_spans(
        tsi.AnnotationQueueAddSpansReq(
            project_id=client.project_id,
            queue_id=queue_id,
            span_refs=[SpanRef(trace_id=span.trace_id, span_id=span.span_id)],
            display_mode="chat_view",
            wb_user_id="test_user",
        )
    )

    # Get the item ID
    items_res = client.server.annotation_queue_span_items_query(
        tsi.AnnotationQueueSpanItemsQueryReq(
            project_id=client.project_id,
            queue_id=queue_id,
        )
    )
    item_id = items_res.items[0].id

    # Update to completed
    progress_res = client.server.annotator_queue_items_progress_update(
        tsi.AnnotatorQueueItemsProgressUpdateReq(
            project_id=client.project_id,
            queue_id=queue_id,
            item_id=item_id,
            annotation_state="completed",
            wb_user_id="annotator_1",
        )
    )

    assert progress_res.item.annotation_state == "completed"

    # Verify stats updated
    stats_res = client.server.annotation_queues_stats(
        tsi.AnnotationQueuesStatsReq(
            project_id=client.project_id,
            queue_ids=[queue_id],
        )
    )
    assert stats_res.stats[0].completed_items == 1
