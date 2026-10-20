"""Tests for the requests StainlessRemoteHTTPTraceServer sends.

These tests drive the binding through the vendored generated client over an
httpx.MockTransport, so what they assert is the request the generated resource
builds. The file is not gated to the stainless shard, so it also runs against
the default one.
"""

from __future__ import annotations

import collections.abc
import datetime
import inspect
import json
import operator
import types
import typing
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import typing_extensions
from pydantic import BaseModel

from tests.trace_server_bindings.conftest import generate_call_start_end_pair
from weave.durability.wal_sender import build_trace_server_handlers
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents import types as agent_types
from weave.trace_server_bindings.client_interface import (
    ObjAddTagsParams,
    ObjRemoveAliasesParams,
    ObjRemoveTagsParams,
    ObjSetAliasesParams,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient
from weave.vendor.weave_server_sdk.types import (
    AgentQueryParams,
    AgentQueryResponse,
    AgentSearchParams,
    AgentSearchResponse,
    AgentTraceChatRes,
    AnnotationQueueCreateParams,
    AnnotationQueueCreateResponse,
    AnnotationQueueDeleteParams,
    AnnotationQueueQueryParams,
    AnnotationQueueReadParams,
    AnnotationQueueReadResponse,
    AnnotationQueueSchema,
    AnnotationQueueStatsParams,
    AnnotationQueueStatsResponse,
    AnnotationQueueUpdateParams,
    CallDeleteParams,
    CallEndParams,
    CallQueryStatsParams,
    CallReadParams,
    CallScoreParams,
    CallStartParams,
    CallStatsParams,
    CallStatsResponse,
    CallStreamQueryParams,
    CallUpdateParams,
    CallUpsertBatchParams,
    CallUpsertBatchResponse,
    CallUsageParams,
    CompletionCreateParams,
    CompletionCreateResponse,
    CompletionCreateStreamParams,
    CostCreateParams,
    CostPurgeParams,
    CostQueryParams,
    DatasetSourceLinkParams,
    DatasetSourceLinkResponse,
    DatasetSourceQueryParams,
    DatasetSourceQueryResponse,
    DatasetSourceSourceDatasetsQueryParams,
    DatasetSourceSourceDatasetsQueryResponse,
    EvaluationEvaluateModelParams,
    EvaluationEvaluateModelResponse,
    EvaluationRescoreParams,
    EvaluationRescoreResponse,
    EvaluationStatusParams,
    EvaluationStatusResponse,
    FeedbackAggregateParams,
    FeedbackAggregateResponse,
    FeedbackBatchCreateParams,
    FeedbackCreateParams,
    FeedbackPayloadSchemaParams,
    FeedbackPayloadSchemaResponse,
    FeedbackPurgeParams,
    FeedbackQueryParams,
    FeedbackReplaceParams,
    FeedbackStatsParams,
    FeedbackStatsResponse,
    FileContentParams,
    FileCreateResponse,
    FileStatsParams,
    ImageCreateParams,
    ImageCreateResponse,
    ObjectCreateParams,
    ObjectDeleteParams,
    ObjectQueryParams,
    ObjectReadParams,
    ProjectStatsParams,
    ProjectStatsResponse,
    RefReadBatchParams,
    ServiceProjectsInfoParams,
    TableCreateFromDigestsParams,
    TableCreateParams,
    TableQueryParams,
    TableQueryStatsBatchParams,
    TableQueryStatsParams,
    TableUpdateParams,
    ThreadStreamQueryParams,
    ThreadStreamQueryResponse,
    TraceUsageParams,
    V2DatasetCreateParams,
    V2DatasetCreateResponse,
    V2DatasetDeleteParams,
    V2DatasetListParams,
    V2DatasetListResponse,
    V2DatasetReadResponse,
    V2EvalResultQueryParams,
    V2EvalResultQueryResponse,
    V2EvaluationCreateParams,
    V2EvaluationCreateResponse,
    V2EvaluationDeleteParams,
    V2EvaluationListParams,
    V2EvaluationListResponse,
    V2EvaluationReadResponse,
    V2EvaluationRunCreateParams,
    V2EvaluationRunCreateResponse,
    V2EvaluationRunDeleteParams,
    V2EvaluationRunDeleteResponse,
    V2EvaluationRunFinishParams,
    V2EvaluationRunFinishResponse,
    V2EvaluationRunListParams,
    V2EvaluationRunListResponse,
    V2EvaluationRunReadResponse,
    V2ModelCreateParams,
    V2ModelCreateResponse,
    V2ModelDeleteParams,
    V2ModelListParams,
    V2ModelListResponse,
    V2ModelReadResponse,
    V2OpCreateParams,
    V2OpCreateResponse,
    V2OpDeleteParams,
    V2OpListParams,
    V2OpListResponse,
    V2OpReadResponse,
    V2PredictionCreateParams,
    V2PredictionCreateResponse,
    V2PredictionDeleteParams,
    V2PredictionDeleteResponse,
    V2PredictionFinishResponse,
    V2PredictionListParams,
    V2PredictionListResponse,
    V2PredictionReadResponse,
    V2RuntimeApplyParams,
    V2RuntimeApplyResponse,
    V2ScoreCreateParams,
    V2ScoreCreateResponse,
    V2ScoreDeleteParams,
    V2ScoreDeleteResponse,
    V2ScoreListParams,
    V2ScoreListResponse,
    V2ScorerCreateParams,
    V2ScorerCreateResponse,
    V2ScorerDeleteParams,
    V2ScoreReadResponse,
    V2ScorerListParams,
    V2ScorerListResponse,
    V2ScorerReadResponse,
)
from weave.vendor.weave_server_sdk.types.agents import (
    AgentVersionQueryParams,
    AgentVersionQueryResponse,
    ConversationChatParams,
    ConversationChatResponse,
    ConversationSpansParams,
    ConversationSpansResponse,
    SpanCustomAttrsSchemaParams,
    SpanCustomAttrsSchemaResponse,
    SpanQueryParams,
    SpanQueryResponse,
    SpanStatsParams,
    SpanStatsResponse,
    TraceChatParams,
)
from weave.vendor.weave_server_sdk.types.annotation_queues import (
    ItemAddParams,
    ItemQueryParams,
    ItemQueryResponse,
    ItemUpdateProgressParams,
)
from weave.vendor.weave_server_sdk.types.call_upsert_batch_response import (
    ReCallStartRes,
)
from weave.vendor.weave_server_sdk.types.objects import (
    AliasListParams,
    TagListParams,
)
from weave.vendor.weave_server_sdk.types.projects import (
    TtlSettingReadParams,
    TtlSettingReadResponse,
    TtlSettingUpdateParams,
    TtlSettingUpdateResponse,
)

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
    "entries": [],
    "evaluation_run_id": "run-id",
    "files_storage_size_bytes": 0,
    "granularity": 86400,
    "groups": [],
    "has_more": False,
    "headers": {},
    "id": "q1",
    "item": ITEM,
    "items": [],
    "limit": 0,
    "links": [],
    "messages": [],
    "memberships": [],
    "name": "my-runtime",
    "objects_storage_size_bytes": 0,
    "offset": 0,
    "paths": [],
    "queue": QUEUE,
    "response": {},
    "results": [],
    "retention_days": 30,
    "rows": [],
    "runtime_ids": [],
    "spans": [],
    "spans_storage_size_bytes": 0,
    "start": "2026-08-20T00:00:00Z",
    "stats": [],
    "status": {"code": "not_found"},
    "tables_storage_size_bytes": 0,
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
    "trace_storage_size_bytes": 0,
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
            V2OpCreateResponse,
            id="op_create",
        ),
        pytest.param(
            "op_read",
            tsi.OpReadReq(project_id=PROJECT, object_id="my-object", digest="abc123"),
            "GET",
            f"{V2}/ops/my-object/versions/abc123",
            V2OpReadResponse,
            id="op_read",
        ),
        pytest.param(
            "dataset_create",
            tsi.DatasetCreateReq(project_id=PROJECT, name="my-object", rows=[]),
            "POST",
            f"{V2}/datasets",
            V2DatasetCreateResponse,
            id="dataset_create",
        ),
        pytest.param(
            "dataset_read",
            tsi.DatasetReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/datasets/my-object/versions/abc123",
            V2DatasetReadResponse,
            id="dataset_read",
        ),
        pytest.param(
            "scorer_create",
            tsi.ScorerCreateReq(
                project_id=PROJECT, name="my-object", op_source_code="def f(): pass"
            ),
            "POST",
            f"{V2}/scorers",
            V2ScorerCreateResponse,
            id="scorer_create",
        ),
        pytest.param(
            "scorer_read",
            tsi.ScorerReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/scorers/my-object/versions/abc123",
            V2ScorerReadResponse,
            id="scorer_read",
        ),
        pytest.param(
            "evaluation_create",
            tsi.EvaluationCreateReq(
                project_id=PROJECT, name="my-object", dataset="ds-ref"
            ),
            "POST",
            f"{V2}/evaluations",
            V2EvaluationCreateResponse,
            id="evaluation_create",
        ),
        pytest.param(
            "evaluation_read",
            tsi.EvaluationReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/evaluations/my-object/versions/abc123",
            V2EvaluationReadResponse,
            id="evaluation_read",
        ),
        pytest.param(
            "model_create",
            tsi.ModelCreateReq(
                project_id=PROJECT, name="my-object", source_code="def f(): pass"
            ),
            "POST",
            f"{V2}/models",
            V2ModelCreateResponse,
            id="model_create",
        ),
        pytest.param(
            "model_read",
            tsi.ModelReadReq(
                project_id=PROJECT, object_id="my-object", digest="abc123"
            ),
            "GET",
            f"{V2}/models/my-object/versions/abc123",
            V2ModelReadResponse,
            id="model_read",
        ),
        pytest.param(
            "evaluation_run_create",
            tsi.EvaluationRunCreateReq(
                project_id=PROJECT, evaluation="ev-ref", model="m-ref"
            ),
            "POST",
            f"{V2}/evaluation_runs",
            V2EvaluationRunCreateResponse,
            id="evaluation_run_create",
        ),
        pytest.param(
            "evaluation_run_read",
            tsi.EvaluationRunReadReq(project_id=PROJECT, evaluation_run_id="run-id"),
            "GET",
            f"{V2}/evaluation_runs/run-id",
            V2EvaluationRunReadResponse,
            id="evaluation_run_read",
        ),
        pytest.param(
            "evaluation_run_delete",
            tsi.EvaluationRunDeleteReq(
                project_id=PROJECT, evaluation_run_ids=["run-id"]
            ),
            "DELETE",
            f"{V2}/evaluation_runs",
            V2EvaluationRunDeleteResponse,
            id="evaluation_run_delete",
        ),
        pytest.param(
            "evaluation_run_finish",
            tsi.EvaluationRunFinishReq(project_id=PROJECT, evaluation_run_id="run-id"),
            "POST",
            f"{V2}/evaluation_runs/run-id/finish",
            V2EvaluationRunFinishResponse,
            id="evaluation_run_finish",
        ),
        pytest.param(
            "prediction_create",
            tsi.PredictionCreateReq(
                project_id=PROJECT, model="m-ref", inputs={}, output=None
            ),
            "POST",
            f"{V2}/predictions",
            V2PredictionCreateResponse,
            id="prediction_create",
        ),
        pytest.param(
            "prediction_read",
            tsi.PredictionReadReq(project_id=PROJECT, prediction_id="prediction-id"),
            "GET",
            f"{V2}/predictions/prediction-id",
            V2PredictionReadResponse,
            id="prediction_read",
        ),
        pytest.param(
            "prediction_delete",
            tsi.PredictionDeleteReq(
                project_id=PROJECT, prediction_ids=["prediction-id"]
            ),
            "DELETE",
            f"{V2}/predictions",
            V2PredictionDeleteResponse,
            id="prediction_delete",
        ),
        pytest.param(
            "prediction_finish",
            tsi.PredictionFinishReq(project_id=PROJECT, prediction_id="prediction-id"),
            "POST",
            f"{V2}/predictions/prediction-id/finish",
            V2PredictionFinishResponse,
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
            V2ScoreCreateResponse,
            id="score_create",
        ),
        pytest.param(
            "score_read",
            tsi.ScoreReadReq(project_id=PROJECT, score_id="score-id"),
            "GET",
            f"{V2}/scores/score-id",
            V2ScoreReadResponse,
            id="score_read",
        ),
        pytest.param(
            "score_delete",
            tsi.ScoreDeleteReq(project_id=PROJECT, score_ids=["score-id"]),
            "DELETE",
            f"{V2}/scores",
            V2ScoreDeleteResponse,
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
            SpanQueryResponse,
            id="agent_spans_query",
        ),
        pytest.param(
            "agent_traces_chat",
            agent_types.AgentTraceChatReq(project_id=PROJECT, trace_id="t1"),
            "POST",
            "/agents/traces/chat",
            AgentTraceChatRes,
            id="agent_traces_chat",
        ),
        pytest.param(
            "agent_conversation_chat",
            agent_types.AgentConversationChatReq(
                project_id=PROJECT, conversation_id="conv1"
            ),
            "POST",
            "/agents/conversations/chat",
            ConversationChatResponse,
            id="agent_conversation_chat",
        ),
        pytest.param(
            "agent_conversation_spans",
            agent_types.AgentConversationSpansReq(project_id=PROJECT),
            "POST",
            "/agents/conversations/spans",
            ConversationSpansResponse,
            id="agent_conversation_spans",
        ),
        pytest.param(
            "agent_agents_query",
            agent_types.AgentsQueryReq(project_id=PROJECT),
            "POST",
            "/agents/query",
            AgentQueryResponse,
            id="agent_agents_query",
        ),
        pytest.param(
            "agent_versions_query",
            agent_types.AgentVersionsQueryReq(
                project_id=PROJECT, agent_name="my-agent"
            ),
            "POST",
            "/agents/agent-versions/query",
            AgentVersionQueryResponse,
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
                insight_filters=[
                    agent_types.AgentInsightFilter(
                        field="failure_severity",
                        values=["major"],
                    ),
                    agent_types.AgentInsightFilter(
                        field="intent_topic_id",
                        values=["01994634-c680-7dc3-a40b-0383b5008d70"],
                    ),
                ],
            ),
            "POST",
            "/agents/spans/stats",
            SpanStatsResponse,
            id="agent_spans_stats",
        ),
        pytest.param(
            "agent_custom_attrs_schema",
            agent_types.AgentCustomAttrsSchemaReq(project_id=PROJECT),
            "POST",
            "/agents/spans/custom-attrs/schema",
            SpanCustomAttrsSchemaResponse,
            id="agent_custom_attrs_schema",
        ),
        pytest.param(
            "agent_search",
            agent_types.AgentSearchReq(project_id=PROJECT),
            "POST",
            "/agents/search",
            AgentSearchResponse,
            id="agent_search",
        ),
        pytest.param(
            "call_stats",
            tsi.CallStatsReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/calls/stats",
            CallStatsResponse,
            id="call_stats",
        ),
        pytest.param(
            "feedback_stats",
            tsi.FeedbackStatsReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/feedback/stats",
            FeedbackStatsResponse,
            id="feedback_stats",
        ),
        pytest.param(
            "feedback_aggregate",
            tsi.FeedbackAggregateReq(project_id=PROJECT, after_ms=0, before_ms=1),
            "POST",
            "/feedback/aggregate",
            FeedbackAggregateResponse,
            id="feedback_aggregate",
        ),
        pytest.param(
            "feedback_payload_schema",
            tsi.FeedbackPayloadSchemaReq(project_id=PROJECT, start=START, end=END),
            "POST",
            "/feedback/payload_schema",
            FeedbackPayloadSchemaResponse,
            id="feedback_payload_schema",
        ),
        pytest.param(
            "completions_create",
            tsi.CompletionsCreateReq(project_id=PROJECT, inputs={"model": "gpt-4o"}),
            "POST",
            "/completions/create",
            CompletionCreateResponse,
            id="completions_create",
        ),
        pytest.param(
            "image_create",
            tsi.ImageGenerationCreateReq(
                project_id=PROJECT, inputs={"model": "dall-e-3", "prompt": "a cat"}
            ),
            "POST",
            "/image/create",
            ImageCreateResponse,
            id="image_create",
        ),
        pytest.param(
            "project_stats",
            tsi.ProjectStatsReq(project_id=PROJECT),
            "POST",
            "/project/stats",
            ProjectStatsResponse,
            id="project_stats",
        ),
        pytest.param(
            "project_ttl_settings_read",
            tsi.ProjectTTLSettingsReadReq(project_id=PROJECT),
            "POST",
            "/project/ttl_settings/read",
            TtlSettingReadResponse,
            id="project_ttl_settings_read",
        ),
        pytest.param(
            "project_ttl_settings_update",
            tsi.ProjectTTLSettingsUpdateReq(project_id=PROJECT, retention_days=30),
            "POST",
            "/project/ttl_settings/update",
            TtlSettingUpdateResponse,
            id="project_ttl_settings_update",
        ),
        pytest.param(
            "dataset_sources_link",
            tsi.DatasetSourcesLinkReq(
                project_id=PROJECT,
                dataset_object_id="ds",
                dataset_digest="abc123",
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest="row1",
                        sources=[
                            tsi.SourceRef(
                                source_kind=tsi.SourceKind.CALL,
                                source_id="c1",
                                source_trace_id="t1",
                            )
                        ],
                    )
                ],
            ),
            "POST",
            "/dataset_sources/link",
            DatasetSourceLinkResponse,
            id="dataset_sources_link",
        ),
        pytest.param(
            "dataset_sources_query",
            tsi.DatasetSourcesQueryReq(project_id=PROJECT, dataset_object_id="ds"),
            "POST",
            "/dataset_sources/query",
            DatasetSourceQueryResponse,
            id="dataset_sources_query",
        ),
        pytest.param(
            "source_datasets_query",
            tsi.SourceDatasetsQueryReq(
                project_id=PROJECT,
                sources=[
                    tsi.SourceRef(
                        source_kind=tsi.SourceKind.CALL,
                        source_id="c1",
                        source_trace_id="t1",
                    )
                ],
            ),
            "POST",
            "/dataset_sources/source_datasets_query",
            DatasetSourceSourceDatasetsQueryResponse,
            id="source_datasets_query",
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
            EvaluationEvaluateModelResponse,
            id="evaluate_model",
        ),
        pytest.param(
            "evaluation_status",
            tsi.EvaluationStatusReq(project_id=PROJECT, call_id="c1"),
            "POST",
            "/evaluations/status",
            EvaluationStatusResponse,
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
            EvaluationRescoreResponse,
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
            dict,
            id="calls_score",
        ),
        pytest.param(
            "annotation_queue_create",
            tsi.AnnotationQueueCreateReq(
                project_id=PROJECT, name="my-queue", scorer_refs=[]
            ),
            "POST",
            "/annotation_queues",
            AnnotationQueueCreateResponse,
            id="annotation_queue_create",
        ),
        pytest.param(
            "annotation_queue_read",
            tsi.AnnotationQueueReadReq(project_id=PROJECT, queue_id="q1"),
            "GET",
            "/annotation_queues/q1",
            AnnotationQueueReadResponse,
            id="annotation_queue_read",
        ),
        pytest.param(
            "annotation_queue_items_query",
            tsi.AnnotationQueueItemsQueryReq(project_id=PROJECT, queue_id="q1"),
            "POST",
            "/annotation_queues/q1/items/query",
            ItemQueryResponse,
            id="annotation_queue_items_query",
        ),
        pytest.param(
            "annotation_queues_stats",
            tsi.AnnotationQueuesStatsReq(project_id=PROJECT, queue_ids=["q1"]),
            "POST",
            "/annotation_queues/stats",
            AnnotationQueueStatsResponse,
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
            V2RuntimeApplyResponse,
            id="custom_runtime_apply",
        ),
        pytest.param(
            "eval_results_query",
            tsi.EvalResultsQueryReq(project_id=PROJECT, evaluation_call_ids=["c1"]),
            "POST",
            f"{V2}/eval_results/query",
            V2EvalResultQueryResponse,
            id="eval_results_query",
        ),
    ],
)
def test_route_reaches_its_path(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    res_type: type,
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
@pytest.mark.parametrize("as_dict", [False, True], ids=["model", "dict"])
def test_tag_and_alias_method_omits_wb_user_id(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    expected_body: dict,
    as_dict: bool,
):
    """Test that the server-populated wb_user_id stays out of the request."""
    mock_server = _mock_server(httpx.Response(200, json={}))

    getattr(mock_server.server, method_name)(req.model_dump() if as_dict else req)

    assert len(mock_server.requests) == 1
    assert (mock_server.requests[0].method, mock_server.requests[0].url.path) == (
        expected_method,
        expected_path,
    )
    assert json.loads(mock_server.requests[0].content) == expected_body


def test_objs_query_drops_a_query_key():
    """A dict with a `query` key, which the route lacks, sends the model's body."""
    mock_server = _mock_server(httpx.Response(200, json={"objs": []}))
    req = tsi.ObjQueryReq(project_id=PROJECT)

    mock_server.server.objs_query(req)
    mock_server.server.objs_query({**req.model_dump(), "query": {"$expr": {}}})

    first, second = (json.loads(r.content) for r in mock_server.requests)
    assert first == second


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
@pytest.mark.parametrize("as_dict", [False, True], ids=["model", "dict"])
def test_annotation_queue_method_omits_wb_user_id(
    method_name: str,
    req: BaseModel,
    expected_method: str,
    expected_path: str,
    expected_body: dict,
    as_dict: bool,
):
    """Test that the server-populated wb_user_id stays out of the request."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    getattr(mock_server.server, method_name)(req.model_dump() if as_dict else req)

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


@pytest.mark.parametrize(
    ("method_name", "req", "expected_body"),
    [
        pytest.param(
            "completions_create",
            tsi.CompletionsCreateReq(
                project_id=PROJECT,
                inputs={"model": "gpt-4o", "messages": [{"role": "user"}]},
                inference_route=tsi.DedicatedInferenceRoute(
                    connection_type="dedicated",
                    connection="dedicated_cwc38d",
                    base_url="https://cw.cwc38d.gw.cwinference.com/v1",
                ),
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "inputs": {
                    "model": "gpt-4o",
                    "messages": [{"role": "user"}],
                    "timeout": None,
                    "temperature": None,
                    "top_p": None,
                    "n": None,
                    "stop": None,
                    "max_completion_tokens": None,
                    "max_tokens": None,
                    "modalities": None,
                    "presence_penalty": None,
                    "frequency_penalty": None,
                    "stream": None,
                    "logit_bias": None,
                    "user": None,
                    "response_format": None,
                    "seed": None,
                    "tools": None,
                    "tool_choice": None,
                    "logprobs": None,
                    "top_logprobs": None,
                    "parallel_tool_calls": None,
                    "reasoning_effort": None,
                    "extra_headers": None,
                    "functions": None,
                    "function_call": None,
                    "api_version": None,
                    "prompt": None,
                    "template_vars": None,
                    "vertex_credentials": None,
                },
                "inference_route": {
                    "connection_type": "dedicated",
                    "connection": "dedicated_cwc38d",
                    "base_url": "https://cw.cwc38d.gw.cwinference.com/v1",
                },
                "wb_user_id": "user-id",
                "track_llm_call": True,
                "trace_id": None,
                "parent_id": None,
                "conversation_id": None,
                "conversation_name": None,
                "source": None,
            },
            id="completions_create",
        ),
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
            "project_stats",
            tsi.ProjectStatsReq(
                project_id=PROJECT,
                include_file_storage_size=False,
            ),
            {
                "project_id": PROJECT,
                "include_trace_storage_size": True,
                "include_object_storage_size": True,
                "include_table_storage_size": True,
                "include_file_storage_size": False,
            },
            id="project_stats",
        ),
        pytest.param(
            "project_ttl_settings_update",
            tsi.ProjectTTLSettingsUpdateReq(
                project_id=PROJECT, retention_days=30, wb_user_id="user-id"
            ),
            {
                "project_id": PROJECT,
                "retention_days": 30,
                "wb_user_id": "user-id",
            },
            id="project_ttl_settings_update",
        ),
        pytest.param(
            "dataset_sources_link",
            tsi.DatasetSourcesLinkReq(
                project_id=PROJECT,
                dataset_object_id="ds",
                dataset_digest="abc123",
                links=[
                    tsi.DatasetSourceLinkPayload(
                        row_digest="row1",
                        sources=[
                            tsi.SourceRef(
                                source_kind=tsi.SourceKind.CALL,
                                source_id="c1",
                                source_trace_id="t1",
                            )
                        ],
                        link_metadata={"note": "from-call"},
                    )
                ],
                include_created_status=True,
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "dataset_object_id": "ds",
                "dataset_digest": "abc123",
                "links": [
                    {
                        "row_digest": "row1",
                        "sources": [
                            {
                                "source_kind": "call",
                                "source_id": "c1",
                                "source_trace_id": "t1",
                            }
                        ],
                        "link_metadata": {"note": "from-call"},
                    }
                ],
                "include_created_status": True,
                "wb_user_id": "user-id",
            },
            id="dataset_sources_link",
        ),
        pytest.param(
            "dataset_sources_query",
            tsi.DatasetSourcesQueryReq(
                project_id=PROJECT,
                dataset_object_id="ds",
                row_digests=["row1"],
                source_kinds=[tsi.SourceKind.CALL],
                include_deleted=True,
                limit=10,
                offset=2,
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "dataset_object_id": "ds",
                "row_digests": ["row1"],
                "source_kinds": ["call"],
                "include_deleted": True,
                "limit": 10,
                "offset": 2,
                "wb_user_id": "user-id",
            },
            id="dataset_sources_query",
        ),
        pytest.param(
            "source_datasets_query",
            tsi.SourceDatasetsQueryReq(
                project_id=PROJECT,
                sources=[
                    tsi.SourceRef(
                        source_kind=tsi.SourceKind.SPAN,
                        source_id="s1",
                        source_trace_id="t1",
                    )
                ],
                include_deleted=True,
                wb_user_id="user-id",
            ),
            {
                "project_id": PROJECT,
                "sources": [
                    {
                        "source_kind": "span",
                        "source_id": "s1",
                        "source_trace_id": "t1",
                    }
                ],
                "include_deleted": True,
                "wb_user_id": "user-id",
            },
            id="source_datasets_query",
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
            "agent_spans_query",
            agent_types.AgentSpansQueryReq(
                project_id=PROJECT,
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": "attributes.model"},
                            {"$literal": "gpt-4o"},
                        ]
                    }
                },
                group_by=[
                    agent_types.AgentGroupByRef(source="column", key="conversation_id")
                ],
                insight_filters=[
                    agent_types.AgentInsightFilter(
                        field="failure_severity",
                        values=["major"],
                    ),
                    agent_types.AgentInsightFilter(
                        field="intent_topic_id",
                        values=["01994634-c680-7dc3-a40b-0383b5008d70"],
                    ),
                ],
            ),
            {
                "project_id": PROJECT,
                "query": {
                    "$expr": {
                        "$eq": [
                            {"$getField": "attributes.model"},
                            {"$literal": "gpt-4o"},
                        ]
                    },
                },
                "custom_attr_columns": [],
                "group_by": [
                    {
                        "alias": None,
                        "key": "conversation_id",
                        "source": "column",
                    }
                ],
                "group_distributions": [],
                "group_filters": [],
                "include_costs": False,
                "include_details": False,
                "insight_filters": [
                    {
                        "exclude": False,
                        "field": "failure_severity",
                        "values": ["major"],
                    },
                    {
                        "exclude": False,
                        "field": "intent_topic_id",
                        "values": ["01994634-c680-7dc3-a40b-0383b5008d70"],
                    },
                ],
                "limit": 100,
                "measures": [],
                "offset": 0,
                "signal_filters": None,
                "sort_by": None,
                "started_after": None,
                "started_before": None,
            },
            id="agent_spans_query",
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
                        query={
                            "$expr": {
                                "$eq": [{"$getField": "output.x"}, {"$literal": 1}]
                            }
                        },
                    )
                ],
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
                "sort_by": None,
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


@pytest.mark.parametrize("as_dict", [False, True])
@pytest.mark.parametrize("include_model_tool_calls", [None, False, True])
def test_chat_tool_call_option_reaches_http(
    include_model_tool_calls: bool | None, as_dict: bool
) -> None:
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))
    trace_req = agent_types.AgentTraceChatReq(project_id=PROJECT, trace_id="t1")
    conversation_req = agent_types.AgentConversationChatReq(
        project_id=PROJECT, conversation_id="conv1"
    )
    if include_model_tool_calls is not None:
        trace_req.include_model_tool_calls = include_model_tool_calls
        conversation_req.include_model_tool_calls = include_model_tool_calls

    trace = mock_server.server.agent_traces_chat(
        trace_req.model_dump() if as_dict else trace_req
    )
    conversation = mock_server.server.agent_conversation_chat(
        conversation_req.model_dump() if as_dict else conversation_req
    )

    assert isinstance(trace, AgentTraceChatRes)
    assert isinstance(conversation, ConversationChatResponse)
    assert [request.url.path for request in mock_server.requests] == [
        "/agents/traces/chat",
        "/agents/conversations/chat",
    ]
    expected_bodies = [
        {"project_id": PROJECT, "trace_id": "t1", "include_feedback": False},
        {
            "project_id": PROJECT,
            "conversation_id": "conv1",
            "include_feedback": False,
            "limit": conversation_req.limit,
            "offset": 0,
        },
    ]
    for body in expected_bodies:
        body["include_model_tool_calls"] = include_model_tool_calls is True

    assert [
        json.loads(request.content) for request in mock_server.requests
    ] == expected_bodies


def test_agent_spans_stats_sends_insight_filters() -> None:
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))
    req = agent_types.AgentSpanStatsReq(
        project_id=PROJECT,
        start=START,
        end=END,
        metrics=[
            agent_types.AgentSpanStatsMetricSpec(
                alias="spans",
                value_type="datetime",
                value=agent_types.AgentSpanValueRef(source="field", key="started_at"),
                aggregations=["count"],
            )
        ],
        insight_filters=[
            agent_types.AgentInsightFilter(
                field="failure_severity",
                values=["major"],
            ),
            agent_types.AgentInsightFilter(
                field="intent_topic_id",
                values=["01994634-c680-7dc3-a40b-0383b5008d70"],
            ),
        ],
    )

    mock_server.server.agent_spans_stats(req)

    assert len(mock_server.requests) == 1
    assert json.loads(mock_server.requests[0].content)["insight_filters"] == [
        {
            "exclude": False,
            "field": "failure_severity",
            "values": ["major"],
        },
        {
            "exclude": False,
            "field": "intent_topic_id",
            "values": ["01994634-c680-7dc3-a40b-0383b5008d70"],
        },
    ]


def test_stream_route_sends_every_supported_field():
    """Test that the stream route, which dumps its own request, sends every field."""
    mock_server = _mock_server(
        httpx.Response(200, content=b"", headers={"content-type": "application/jsonl"})
    )

    list(
        mock_server.server.annotation_queues_query_stream(
            tsi.AnnotationQueuesQueryReq(project_id=PROJECT)
        )
    )

    assert len(mock_server.requests) == 1
    assert json.loads(mock_server.requests[0].content) == {
        "project_id": PROJECT,
        "limit": None,
        "offset": None,
        "name": None,
        "sort_by": None,
    }


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
    assert res == {}


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
    assert isinstance(res, CallUpsertBatchResponse)
    assert res.res == [ReCallStartRes(id="call-id", trace_id="trace-id"), {}]


def _strip(hint: Any) -> tuple[Any, list[Any]]:
    """Drop `Required`, `NotRequired` and `Annotated`; return the type and metadata."""
    metadata: list[Any] = []
    while typing_extensions.get_origin(hint) in {
        typing_extensions.Required,
        typing_extensions.NotRequired,
        typing_extensions.Annotated,
    }:
        if typing_extensions.get_origin(hint) is typing_extensions.Annotated:
            metadata.extend(hint.__metadata__)
        hint = typing_extensions.get_args(hint)[0]
    return hint, metadata


def _typed_dicts(hint: Any) -> list[type]:
    """The TypedDicts a value of type `hint` can be, in declaration order."""
    hint, _ = _strip(hint)
    if typing_extensions.get_origin(hint) in {typing.Union, types.UnionType}:
        return [
            t for arg in typing_extensions.get_args(hint) for t in _typed_dicts(arg)
        ]
    return [hint] if typing_extensions.is_typeddict(hint) else []


def _sentinel_params(typed_dict: type, here: str = "") -> dict[str, Any]:
    """A value for every key of `typed_dict`, each naming its own place on the wire.

    Nested TypedDicts, and lists of them, are filled the same way; every other
    value is the string `<path>`, which the generated client sends unchanged.
    """
    params: dict[str, Any] = {}
    hints = typing_extensions.get_type_hints(typed_dict, include_extras=True)
    for key, hint in hints.items():
        stripped, metadata = _strip(hint)
        wire_key = next((m.alias for m in metadata if getattr(m, "alias", None)), key)
        path = f"{here}.{wire_key}" if here else wire_key
        origin = typing_extensions.get_origin(stripped)
        if origin in {list, collections.abc.Iterable, collections.abc.Sequence}:
            members = _typed_dicts(typing_extensions.get_args(stripped)[0])
            params[key] = (
                [_sentinel_params(t, f"{path}[{i}]") for i, t in enumerate(members)]
                if members
                else f"<{path}>"
            )
        elif members := _typed_dicts(stripped):
            params[key] = _sentinel_params(members[0], path)
        else:
            params[key] = f"<{path}>"
    return params


def _leaves(value: Any, here: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{here}.{key}" if here else key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _leaves(item, f"{here}[{i}]")
    else:
        yield here, value


@pytest.mark.parametrize(
    ("method_name", "params_type", "expected_method", "expected_path"),
    [
        pytest.param("call_start", CallStartParams, "POST", "/call/start"),
        pytest.param("call_end", CallEndParams, "POST", "/call/end"),
        pytest.param(
            "call_start_batch", CallUpsertBatchParams, "POST", "/call/upsert_batch"
        ),
        pytest.param("call_update", CallUpdateParams, "POST", "/call/update"),
        pytest.param("calls_delete", CallDeleteParams, "POST", "/calls/delete"),
        pytest.param("call_read", CallReadParams, "POST", "/call/read"),
        pytest.param(
            "calls_query", CallStreamQueryParams, "POST", "/calls/stream_query"
        ),
        pytest.param(
            "calls_query_stream",
            CallStreamQueryParams,
            "POST",
            "/calls/stream_query",
        ),
        pytest.param(
            "calls_query_stats", CallQueryStatsParams, "POST", "/calls/query_stats"
        ),
        pytest.param("call_stats", CallStatsParams, "POST", "/calls/stats"),
        pytest.param("trace_usage", TraceUsageParams, "POST", "/trace/usage"),
        pytest.param("calls_usage", CallUsageParams, "POST", "/calls/usage"),
        pytest.param(
            "threads_query_stream",
            ThreadStreamQueryParams,
            "POST",
            "/threads/stream_query",
        ),
        pytest.param("feedback_query", FeedbackQueryParams, "POST", "/feedback/query"),
        pytest.param("feedback_purge", FeedbackPurgeParams, "POST", "/feedback/purge"),
        pytest.param(
            "feedback_replace", FeedbackReplaceParams, "POST", "/feedback/replace"
        ),
        pytest.param("feedback_stats", FeedbackStatsParams, "POST", "/feedback/stats"),
        pytest.param(
            "feedback_aggregate", FeedbackAggregateParams, "POST", "/feedback/aggregate"
        ),
        pytest.param(
            "feedback_payload_schema",
            FeedbackPayloadSchemaParams,
            "POST",
            "/feedback/payload_schema",
        ),
        pytest.param("cost_query", CostQueryParams, "POST", "/cost/query"),
        pytest.param("cost_create", CostCreateParams, "POST", "/cost/create"),
        pytest.param("cost_purge", CostPurgeParams, "POST", "/cost/purge"),
        pytest.param(
            "completions_create", CompletionCreateParams, "POST", "/completions/create"
        ),
        pytest.param("image_create", ImageCreateParams, "POST", "/image/create"),
        pytest.param("project_stats", ProjectStatsParams, "POST", "/project/stats"),
        pytest.param(
            "project_ttl_settings_read",
            TtlSettingReadParams,
            "POST",
            "/project/ttl_settings/read",
        ),
        pytest.param(
            "project_ttl_settings_update",
            TtlSettingUpdateParams,
            "POST",
            "/project/ttl_settings/update",
        ),
        pytest.param(
            "dataset_sources_link",
            DatasetSourceLinkParams,
            "POST",
            "/dataset_sources/link",
        ),
        pytest.param(
            "dataset_sources_query",
            DatasetSourceQueryParams,
            "POST",
            "/dataset_sources/query",
        ),
        pytest.param(
            "source_datasets_query",
            DatasetSourceSourceDatasetsQueryParams,
            "POST",
            "/dataset_sources/source_datasets_query",
        ),
        pytest.param(
            "annotation_queue_create",
            AnnotationQueueCreateParams,
            "POST",
            "/annotation_queues",
        ),
        pytest.param(
            "annotation_queues_stats",
            AnnotationQueueStatsParams,
            "POST",
            "/annotation_queues/stats",
        ),
        pytest.param(
            "evaluate_model",
            EvaluationEvaluateModelParams,
            "POST",
            "/evaluations/evaluate_model",
        ),
        pytest.param(
            "evaluation_status", EvaluationStatusParams, "POST", "/evaluations/status"
        ),
        pytest.param(
            "rescore", EvaluationRescoreParams, "POST", "/evaluations/rescore"
        ),
        pytest.param("calls_score", CallScoreParams, "POST", "/calls/score"),
        pytest.param(
            "projects_info",
            ServiceProjectsInfoParams,
            "POST",
            "/service/projects_info",
        ),
        pytest.param(
            "agent_spans_query", SpanQueryParams, "POST", "/agents/spans/query"
        ),
        pytest.param(
            "agent_traces_chat", TraceChatParams, "POST", "/agents/traces/chat"
        ),
        pytest.param(
            "agent_conversation_chat",
            ConversationChatParams,
            "POST",
            "/agents/conversations/chat",
        ),
        pytest.param(
            "agent_conversation_spans",
            ConversationSpansParams,
            "POST",
            "/agents/conversations/spans",
        ),
        pytest.param("agent_agents_query", AgentQueryParams, "POST", "/agents/query"),
        pytest.param(
            "agent_versions_query",
            AgentVersionQueryParams,
            "POST",
            "/agents/agent-versions/query",
        ),
        pytest.param(
            "agent_spans_stats", SpanStatsParams, "POST", "/agents/spans/stats"
        ),
        pytest.param(
            "agent_custom_attrs_schema",
            SpanCustomAttrsSchemaParams,
            "POST",
            "/agents/spans/custom-attrs/schema",
        ),
        pytest.param("agent_search", AgentSearchParams, "POST", "/agents/search"),
        pytest.param("obj_create", ObjectCreateParams, "POST", "/obj/create"),
        pytest.param("obj_read", ObjectReadParams, "POST", "/obj/read"),
        pytest.param("objs_query", ObjectQueryParams, "POST", "/objs/query"),
        pytest.param("obj_delete", ObjectDeleteParams, "POST", "/obj/delete"),
        pytest.param(
            "obj_add_tags",
            ObjAddTagsParams,
            "PUT",
            "/objs/<object_id>/versions/<digest>/tags",
        ),
        pytest.param(
            "obj_remove_tags",
            ObjRemoveTagsParams,
            "POST",
            "/objs/<object_id>/versions/<digest>/tags/remove",
        ),
        pytest.param(
            "obj_set_aliases", ObjSetAliasesParams, "PUT", "/objs/<object_id>/aliases"
        ),
        pytest.param(
            "obj_remove_aliases",
            ObjRemoveAliasesParams,
            "POST",
            "/objs/<object_id>/aliases/remove",
        ),
        pytest.param("tags_list", TagListParams, "GET", "/tags"),
        pytest.param("aliases_list", AliasListParams, "GET", "/aliases"),
        pytest.param("table_create", TableCreateParams, "POST", "/table/create"),
        pytest.param("table_update", TableUpdateParams, "POST", "/table/update"),
        pytest.param("table_query", TableQueryParams, "POST", "/table/query"),
        pytest.param(
            "table_query_stats", TableQueryStatsParams, "POST", "/table/query_stats"
        ),
        pytest.param(
            "table_query_stats_batch",
            TableQueryStatsBatchParams,
            "POST",
            "/table/query_stats_batch",
        ),
        pytest.param(
            "table_create_from_digests",
            TableCreateFromDigestsParams,
            "POST",
            "/table/create_from_digests",
        ),
        pytest.param("refs_read_batch", RefReadBatchParams, "POST", "/refs/read_batch"),
        pytest.param("file_content_read", FileContentParams, "POST", "/file/content"),
        pytest.param("files_stats", FileStatsParams, "POST", "/files/query_stats"),
    ],
)
def test_every_params_key_reaches_the_request(
    method_name: str, params_type: type, expected_method: str, expected_path: str
):
    """A binding method given the generated client's params must lose no key."""
    mock_server = _mock_server(
        httpx.Response(
            200, json={"id": "c1", "trace_id": "t1", "num_deleted": 0, "res": []}
        )
    )
    params = _sentinel_params(params_type)

    res = getattr(mock_server.server, method_name)(params)
    if isinstance(res, Iterator):
        list(res)

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    assert (request.method, request.url.path) == (expected_method, expected_path)
    body = dict(_leaves(json.loads(request.content) if request.content else {}))
    # A header parameter (the stream's `accept`) joins the generated default.
    headers = [v for h in request.headers.values() for v in h.split(", ")]
    sent = sorted(
        [
            *body.values(),
            *request.url.params.values(),
            *request.url.path.split("/"),
            *headers,
        ]
    )
    assert [s for s in sent if s.startswith("<")] == sorted(
        value for _, value in _leaves(params)
    )
    # Each value sits under the key path it names.
    assert all(value == f"<{path}>" for path, value in body.items())


@pytest.mark.parametrize(
    ("method_name", "params", "expected_method", "expected_path"),
    [
        pytest.param(
            "annotation_queue_read",
            {**_sentinel_params(AnnotationQueueReadParams), "queue_id": "<queue_id>"},
            "GET",
            "/annotation_queues/<queue_id>",
            id="annotation_queue_read",
        ),
        pytest.param(
            "annotation_queue_delete",
            {**_sentinel_params(AnnotationQueueDeleteParams), "queue_id": "<queue_id>"},
            "DELETE",
            "/annotation_queues/<queue_id>",
            id="annotation_queue_delete",
        ),
        pytest.param(
            "annotation_queue_update",
            {**_sentinel_params(AnnotationQueueUpdateParams), "queue_id": "<queue_id>"},
            "PUT",
            "/annotation_queues/<queue_id>",
            id="annotation_queue_update",
        ),
        pytest.param(
            "annotation_queue_add_calls",
            {**_sentinel_params(ItemAddParams), "queue_id": "<queue_id>"},
            "POST",
            "/annotation_queues/<queue_id>/items",
            id="annotation_queue_add_calls",
        ),
        pytest.param(
            "annotation_queue_items_query",
            {**_sentinel_params(ItemQueryParams), "queue_id": "<queue_id>"},
            "POST",
            "/annotation_queues/<queue_id>/items/query",
            id="annotation_queue_items_query",
        ),
        pytest.param(
            "annotator_queue_items_progress_update",
            {**_sentinel_params(ItemUpdateProgressParams), "item_id": "<item_id>"},
            "POST",
            "/annotation_queues/<queue_id>/items/<item_id>/progress",
            id="annotator_queue_items_progress_update",
        ),
        pytest.param(
            "annotation_queues_query_stream",
            _sentinel_params(AnnotationQueueQueryParams),
            "POST",
            "/annotation_queues/query",
            id="annotation_queues_query_stream",
        ),
        pytest.param(
            "completions_create_stream",
            _sentinel_params(CompletionCreateStreamParams),
            "POST",
            "/completions/create_stream",
            id="completions_create_stream",
        ),
    ],
)
def test_every_key_of_a_path_or_stream_request_reaches_it(
    method_name: str, params: dict[str, Any], expected_method: str, expected_path: str
):
    """Path parameters, which the params TypedDict leaves out, and streams lose no key."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))

    res = getattr(mock_server.server, method_name)(params)
    if inspect.isgenerator(res):
        list(res)

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    assert (request.method, request.url.path) == (expected_method, expected_path)
    body = dict(_leaves(json.loads(request.content))) if request.content else {}
    sent = sorted(
        [*body.values(), *request.url.params.values(), *request.url.path.split("/")]
    )
    assert [s for s in sent if s.startswith("<")] == sorted(
        value for _, value in _leaves(params)
    )
    assert all(value == f"<{path}>" for path, value in body.items())


def test_custom_runtime_apply_sends_every_key():
    """The project id and runtime name make the path; every other key is the body."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))
    body = _sentinel_params(V2RuntimeApplyParams)
    entity, project = body.pop("entity"), body.pop("project")

    mock_server.server.custom_runtime_apply(
        {"project_id": f"{entity}/{project}", "runtime_name": "<runtime_name>", **body}
    )

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    assert (request.method, request.url.path) == (
        "PUT",
        "/v2/<entity>/<project>/runtimes/<runtime_name>",
    )
    assert json.loads(request.content) == body


@pytest.mark.parametrize(
    ("method_name", "params_type", "expected_path", "dropped"),
    [
        pytest.param(
            "feedback_create",
            FeedbackCreateParams,
            "/feedback/create",
            ["<id>"],
            id="feedback_create",
        ),
        pytest.param(
            "feedback_create_batch",
            FeedbackBatchCreateParams,
            "/feedback/batch/create",
            ["<batch[0].id>"],
            id="feedback_create_batch",
        ),
    ],
)
def test_feedback_create_sends_every_key_but_the_id(
    method_name: str, params_type: type, expected_path: str, dropped: list[str]
):
    """Feedback creation sends every key it is given except the feedback id."""
    mock_server = _mock_server(httpx.Response(200, json=V1_RESPONSE))
    params = _sentinel_params(params_type)

    getattr(mock_server.server, method_name)(params)

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    assert (request.method, request.url.path) == ("POST", expected_path)
    body = dict(_leaves(json.loads(request.content)))
    assert sorted(body.values()) == sorted(
        value for _, value in _leaves(params) if value not in dropped
    )
    assert all(value == f"<{path}>" for path, value in body.items())


@pytest.mark.parametrize(
    ("method_name", "generated_method", "params_type"),
    [
        pytest.param("op_create", "v2_ops.create", V2OpCreateParams),
        pytest.param("op_read", "v2_ops.read", None),
        pytest.param("op_list", "v2_ops.list", V2OpListParams),
        pytest.param("op_delete", "v2_ops.delete", V2OpDeleteParams),
        pytest.param("dataset_create", "v2_datasets.create", V2DatasetCreateParams),
        pytest.param("dataset_read", "v2_datasets.read", None),
        pytest.param("dataset_list", "v2_datasets.list", V2DatasetListParams),
        pytest.param("dataset_delete", "v2_datasets.delete", V2DatasetDeleteParams),
        pytest.param("scorer_create", "v2_scorers.create", V2ScorerCreateParams),
        pytest.param("scorer_read", "v2_scorers.read", None),
        pytest.param("scorer_list", "v2_scorers.list", V2ScorerListParams),
        pytest.param("scorer_delete", "v2_scorers.delete", V2ScorerDeleteParams),
        pytest.param(
            "evaluation_create", "v2_evaluations.create", V2EvaluationCreateParams
        ),
        pytest.param("evaluation_read", "v2_evaluations.read", None),
        pytest.param("evaluation_list", "v2_evaluations.list", V2EvaluationListParams),
        pytest.param(
            "evaluation_delete", "v2_evaluations.delete", V2EvaluationDeleteParams
        ),
        pytest.param("model_create", "v2_models.create", V2ModelCreateParams),
        pytest.param("model_read", "v2_models.read", None),
        pytest.param("model_list", "v2_models.list", V2ModelListParams),
        pytest.param("model_delete", "v2_models.delete", V2ModelDeleteParams),
        pytest.param(
            "evaluation_run_create",
            "v2_evaluation_runs.create",
            V2EvaluationRunCreateParams,
        ),
        pytest.param("evaluation_run_read", "v2_evaluation_runs.read", None),
        pytest.param(
            "evaluation_run_list", "v2_evaluation_runs.list", V2EvaluationRunListParams
        ),
        pytest.param(
            "evaluation_run_delete",
            "v2_evaluation_runs.delete",
            V2EvaluationRunDeleteParams,
        ),
        pytest.param(
            "evaluation_run_finish",
            "v2_evaluation_runs.finish",
            V2EvaluationRunFinishParams,
        ),
        pytest.param(
            "prediction_create", "v2_predictions.create", V2PredictionCreateParams
        ),
        pytest.param("prediction_read", "v2_predictions.read", None),
        pytest.param("prediction_list", "v2_predictions.list", V2PredictionListParams),
        pytest.param(
            "prediction_delete", "v2_predictions.delete", V2PredictionDeleteParams
        ),
        pytest.param("prediction_finish", "v2_predictions.finish", None),
        pytest.param("score_create", "v2_scores.create", V2ScoreCreateParams),
        pytest.param("score_read", "v2_scores.read", None),
        pytest.param("score_list", "v2_scores.list", V2ScoreListParams),
        pytest.param("score_delete", "v2_scores.delete", V2ScoreDeleteParams),
        pytest.param(
            "eval_results_query", "v2_eval_results.query", V2EvalResultQueryParams
        ),
    ],
)
def test_every_v2_argument_reaches_the_request(
    method_name: str, generated_method: str, params_type: type | None
):
    """A v2 binding method must pass on every argument of its generated method.

    The binding takes the project as `project_id`, which fills the route's
    `entity` and `project` path parameters.
    """
    mock_server = _mock_server(httpx.Response(200, json=V2_RESPONSE))
    generated = operator.attrgetter(generated_method)(
        mock_server.server._stainless_client
    )
    typed = _sentinel_params(params_type) if params_type is not None else {}
    arguments = {
        name: typed.get(name, f"<{name}>")
        for name in inspect.signature(generated).parameters
        if name not in {"extra_headers", "extra_query", "extra_body", "timeout"}
    }
    req = {
        "project_id": f"{arguments.pop('entity')}/{arguments.pop('project')}",
        **arguments,
    }

    res = getattr(mock_server.server, method_name)(req)
    if inspect.isgenerator(res):
        list(res)

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    body = dict(_leaves(json.loads(request.content))) if request.content else {}
    sent = sorted(
        [*body.values(), *request.url.params.values(), *request.url.path.split("/")]
    )
    assert [s for s in sent if s.startswith("<")] == sorted(
        ["<entity>", "<project>", *(value for _, value in _leaves(arguments))]
    )
    # Each body value sits under the key path it names.
    assert all(value == f"<{path}>" for path, value in body.items())


def test_evaluation_run_list_sends_the_filter_as_query_params():
    """Test that each filter field of a request model becomes its own query param."""
    mock_server = _mock_server(
        httpx.Response(200, content=b"", headers={"content-type": "application/jsonl"})
    )

    res = mock_server.server.evaluation_run_list(
        tsi.EvaluationRunListReq(
            project_id=PROJECT,
            filter=tsi.EvaluationRunFilter(
                evaluations=["ev-ref"], models=["m1", "m2"], evaluation_run_ids=["r1"]
            ),
            limit=10,
        )
    )

    assert list(res) == []
    assert len(mock_server.requests) == 1
    assert mock_server.requests[0].url.path == f"{V2}/evaluation_runs"
    assert mock_server.requests[0].url.params.multi_items() == [
        ("evaluation_run_ids", "r1"),
        ("evaluations", "ev-ref"),
        ("limit", "10"),
        ("models", "m1"),
        ("models", "m2"),
    ]


@pytest.mark.parametrize("should_batch", [False, True])
def test_call_records_written_from_models_replay(should_batch: bool, monkeypatch):
    """A WAL record holds a request model's JSON dump; replaying sends it."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "call-id", "trace_id": "test_trace_id"})

    server = StainlessRemoteHTTPTraceServer(BASE_URL, should_batch=should_batch)
    server._stainless_client = StainlessClient(
        base_url=BASE_URL,
        username="",
        password="",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    start, end = generate_call_start_end_pair(id="call-id", project_id=PROJECT)
    records = [
        {"type": "call_start", "req": start.model_dump(mode="json")},
        {"type": "call_end", "req": end.model_dump(mode="json")},
    ]

    handlers = build_trace_server_handlers(server)
    for record in records:
        handlers[record["type"]](record)
    if server.call_processor is not None:
        server.call_processor.stop_accepting_new_work_and_flush_queue()

    sent = [(r.url.path, json.loads(r.content)) for r in requests]
    if not should_batch:
        assert sent == [
            ("/call/start", records[0]["req"]),
            ("/call/end", records[1]["req"]),
        ]
    else:
        paired = tsi.CompletedCallSchemaForInsert(
            project_id=PROJECT,
            id="call-id",
            trace_id=start.start.trace_id,
            op_name=start.start.op_name,
            parent_id=start.start.parent_id,
            started_at=start.start.started_at,
            attributes=start.start.attributes,
            inputs=start.start.inputs,
            ended_at=end.end.ended_at,
            summary=end.end.summary,
        )
        assert sent == [
            (
                f"{V2}/calls/complete",
                tsi.CallsUpsertCompleteReq(batch=[paired]).model_dump(mode="json"),
            )
        ]


def _sent(request: httpx.Request) -> tuple[str, str, bytes]:
    """A request's method, path and body, with any multipart boundary made fixed."""
    body = request.read()
    content_type = request.headers.get("content-type", "")
    if "boundary=" in content_type:
        body = body.replace(content_type.split("boundary=")[1].encode(), b"BOUNDARY")
    return request.method, request.url.path, body


def test_object_records_written_from_models_replay():
    """WAL records hold a request model's JSON dump; replaying sends what the model did."""
    models: dict[str, BaseModel] = {
        "obj_create": tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT, object_id="o", val={"a": [1, "b", None]}
            )
        ),
        "table_create": tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(project_id=PROJECT, rows=[{"x": 1.5}])
        ),
        "file_create": tsi.FileCreateReq(
            project_id=PROJECT,
            name="f.txt",
            content="café".encode(),
            expected_digest="d",
        ),
    }
    direct = _mock_server(httpx.Response(200, json={"digest": "d"}))
    for method_name, req in models.items():
        getattr(direct.server, method_name)(req)

    replayed = _mock_server(httpx.Response(200, json={"digest": "d"}))
    handlers = build_trace_server_handlers(replayed.server)
    for record_type, req in models.items():
        handlers[record_type]({"type": record_type, "req": req.model_dump(mode="json")})

    assert len(direct.requests) == 3
    assert [_sent(r) for r in replayed.requests] == [_sent(r) for r in direct.requests]


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
                ThreadStreamQueryResponse(
                    thread_id="t1",
                    turn_count=1,
                    start_time="2026-08-20T00:00:00Z",
                    last_updated="2026-08-20T00:00:00Z",
                    first_turn_id=None,
                    last_turn_id=None,
                    p50_turn_duration_ms=None,
                    p99_turn_duration_ms=None,
                ),
                ThreadStreamQueryResponse(
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
                V2OpListResponse(
                    object_id="op-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    code="def f(): pass",
                ),
                V2OpListResponse(
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
                V2DatasetListResponse(
                    object_id="ds-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="ds-1",
                    rows="weave:///entity/project/table/abc123",
                ),
                V2DatasetListResponse(
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
                V2ScorerListResponse(
                    object_id="s-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="s-1",
                    score_op="weave:///entity/project/op/s:abc123",
                ),
                V2ScorerListResponse(
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
                V2EvaluationListResponse(
                    object_id="ev-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="ev-1",
                    dataset="weave:///entity/project/object/ds:abc123",
                    scorers=[],
                    trials=1,
                ),
                V2EvaluationListResponse(
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
                V2ModelListResponse(
                    object_id="m-1",
                    digest="d1",
                    version_index=0,
                    created_at="2026-08-20T00:00:00Z",
                    name="m-1",
                    source_code="def f(): pass",
                ),
                V2ModelListResponse(
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
                V2EvaluationRunListResponse(
                    evaluation_run_id="r1", evaluation="ev-ref", model="m-ref"
                ),
                V2EvaluationRunListResponse(
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
                V2PredictionListResponse(
                    prediction_id="p1", model="m-ref", inputs={}, output=None
                ),
                V2PredictionListResponse(
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
                V2ScoreListResponse(score_id="s1", scorer="s-ref", value=1),
                V2ScoreListResponse(score_id="s2", scorer="s-ref", value=2),
            ],
            id="score_list",
        ),
        pytest.param(
            "annotation_queues_query_stream",
            tsi.AnnotationQueuesQueryReq(project_id=PROJECT),
            "/annotation_queues/query",
            [QUEUE, {**QUEUE, "id": "q2"}],
            [
                AnnotationQueueSchema.construct(**QUEUE),
                AnnotationQueueSchema.construct(**{**QUEUE, "id": "q2"}),
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
            "otel_export",
            tsi.OTelExportReq(project_id=PROJECT, processed_spans=[]),
            id="otel_export",
        ),
    ],
)
def test_route_missing_from_the_spec_raises(method_name: str, req: BaseModel):
    """Test that a method with no usable generated route says so."""
    mock_server = _mock_server(httpx.Response(200, json={}))

    with pytest.raises(NotImplementedError):
        getattr(mock_server.server, method_name)(req)

    assert mock_server.requests == []


def test_completions_create_stream_reads_ndjson_chunks():
    """Test that the stream keeps _meta on the first line and omits it later."""
    mock_server = _mock_server(
        httpx.Response(
            200,
            content="\n".join(
                [
                    json.dumps({"_meta": {"weave_call_id": "c1", "trace_id": "t1"}}),
                    json.dumps({"choices": [{"delta": {"content": "hi"}}]}),
                ]
            ).encode(),
            headers={"content-type": "application/x-ndjson"},
        )
    )

    chunks = list(
        mock_server.server.completions_create_stream(
            tsi.CompletionsCreateReq(
                project_id=PROJECT,
                inputs={"model": "gpt-4o", "messages": [{"role": "user"}]},
                wb_user_id="user-id",
            )
        )
    )

    assert len(mock_server.requests) == 1
    request = mock_server.requests[0]
    assert (request.method, request.url.path) == ("POST", "/completions/create_stream")
    assert request.headers["accept"] == "application/x-ndjson"
    assert "_meta" in chunks[0]
    assert "api_meta" not in chunks[0]
    assert chunks[0]["_meta"]["weave_call_id"] == "c1"
    assert "_meta" not in chunks[1]
    assert "error" not in chunks[1]
    assert chunks[1]["choices"] == [{"delta": {"content": "hi"}}]
    assert json.loads(request.content)["wb_user_id"] == "user-id"


@pytest.mark.parametrize(
    "req",
    [
        pytest.param(
            tsi.FileCreateReq(
                project_id=PROJECT,
                name="pic.png",
                content=b"\x89PNG",
                expected_digest="deadbeef",
            ),
            id="model",
        ),
        pytest.param(
            {
                "project_id": PROJECT,
                "file": ("pic.png", b"\x89PNG"),
                "expected_digest": "deadbeef",
            },
            id="dict",
        ),
    ],
)
def test_file_create_sends_the_filename(req):
    """Test that the upload keeps the filename on the multipart part."""
    mock_server = _mock_server(httpx.Response(200, json={"digest": "abc123"}))

    res = mock_server.server.file_create(req)

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
    assert res == FileCreateResponse(digest="abc123")


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
