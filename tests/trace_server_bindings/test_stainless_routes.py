"""Tests for the requests StainlessRemoteHTTPTraceServer sends.

These tests drive the binding through the vendored generated client over an
httpx.MockTransport, so what they assert is the request the generated resource
builds. The file is not gated to the stainless shard, so it also runs against
the default one.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass

import httpx
import pytest
from pydantic import BaseModel

from tests.trace_server_bindings.conftest import generate_call_start_end_pair
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents import types as agent_types
from weave.trace_server.interface import query
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient

BASE_URL = "http://example.com"
PROJECT = "entity/project"
V2 = "/v2/entity/project"
START = datetime.datetime(2026, 8, 20, tzinfo=datetime.timezone.utc)
END = datetime.datetime(2026, 8, 21, tzinfo=datetime.timezone.utc)

V2_RESPONSE = {
    "code": "def f(): pass",
    "created_at": "2026-08-20T00:00:00Z",
    "dataset": "weave:///entity/project/object/ds:abc123",
    "digest": "abc123",
    "evaluation": "weave:///entity/project/object/ev:abc123",
    "evaluation_ref": "weave:///entity/project/object/ev:abc123",
    "evaluation_run_id": "run-id",
    "inputs": {},
    "model": "weave:///entity/project/object/m:abc123",
    "model_ref": "weave:///entity/project/object/m:abc123",
    "name": "my-object",
    "num_deleted": 1,
    "object_id": "my-object",
    "output": None,
    "prediction_id": "prediction-id",
    "rows": "weave:///entity/project/table/abc123",
    "score_id": "score-id",
    "score_op": "weave:///entity/project/op/s:abc123",
    "scorer": "weave:///entity/project/object/s:abc123",
    "scorers": [],
    "source_code": "def f(): pass",
    "success": True,
    "trials": 1,
    "value": None,
    "version_index": 0,
}

QUEUE = {
    "id": "q1",
    "project_id": PROJECT,
    "name": "my-queue",
    "description": "",
    "scorer_refs": [],
    "created_at": "2026-08-20T00:00:00Z",
    "created_by": "user-id",
    "updated_at": "2026-08-20T00:00:00Z",
}

ITEM = {
    "id": "i1",
    "queue_id": "q1",
    "project_id": PROJECT,
    "call_id": "c1",
    "call_op_name": "my-op",
    "call_trace_id": "t1",
    "call_started_at": "2026-08-20T00:00:00Z",
    "display_fields": [],
    "annotation_state": "unstarted",
    "created_at": "2026-08-20T00:00:00Z",
    "created_by": "user-id",
    "updated_at": "2026-08-20T00:00:00Z",
}

V1_RESPONSE = {
    "added_count": 0,
    "after_ms": 0,
    "agents": [],
    "attributes": [],
    "base_url": "http://example.com",
    "before_ms": 1,
    "bucket_type": "time",
    "buckets": [],
    "call_buckets": [],
    "call_id": "c1",
    "columns": [],
    "conversation_id": "conv1",
    "conversations": [],
    "duplicates": 0,
    "end": "2026-08-20T00:00:00Z",
    "evaluation_run_id": "run-id",
    "granularity": 86400,
    "groups": [],
    "has_more": False,
    "headers": {},
    "id": "q1",
    "item": ITEM,
    "items": [],
    "limit": 0,
    "messages": [],
    "name": "my-runtime",
    "offset": 0,
    "paths": [],
    "queue": QUEUE,
    "response": {},
    "results": [],
    "rows": [],
    "runtime_ids": [],
    "spans": [],
    "start": "2026-08-20T00:00:00Z",
    "stats": [],
    "status": {"code": "not_found"},
    "timezone": "UTC",
    "total_cache_creation_input_tokens": 0,
    "total_cache_read_input_tokens": 0,
    "total_conversations": 0,
    "total_count": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_reasoning_tokens": 0,
    "total_rows": 0,
    "total_turns": 0,
    "trace_id": "t1",
    "turns": [],
    "usage_buckets": [],
    "versions": [],
    "warnings": [],
}


@dataclass
class _MockServerResult:
    server: StainlessRemoteHTTPTraceServer
    requests: list[httpx.Request]


def _mock_server(
    response: httpx.Response,
) -> _MockServerResult:
    """Return a server that answers every request with `response`.

    The binding builds its own generated client and takes no transport, so the
    test swaps in one backed by an httpx.MockTransport.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response

    server = StainlessRemoteHTTPTraceServer(BASE_URL, should_batch=False)
    server._stainless_client = StainlessClient(
        base_url=BASE_URL,
        username="",
        password="",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    return _MockServerResult(server=server, requests=requests)


@pytest.mark.parametrize(
    ("method_name", "req", "expected_method", "expected_path", "res_type"),
    [
        pytest.param(
            "op_create",
            tsi.OpCreateReq(
                project_id=PROJECT, name="my-object", source_code="def f(): pass"
            ),
            "POST",
            f"{V2}/ops",
            tsi.OpCreateRes,
            id="op_create",
        ),
        pytest.param(
            "op_read",
            tsi.OpReadReq(project_id=PROJECT, object_id="my-object", digest="abc123"),
            "GET",
            f"{V2}/ops/my-object/versions/abc123",
            tsi.OpReadRes,
            id="op_read",
        ),
        pytest.param(
            "dataset_create",
            tsi.DatasetCreateReq(project_id=PROJECT, name="my-object", rows=[]),
            "POST",
            f"{V2}/datasets",
            tsi.DatasetCreateRes,
            id="dataset_create",
        ),
        pytest.param(
            "dataset_read",
            tsi.DatasetReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/datasets/my-object/versions/abc123",
            tsi.DatasetReadRes,
            id="dataset_read",
        ),
        pytest.param(
            "scorer_create",
            tsi.ScorerCreateReq(
                project_id=PROJECT, name="my-object", op_source_code="def f(): pass"
            ),
            "POST",
            f"{V2}/scorers",
            tsi.ScorerCreateRes,
            id="scorer_create",
        ),
        pytest.param(
            "scorer_read",
            tsi.ScorerReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/scorers/my-object/versions/abc123",
            tsi.ScorerReadRes,
            id="scorer_read",
        ),
        pytest.param(
            "evaluation_create",
            tsi.EvaluationCreateReq(
                project_id=PROJECT, name="my-object", dataset="ds-ref"
            ),
            "POST",
            f"{V2}/evaluations",
            tsi.EvaluationCreateRes,
            id="evaluation_create",
        ),
        pytest.param(
            "evaluation_read",
            tsi.EvaluationReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/evaluations/my-object/versions/abc123",
            tsi.EvaluationReadRes,
            id="evaluation_read",
        ),
        pytest.param(
            "model_create",
            tsi.ModelCreateReq(
                project_id=PROJECT, name="my-object", source_code="def f(): pass"
            ),
            "POST",
            f"{V2}/models",
            tsi.ModelCreateRes,
            id="model_create",
        ),
        pytest.param(
            "model_read",
            tsi.ModelReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/models/my-object/versions/abc123",
            tsi.ModelReadRes,
            id="model_read",
        ),
        pytest.param(
            "evaluation_run_create",
            tsi.EvaluationRunCreateReq(
                project_id=PROJECT, evaluation="ev-ref", model="m-ref"
            ),
            "POST",
            f"{V2}/evaluation_runs",
            tsi.EvaluationRunCreateRes,
            id="evaluation_run_create",
        ),
        pytest.param(
            "evaluation_run_read",
            tsi.EvaluationRunReadReq(project_id=PROJECT, evaluation_run_id="run-id"),
            "GET",
            f"{V2}/evaluation_runs/run-id",
            tsi.EvaluationRunReadRes,
            id="evaluation_run_read",
        ),
        pytest.param(
            "evaluation_run_delete",
            tsi.EvaluationRunDeleteReq(
                project_id=PROJECT, evaluation_run_ids=["run-id"]
            ),
            "DELETE",
            f"{V2}/evaluation_runs",
            tsi.EvaluationRunDeleteRes,
            id="evaluation_run_delete",
        ),
        pytest.param(
            "evaluation_run_finish",
            tsi.EvaluationRunFinishReq(project_id=PROJECT, evaluation_run_id="run-id"),
            "POST",
            f"{V2}/evaluation_runs/run-id/finish",
            tsi.EvaluationRunFinishRes,
            id="evaluation_run_finish",
        ),
        pytest.param(
            "prediction_create",
            tsi.PredictionCreateReq(
                project_id=PROJECT, model="m-ref", inputs={}, output=None
            ),
            "POST",
            f"{V2}/predictions",
            tsi.PredictionCreateRes,
            id="prediction_create",
        ),
        pytest.param(
            "prediction_read",
            tsi.PredictionReadReq(project_id=PROJECT, prediction_id="prediction-id"),
            "GET",
            f"{V2}/predictions/prediction-id",
            tsi.PredictionReadRes,
            id="prediction_read",
        ),
        pytest.param(
            "prediction_delete",
            tsi.PredictionDeleteReq(
                project_id=PROJECT, prediction_ids=["prediction-id"]
            ),
            "DELETE",
            f"{V2}/predictions",
            tsi.PredictionDeleteRes,
            id="prediction_delete",
        ),
        pytest.param(
            "prediction_finish",
            tsi.PredictionFinishReq(project_id=PROJECT, prediction_id="prediction-id"),
            "POST",
            f"{V2}/predictions/prediction-id/finish",
            tsi.PredictionFinishRes,
            id="prediction_finish",
        ),
        pytest.param(
            "score_create",
            tsi.ScoreCreateReq(
                project_id=PROJECT,
                prediction_id="prediction-id",
                scorer="s-ref",
                value=None,
            ),
            "POST",
            f"{V2}/scores",
            tsi.ScoreCreateRes,
            id="score_create",
        ),
        pytest.param(
            "score_read",
            tsi.ScoreReadReq(project_id=PROJECT, score_id="score-id"),
            "GET",
            f"{V2}/scores/score-id",
            tsi.ScoreReadRes,
            id="score_read",
        ),
        pytest.param(
            "score_delete",
            tsi.ScoreDeleteReq(project_id=PROJECT, score_ids=["score-id"]),
            "DELETE",
            f"{V2}/scores",
            tsi.ScoreDeleteRes,
            id="score_delete",
        ),
    ],
)
def test_v2_method_reaches_its_flat_route(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    res_type: type[BaseModel],
):
    """Test that a v2 method reaches its route with entity and project filled in."""
    mock_server = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    res = getattr(mock_server.server, method_name)(req)

    assert [(r.method, r.url.path) for r in mock_server.requests] == [
        (expected_method, expected_path)
    ]
    assert isinstance(res, res_type)


@pytest.mark.parametrize(
    ("method_name", "req", "expected_method", "expected_path", "res_type"),
    [
        pytest.param(
            "agent_spans_query",
            agent_types.AgentSpansQueryReq(project_id=PROJECT),
            "POST",
            "/agents/spans/query",
            agent_types.AgentSpansQueryRes,
            id="agent_spans_query",
        ),
        pytest.param(
            "agent_traces_chat",
            agent_types.AgentTraceChatReq(project_id=PROJECT, trace_id="t1"),
            "POST",
            "/agents/traces/chat",
            agent_types.AgentTraceChatRes,
            id="agent_traces_chat",
        ),
        pytest.param(
            "agent_conversation_chat",
            agent_types.AgentConversationChatReq(
                project_id=PROJECT, conversation_id="conv1"
            ),
            "POST",
            "/agents/conversations/chat",
            agent_types.AgentConversationChatRes,
            id="agent_conversation_chat",
        ),
        pytest.param(
            "agent_conversation_spans",
            agent_types.AgentConversationSpansReq(project_id=PROJECT),
            "POST",
            "/agents/conversations/spans",
            agent_types.AgentConversationSpansRes,
            id="agent_conversation_spans",
        ),
        pytest.param(
            "agent_agents_query",
            agent_types.AgentsQueryReq(project_id=PROJECT),
            "POST",
            "/agents/query",
            agent_types.AgentsQueryRes,
            id="agent_agents_query",
        ),
        pytest.param(
            "agent_versions_query",
            agent_types.AgentVersionsQueryReq(
                project_id=PROJECT, agent_name="my-agent"
            ),
            "POST",
            "/agents/agent-versions/query",
            agent_types.AgentVersionsQueryRes,
            id="agent_versions_query",
        ),
        pytest.param(
            "agent_spans_stats",
            agent_types.AgentSpanStatsReq(
                project_id=PROJECT,
                start=START,
                end=END,
                metrics=[
                    agent_types.AgentSpanStatsMetricSpec(
                        alias="input_tokens",
                        value_type="number",
                        value=agent_types.AgentSpanValueRef(
                            source="field", key="usage.input_tokens"
                        ),
                        aggregations=["sum"],
                    )
                ],
            ),
            "POST",
            "/agents/spans/stats",
            agent_types.AgentSpanStatsRes,
            id="agent_spans_stats",
        ),
        pytest.param(
            "agent_custom_attrs_schema",
            agent_types.AgentCustomAttrsSchemaReq(project_id=PROJECT),
            "POST",
            "/agents/spans/custom-attrs/schema",
            agent_types.AgentCustomAttrsSchemaRes,
            id="agent_custom_attrs_schema",
        ),
        pytest.param(
            "agent_search",
            agent_types.AgentSearchReq(project_id=PROJECT),
            "POST",
            "/agents/search",
            agent_types.AgentSearchRes,
            id="agent_search",
        ),
        pytest.param(
            "call_stats",
            tsi.CallStatsReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/calls/stats",
            tsi.CallStatsRes,
            id="call_stats",
        ),
        pytest.param(
            "feedback_stats",
            tsi.FeedbackStatsReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/feedback/stats",
            tsi.FeedbackStatsRes,
            id="feedback_stats",
        ),
        pytest.param(
            "feedback_aggregate",
            tsi.FeedbackAggregateReq(project_id=PROJECT, after_ms=0, before_ms=1),
            "POST",
            "/feedback/aggregate",
            tsi.FeedbackAggregateRes,
            id="feedback_aggregate",
        ),
        pytest.param(
            "feedback_payload_schema",
            tsi.FeedbackPayloadSchemaReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/feedback/payload_schema",
            tsi.FeedbackPayloadSchemaRes,
            id="feedback_payload_schema",
        ),
        pytest.param(
            "image_create",
            tsi.ImageGenerationCreateReq(
                project_id=PROJECT, inputs={"model": "dall-e-3", "prompt": "a cat"}
            ),
            "POST",
            "/image/create",
            tsi.ImageGenerationCreateRes,
            id="image_create",
        ),
        pytest.param(
            "evaluate_model",
            tsi.EvaluateModelReq(
                project_id=PROJECT,
                evaluation_ref="weave:///entity/project/object/ev:abc123",
                model_ref="weave:///entity/project/object/m:abc123",
            ),
            "POST",
            "/evaluations/evaluate_model",
            tsi.EvaluateModelRes,
            id="evaluate_model",
        ),
        pytest.param(
            "evaluation_status",
            tsi.EvaluationStatusReq(project_id=PROJECT, call_id="c1"),
            "POST",
            "/evaluations/status",
            tsi.EvaluationStatusRes,
            id="evaluation_status",
        ),
        pytest.param(
            "rescore",
            tsi.RescoreReq(
                project_id=PROJECT,
                source_evaluation_run_id="run-id",
                scorer_refs=["weave:///entity/project/object/s:abc123"],
            ),
            "POST",
            "/evaluations/rescore",
            tsi.RescoreRes,
            id="rescore",
        ),
        pytest.param(
            "calls_score",
            tsi.CallsScoreReq(
                project_id=PROJECT,
                call_ids=["c1"],
                scorer_refs=["weave:///entity/project/object/s:abc123"],
            ),
            "POST",
            "/calls/score",
            tsi.CallsScoreRes,
            id="calls_score",
        ),
        pytest.param(
            "annotation_queue_create",
            tsi.AnnotationQueueCreateReq(
                project_id=PROJECT, name="my-queue", scorer_refs=[]
            ),
            "POST",
            "/annotation_queues",
            tsi.AnnotationQueueCreateRes,
            id="annotation_queue_create",
        ),
        pytest.param(
            "annotation_queue_read",
            tsi.AnnotationQueueReadReq(project_id=PROJECT, queue_id="q1"),
            "GET",
            "/annotation_queues/q1",
            tsi.AnnotationQueueReadRes,
            id="annotation_queue_read",
        ),
        pytest.param(
            "annotation_queue_items_query",
            tsi.AnnotationQueueItemsQueryReq(project_id=PROJECT, queue_id="q1"),
            "POST",
            "/annotation_queues/q1/items/query",
            tsi.AnnotationQueueItemsQueryRes,
            id="annotation_queue_items_query",
        ),
        pytest.param(
            "annotation_queues_stats",
            tsi.AnnotationQueuesStatsReq(project_id=PROJECT, queue_ids=["q1"]),
            "POST",
            "/annotation_queues/stats",
            tsi.AnnotationQueuesStatsRes,
            id="annotation_queues_stats",
        ),
        pytest.param(
            "custom_runtime_apply",
            tsi.CustomRuntimeApplyReq(
                project_id=PROJECT,
                runtime_name="my-runtime",
                base_url="http://example.com",
                runtime_ids=[],
            ),
            "PUT",
            f"{V2}/runtimes/my-runtime",
            tsi.CustomRuntimeApplyRes,
            id="custom_runtime_apply",
        ),
        pytest.param(
            "eval_results_query",
            tsi.EvalResultsQueryReq(project_id=PROJECT, evaluation_call_ids=["c1"]),
            "POST",
            f"{V2}/eval_results/query",
            tsi.EvalResultsQueryRes,
            id="eval_results_query",
        ),
    ],
)
def test_route_reaches_its_path(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    res_type: type[BaseModel],
):
    """Test that a bound method reaches its route and parses the response back."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    res = getattr(mock_server.server, method_name)(req)

    assert [(r.method, r.url.path) for r in mock_server.requests] == [
        (expected_method, expected_path)
    ]
    assert isinstance(res, res_type)


@pytest.mark.parametrize(
    ("method_name", "req", "expected_method", "expected_path", "expected_body"),
    [
        pytest.param(
            "obj_add_tags",
            tsi.ObjAddTagsReq(
                project_id=PROJECT,
                object_id="my-obj",
                digest="abc123",
                tags=["production"],
                wb_user_id="user-id",
            ),
            "PUT",
            "/objs/my-obj/versions/abc123/tags",
            {"project_id": PROJECT, "tags": ["production"]},
            id="obj_add_tags",
        ),
        pytest.param(
            "obj_remove_tags",
            tsi.ObjRemoveTagsReq(
                project_id=PROJECT,
                object_id="my-obj",
                digest="abc123",
                tags=["production"],
                wb_user_id="user-id",
            ),
            "POST",
            "/objs/my-obj/versions/abc123/tags/remove",
            {"project_id": PROJECT, "tags": ["production"]},
            id="obj_remove_tags",
        ),
        pytest.param(
            "obj_set_aliases",
            tsi.ObjSetAliasesReq(
                project_id=PROJECT,
                object_id="my-obj",
                digest="abc123",
                aliases=["prod"],
                wb_user_id="user-id",
            ),
            "PUT",
            "/objs/my-obj/aliases",
            {"project_id": PROJECT, "digest": "abc123", "aliases": ["prod"]},
            id="obj_set_aliases",
        ),
        pytest.param(
            "obj_remove_aliases",
            tsi.ObjRemoveAliasesReq(
                project_id=PROJECT,
                object_id="my-obj",
                aliases=["prod"],
                wb_user_id="user-id",
            ),
            "POST",
            "/objs/my-obj/aliases/remove",
            {"project_id": PROJECT, "aliases": ["prod"]},
            id="obj_remove_aliases",
        ),
    ],
)
def test_tag_and_alias_method_omits_wb_user_id(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    expected_body: dict,
):
    """Test that the server-populated wb_user_id stays out of the request."""
    mock_server = _mock_server(httpx.Response(200, json={}))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        expected_method,
        expected_path,
    )
    assert json.loads(mock_server.requests[0].content) == expected_body


@pytest.mark.parametrize(
    ("method_name", "req", "expected_path"),
    [
        pytest.param(
            "tags_list",
            tsi.TagsListReq(project_id=PROJECT, wb_user_id="user-id"),
            "/tags",
            id="tags_list",
        ),
        pytest.param(
            "aliases_list",
            tsi.AliasesListReq(project_id=PROJECT, wb_user_id="user-id"),
            "/aliases",
            id="aliases_list",
        ),
    ],
)
def test_tag_and_alias_list_omits_wb_user_id(
    method_name: str, req: BaseModel, expected_path: str
):
    """Test that the server-populated wb_user_id stays out of the query."""
    mock_server = _mock_server(httpx.Response(200, json={"tags": [], "aliases": []}))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        "GET",
        expected_path,
    )
    assert dict(mock_server.requests[0].url.params) == {"project_id": PROJECT}


@pytest.mark.parametrize(
    ("method_name", "req", "expected_method", "expected_path", "expected_body"),
    [
        pytest.param(
            "annotation_queue_update",
            tsi.AnnotationQueueUpdateReq(
                project_id=PROJECT, queue_id="q1", wb_user_id="user-id"
            ),
            "PUT",
            "/annotation_queues/q1",
            {
                "project_id": PROJECT,
                "name": None,
                "description": None,
                "scorer_refs": None,
            },
            id="annotation_queue_update",
        ),
        pytest.param(
            "annotation_queue_add_calls",
            tsi.AnnotationQueueAddCallsReq(
                project_id=PROJECT,
                queue_id="q1",
                call_ids=["c1"],
                display_fields=[],
                wb_user_id="user-id",
            ),
            "POST",
            "/annotation_queues/q1/items",
            {"project_id": PROJECT, "call_ids": ["c1"], "display_fields": []},
            id="annotation_queue_add_calls",
        ),
        pytest.param(
            "annotator_queue_items_progress_update",
            tsi.AnnotatorQueueItemsProgressUpdateReq(
                project_id=PROJECT,
                queue_id="q1",
                item_id="i1",
                annotation_state="completed",
                wb_user_id="user-id",
            ),
            "POST",
            "/annotation_queues/q1/items/i1/progress",
            {"project_id": PROJECT, "annotation_state": "completed"},
            id="annotator_queue_items_progress_update",
        ),
    ],
)
def test_annotation_queue_method_omits_wb_user_id(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    expected_body: dict,
):
    """Test that the server-populated wb_user_id stays out of the request."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        expected_method,
        expected_path,
    )
    assert json.loads(mock_server.requests[0].content) == expected_body


@pytest.mark.parametrize(
    ("method_name", "req", "expected_method"),
    [
        pytest.param(
            "annotation_queue_read",
            tsi.AnnotationQueueReadReq(project_id=PROJECT, queue_id="q1"),
            "GET",
            id="annotation_queue_read",
        ),
        pytest.param(
            "annotation_queue_delete",
            tsi.AnnotationQueueDeleteReq(
                project_id=PROJECT, queue_id="q1", wb_user_id="user-id"
            ),
            "DELETE",
            id="annotation_queue_delete",
        ),
    ],
)
def test_annotation_queue_read_and_delete_send_project_id_in_the_query(
    method_name: str, req: BaseModel, expected_method: str
):
    """Test that a bodyless annotation queue route carries project_id in the query."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        expected_method,
        "/annotation_queues/q1",
    )
    assert dict(mock_server.requests[0].url.params) == {"project_id": PROJECT}
    assert mock_server.requests[0].content == b""


@pytest.mark.parametrize(
    ("method_name", "req", "expected_body"),
    [
        pytest.param(
            "image_create",
            tsi.ImageGenerationCreateReq(
                project_id=PROJECT,
                inputs={"model": "dall-e-3", "prompt": "a cat"},
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "inputs": {"model": "dall-e-3", "prompt": "a cat", "n": None},
                "track_llm_call": True,
                "wb_user_id": "user-id",
            },
            id="image_create",
        ),
        pytest.param(
            "call_stats",
            tsi.CallStatsReq(
                project_id=PROJECT, start=START, end=END, granularity=3600
            ),
            {
                "project_id": PROJECT,
                "start": "2026-08-20T00:00:00+00:00",
                "end": "2026-08-21T00:00:00+00:00",
                "granularity": 3600,
                "usage_metrics": None,
                "call_metrics": None,
                "filter": None,
                "timezone": "UTC",
            },
            id="call_stats",
        ),
        pytest.param(
            "annotation_queue_create",
            tsi.AnnotationQueueCreateReq(
                project_id=PROJECT,
                name="my-queue",
                description="notes",
                scorer_refs=["weave:///entity/project/object/s:abc123"],
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "name": "my-queue",
                "description": "notes",
                "scorer_refs": ["weave:///entity/project/object/s:abc123"],
                "wb_user_id": "user-id",
            },
            id="annotation_queue_create",
        ),
        pytest.param(
            "custom_runtime_apply",
            tsi.CustomRuntimeApplyReq(
                project_id=PROJECT,
                runtime_name="my-runtime",
                base_url="http://example.com",
                runtime_ids=[tsi.CustomRuntimeID(id="my-model")],
                wb_user_id="user-id",
            ),
            {
                "base_url": "http://example.com",
                "runtime_ids": [{"id": "my-model", "max_tokens": 4096}],
                "api_key_secret": None,
                "headers": {},
            },
            id="custom_runtime_apply",
        ),
        pytest.param(
            "eval_results_query",
            tsi.EvalResultsQueryReq(
                project_id=PROJECT,
                evaluation_call_ids=["c1"],
                filters=[
                    tsi.EvalResultsFilter(
                        evaluation_call_id="c1",
                        query=tsi.Query(
                            expr_=query.EqOperation(
                                eq_=(
                                    query.GetFieldOperator(get_field_="output.x"),
                                    query.LiteralOperation(literal_=1),
                                )
                            )
                        ),
                    )
                ],
                sort_by=[tsi.EvalResultsSortBy(field="output.x", direction="desc")],
            ),
            {
                "evaluation_call_ids": ["c1"],
                "evaluation_run_ids": None,
                "filter_logic_operator": "or",
                "filters": [
                    {
                        "evaluation_call_id": "c1",
                        "query": {
                            "$expr": {
                                "$eq": [
                                    {"$getField": "output.x"},
                                    {"$literal": 1},
                                ]
                            }
                        },
                    }
                ],
                "include_costs": False,
                "include_predict_and_score_children": True,
                "include_raw_data_rows": False,
                "include_rows": True,
                "include_summary": False,
                "limit": None,
                "offset": 0,
                "require_intersection": False,
                "resolve_row_refs": False,
                "sort_by": [
                    {
                        "field": "output.x",
                        "direction": "desc",
                        "evaluation_call_id": None,
                        "mode": "value",
                    }
                ],
                "summary_require_intersection": None,
            },
            id="eval_results_query",
        ),
    ],
)
def test_route_sends_every_supported_field(
    method_name: str, req: BaseModel, expected_body: dict
):
    """Test that the fields the route accepts reach the wire under their aliases."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert json.loads(mock_server.requests[0].content) == expected_body


@pytest.mark.parametrize(
    ("method_name", "req", "expected_path"),
    [
        pytest.param(
            "op_delete",
            tsi.OpDeleteReq(
                project_id=PROJECT, object_id="my-object", digests=["abc123"]
            ),
            f"{V2}/ops/my-object",
            id="op_delete",
        ),
        pytest.param(
            "dataset_delete",
            tsi.DatasetDeleteReq(
                project_id=PROJECT, object_id="my-object", digests=["abc123"]
            ),
            f"{V2}/datasets/my-object",
            id="dataset_delete",
        ),
        pytest.param(
            "scorer_delete",
            tsi.ScorerDeleteReq(
                project_id=PROJECT, object_id="my-object", digests=["abc123"]
            ),
            f"{V2}/scorers/my-object",
            id="scorer_delete",
        ),
        pytest.param(
            "evaluation_delete",
            tsi.EvaluationDeleteReq(
                project_id=PROJECT, object_id="my-object", digests=["abc123"]
            ),
            f"{V2}/evaluations/my-object",
            id="evaluation_delete",
        ),
        pytest.param(
            "model_delete",
            tsi.ModelDeleteReq(
                project_id=PROJECT, object_id="my-object", digests=["abc123"]
            ),
            f"{V2}/models/my-object",
            id="model_delete",
        ),
    ],
)
def test_delete_sends_the_requested_digests(
    method_name: str, req: BaseModel, expected_path: str
):
    """Test that deleting one version does not ask to delete every version."""
    mock_server = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        "DELETE",
        expected_path,
    )
    assert dict(mock_server.requests[0].url.params) == {"digests": "abc123"}


@pytest.mark.parametrize(
    ("method_name", "req", "expected_body"),
    [
        pytest.param(
            "evaluation_create",
            tsi.EvaluationCreateReq(
                project_id=PROJECT,
                name="my-object",
                dataset="ds-ref",
                evaluation_name="my evaluation",
                eval_attributes={"k": "v"},
            ),
            {
                "dataset": "ds-ref",
                "description": None,
                "eval_attributes": {"k": "v"},
                "evaluation_name": "my evaluation",
                "name": "my-object",
                "scorers": None,
                "trials": 1,
            },
            id="evaluation_create",
        ),
        pytest.param(
            "evaluation_run_create",
            tsi.EvaluationRunCreateReq(
                project_id=PROJECT,
                evaluation="ev-ref",
                model="m-ref",
                source_evaluation_run_id="source-run-id",
            ),
            {
                "evaluation": "ev-ref",
                "model": "m-ref",
                "source_evaluation_run_id": "source-run-id",
            },
            id="evaluation_run_create",
        ),
        pytest.param(
            "prediction_create",
            tsi.PredictionCreateReq(
                project_id=PROJECT,
                model="m-ref",
                inputs={"a": 1},
                output="out",
                genai_span_ref=[
                    tsi.GenAISpanRef(trace_id="trace-id", span_id="span-id")
                ],
            ),
            {
                "evaluation_run_id": None,
                "genai_span_ref": [{"trace_id": "trace-id", "span_id": "span-id"}],
                "inputs": {"a": 1},
                "model": "m-ref",
                "output": "out",
            },
            id="prediction_create",
        ),
    ],
)
def test_create_sends_every_supported_field(
    method_name: str, req: BaseModel, expected_body: dict
):
    """Test that the optional fields the route accepts reach the wire."""
    mock_server = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    getattr(mock_server.server, method_name)(req)

    assert len(mock_server.requests) == 1
    assert json.loads(mock_server.requests[0].content) == expected_body


def test_call_end_reads_an_empty_response_body():
    """Test that a route generated as returning a bare `object` is read back."""
    mock_server = _mock_server(httpx.Response(200, json={}))

    res = mock_server.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=PROJECT,
                id="call-id",
                ended_at="2026-08-20T00:00:00Z",
                summary={},
            )
        )
    )

    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.path == "/call/end"
    assert res == tsi.CallEndRes()


def test_call_start_batch_reads_the_response_list():
    """Test that the batch response is read from the field the route returns."""
    mock_server = _mock_server(
        httpx.Response(
            200, json={"res": [{"id": "call-id", "trace_id": "trace-id"}, {}]}
        )
    )
    start, end = generate_call_start_end_pair(id="call-id")

    res = mock_server.server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(req=start),
                tsi.CallBatchEndMode(req=end),
            ]
        )
    )

    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.path == "/call/upsert_batch"
    assert res.res == [
        tsi.CallStartRes(id="call-id", trace_id="trace-id"),
        tsi.CallEndRes(),
    ]


@pytest.mark.parametrize(
    ("method_name", "req", "expected_path", "rows", "expected"),
    [
        pytest.param(
            "threads_query_stream",
            tsi.ThreadsQueryReq(project_id=PROJECT),
            "/threads/stream_query",
            [
                {
                    "thread_id": "t1",
                    "turn_count": 1,
                    "start_time": "2026-08-20T00:00:00Z",
                    "last_updated": "2026-08-20T00:00:00Z",
                    "first_turn_id": None,
                    "last_turn_id": None,
                    "p50_turn_duration_ms": None,
                    "p99_turn_duration_ms": None,
                },
                {
                    "thread_id": "t2",
                    "turn_count": 2,
                    "start_time": "2026-08-20T00:00:00Z",
                    "last_updated": "2026-08-20T00:00:00Z",
                    "first_turn_id": None,
                    "last_turn_id": None,
                    "p50_turn_duration_ms": None,
                    "p99_turn_duration_ms": None,
                },
            ],
            [
                tsi.ThreadSchema(
                    thread_id="t1",
                    turn_count=1,
                    start_time="2026-08-20T00:00:00Z",
                    last_updated="2026-08-20T00:00:00Z",
                    first_turn_id=None,
                    last_turn_id=None,
                    p50_turn_duration_ms=None,
                    p99_turn_duration_ms=None,
                ),
                tsi.ThreadSchema(
                    thread_id="t2",
                    turn_count=2,
                    start_time="2026-08-20T00:00:00Z",
                    last_updated="2026-08-20T00:00:00Z",
                    first_turn_id=None,
                    last_turn_id=None,
                    p50_turn_duration_ms=None,
                    p99_turn_duration_ms=None,
                ),
            ],
            id="threads_query_stream",
        ),
        pytest.param(
            "op_list",
            tsi.OpListReq(project_id=PROJECT),
            f"{V2}/ops",
            [
                {
                    "object_id": "op-1",
                    "digest": "d1",
                    "version_index": 0,
                    "created_at": "2026-08-20T00:00:00Z",
                    "code": "def f(): pass",
                },
                {
                    "object_id": "op-2",
                    "digest": "d2",
                    "version_index": 1,
                    "created_at": "2026-08-20T00:00:00Z",
                    "code": "def g(): pass",
                },
            ],
            [
                tsi.OpReadRes(
                    object_id="op-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    code="def f(): pass",
                ),
                tsi.OpReadRes(
                    object_id="op-2",
                    digest="d2",
                    version_index=1,
                    created_at="2026-08-20T00:00:00Z",
                    code="def g(): pass",
                ),
            ],
            id="op_list",
        ),
        pytest.param(
            "dataset_list",
            tsi.DatasetListReq(project_id=PROJECT),
            f"{V2}/datasets",
            [
                {
                    "object_id": "ds-1",
                    "digest": "d1",
                    "version_index": 0,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "ds-1",
                    "rows": "weave:///entity/project/table/abc123",
                },
                {
                    "object_id": "ds-2",
                    "digest": "d2",
                    "version_index": 1,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "ds-2",
                    "rows": "weave:///entity/project/table/def456",
                },
            ],
            [
                tsi.DatasetReadRes(
                    object_id="ds-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="ds-1",
                    rows="weave:///entity/project/table/abc123",
                ),
                tsi.DatasetReadRes(
                    object_id="ds-2",
                    digest="d2",
                    version_index=1,
                    created_at="2026-08-20T00:00:00Z",
                    name="ds-2",
                    rows="weave:///entity/project/table/def456",
                ),
            ],
            id="dataset_list",
        ),
        pytest.param(
            "scorer_list",
            tsi.ScorerListReq(project_id=PROJECT),
            f"{V2}/scorers",
            [
                {
                    "object_id": "s-1",
                    "digest": "d1",
                    "version_index": 0,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "s-1",
                    "score_op": "weave:///entity/project/op/s:abc123",
                },
                {
                    "object_id": "s-2",
                    "digest": "d2",
                    "version_index": 1,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "s-2",
                    "score_op": "weave:///entity/project/op/s:def456",
                },
            ],
            [
                tsi.ScorerReadRes(
                    object_id="s-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="s-1",
                    score_op="weave:///entity/project/op/s:abc123",
                ),
                tsi.ScorerReadRes(
                    object_id="s-2",
                    digest="d2",
                    version_index=1,
                    created_at="2026-08-20T00:00:00Z",
                    name="s-2",
                    score_op="weave:///entity/project/op/s:def456",
                ),
            ],
            id="scorer_list",
        ),
        pytest.param(
            "evaluation_list",
            tsi.EvaluationListReq(project_id=PROJECT),
            f"{V2}/evaluations",
            [
                {
                    "object_id": "ev-1",
                    "digest": "d1",
                    "version_index": 0,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "ev-1",
                    "dataset": "weave:///entity/project/object/ds:abc123",
                    "scorers": [],
                    "trials": 1,
                },
                {
                    "object_id": "ev-2",
                    "digest": "d2",
                    "version_index": 1,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "ev-2",
                    "dataset": "weave:///entity/project/object/ds:def456",
                    "scorers": [],
                    "trials": 1,
                },
            ],
            [
                tsi.EvaluationReadRes(
                    object_id="ev-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="ev-1",
                    dataset="weave:///entity/project/object/ds:abc123",
                    scorers=[],
                    trials=1,
                ),
                tsi.EvaluationReadRes(
                    object_id="ev-2",
                    digest="d2",
                    version_index=1,
                    created_at="2026-08-20T00:00:00Z",
                    name="ev-2",
                    dataset="weave:///entity/project/object/ds:def456",
                    scorers=[],
                    trials=1,
                ),
            ],
            id="evaluation_list",
        ),
        pytest.param(
            "model_list",
            tsi.ModelListReq(project_id=PROJECT),
            f"{V2}/models",
            [
                {
                    "object_id": "m-1",
                    "digest": "d1",
                    "version_index": 0,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "m-1",
                    "source_code": "def f(): pass",
                },
                {
                    "object_id": "m-2",
                    "digest": "d2",
                    "version_index": 1,
                    "created_at": "2026-08-20T00:00:00Z",
                    "name": "m-2",
                    "source_code": "def g(): pass",
                },
            ],
            [
                tsi.ModelReadRes(
                    object_id="m-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="m-1",
                    source_code="def f(): pass",
                ),
                tsi.ModelReadRes(
                    object_id="m-2",
                    digest="d2",
                    version_index=1,
                    created_at="2026-08-20T00:00:00Z",
                    name="m-2",
                    source_code="def g(): pass",
                ),
            ],
            id="model_list",
        ),
        pytest.param(
            "evaluation_run_list",
            tsi.EvaluationRunListReq(project_id=PROJECT),
            f"{V2}/evaluation_runs",
            [
                {"evaluation_run_id": "r1", "evaluation": "ev-ref", "model": "m-ref"},
                {"evaluation_run_id": "r2", "evaluation": "ev-ref", "model": "m-ref"},
            ],
            [
                tsi.EvaluationRunReadRes(
                    evaluation_run_id="r1", evaluation="ev-ref", model="m-ref"
                ),
                tsi.EvaluationRunReadRes(
                    evaluation_run_id="r2", evaluation="ev-ref", model="m-ref"
                ),
            ],
            id="evaluation_run_list",
        ),
        pytest.param(
            "prediction_list",
            tsi.PredictionListReq(project_id=PROJECT),
            f"{V2}/predictions",
            [
                {"prediction_id": "p1", "model": "m-ref", "inputs": {}, "output": None},
                {"prediction_id": "p2", "model": "m-ref", "inputs": {}, "output": None},
            ],
            [
                tsi.PredictionReadRes(
                    prediction_id="p1", model="m-ref", inputs={}, output=None
                ),
                tsi.PredictionReadRes(
                    prediction_id="p2", model="m-ref", inputs={}, output=None
                ),
            ],
            id="prediction_list",
        ),
        pytest.param(
            "score_list",
            tsi.ScoreListReq(project_id=PROJECT),
            f"{V2}/scores",
            [
                {"score_id": "s1", "scorer": "s-ref", "value": 1},
                {"score_id": "s2", "scorer": "s-ref", "value": 2},
            ],
            [
                tsi.ScoreReadRes(score_id="s1", scorer="s-ref", value=1),
                tsi.ScoreReadRes(score_id="s2", scorer="s-ref", value=2),
            ],
            id="score_list",
        ),
        pytest.param(
            "annotation_queues_query_stream",
            tsi.AnnotationQueuesQueryReq(project_id=PROJECT),
            "/annotation_queues/query",
            [QUEUE, {**QUEUE, "id": "q2"}],
            [
                tsi.AnnotationQueueSchema.model_validate(QUEUE),
                tsi.AnnotationQueueSchema.model_validate({**QUEUE, "id": "q2"}),
            ],
            id="annotation_queues_query_stream",
        ),
    ],
)
def test_typed_stream_reads_one_item_per_line(
    method_name: str,
    req: BaseModel,
    expected_path: str,
    rows: list[dict],
    expected: list[BaseModel],
):
    """Test that a route whose stream the spec types yields one item per line."""
    mock_server = _mock_server(
        httpx.Response(
            200,
            content="\n".join(json.dumps(row) for row in rows).encode(),
            headers={"content-type": "application/jsonl"},
        )
    )

    res = list(getattr(mock_server.server, method_name)(req))

    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.path == expected_path
    assert res == expected


def test_file_content_read_keeps_bytes():
    """Test that a non-text file comes back as the bytes the server sent."""
    content = b"\x89PNG\r\n\x1a\n\xff\xfe"
    mock_server = _mock_server(
        httpx.Response(
            200, content=content, headers={"content-type": "application/octet-stream"}
        )
    )

    res = mock_server.server.file_content_read(
        tsi.FileContentReadReq(project_id=PROJECT, digest="abc123")
    )

    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.path == "/file/content"
    assert res.content == content


def test_custom_runtime_name_keeps_its_colon():
    """Test that a runtime name reaches the path without percent-encoding."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    mock_server.server.custom_runtime_apply(
        tsi.CustomRuntimeApplyReq(
            project_id=PROJECT,
            runtime_name="foo:bar",
            base_url="http://example.com",
            runtime_ids=[],
        )
    )

    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.raw_path.endswith(b"/runtimes/foo:bar")


@pytest.mark.parametrize(
    ("method_name", "req"),
    [
        pytest.param(
            "completions_create",
            tsi.CompletionsCreateReq(project_id=PROJECT, inputs={"model": "gpt-4o"}),
            id="completions_create",
        ),
        pytest.param(
            "project_stats",
            tsi.ProjectStatsReq(project_id=PROJECT),
            id="project_stats",
        ),
        pytest.param(
            "completions_create_stream",
            tsi.CompletionsCreateReq(project_id=PROJECT, inputs={"model": "gpt-4o"}),
            id="completions_create_stream",
        ),
    ],
)
def test_route_missing_from_the_spec_raises(method_name: str, req: BaseModel):
    """Test that a method with no usable generated route says so."""
    mock_server = _mock_server(httpx.Response(200, json={}))

    with pytest.raises(NotImplementedError):
        getattr(mock_server.server, method_name)(req)

    assert mock_server.requests == []


def test_file_create_sends_the_filename():
    """Test that the upload keeps the filename on the multipart part."""
    mock_server = _mock_server(httpx.Response(200, json={"digest": "abc123"}))

    res = mock_server.server.file_create(
        tsi.FileCreateReq(
            project_id=PROJECT,
            name="pic.png",
            content=b"\x89PNG",
            expected_digest="deadbeef",
        )
    )

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        "POST",
        "/file/create",
    )
    assert "multipart/form-data" in mock_server.requests[0].headers["content-type"]
    body = mock_server.requests[0].content
    assert b'filename="pic.png"' in body
    assert b"\x89PNG" in body
    assert b"deadbeef" in body
    assert res == tsi.FileCreateRes(digest="abc123")


@pytest.mark.parametrize(
    ("method_name", "req", "expected_path"),
    [
        pytest.param(
            "scorer_list",
            tsi.ScorerListReq(project_id=PROJECT, limit=10, offset=5),
            f"{V2}/scorers",
            id="scorer_list",
        ),
        pytest.param(
            "evaluation_list",
            tsi.EvaluationListReq(project_id=PROJECT, limit=10, offset=5),
            f"{V2}/evaluations",
            id="evaluation_list",
        ),
    ],
)
def test_list_sends_limit_and_offset(
    method_name: str, req: BaseModel, expected_path: str
):
    """Test that both pagination params reach the query string."""
    mock_server = _mock_server(
        httpx.Response(
            200,
            content=b"",
            headers={"content-type": "application/jsonl"},
        )
    )

    assert list(getattr(mock_server.server, method_name)(req)) == []

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        "GET",
        expected_path,
    )
    assert dict(mock_server.requests[0].url.params) == {"limit": "10", "offset": "5"}
