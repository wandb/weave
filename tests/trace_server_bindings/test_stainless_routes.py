"""Tests for the requests StainlessRemoteHTTPTraceServer sends.

These tests drive the binding through the vendored generated client over an
httpx.MockTransport, so what they assert is the request the generated resource
builds. The file is not gated to the stainless shard, so it also runs against
the default one.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from tests.trace_server_bindings.conftest import generate_call_start_end_pair
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient

BASE_URL = "http://example.com"
PROJECT = "entity/project"
V2 = "/v2/entity/project"

# One body serves the whole route table: it carries the union of the v2 response
# models' required fields, and those models ignore the fields they do not declare.
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


def _mock_server(
    response: httpx.Response,
) -> tuple[StainlessRemoteHTTPTraceServer, list[httpx.Request]]:
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
    return server, requests


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
    server, requests = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    res = getattr(server, method_name)(req)

    assert [(r.method, r.url.path) for r in requests] == [
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
    server, requests = _mock_server(httpx.Response(200, json={}))

    getattr(server, method_name)(req)

    assert len(requests) == 1
    assert (requests[0].method, requests[0].url.path) == (
        expected_method,
        expected_path,
    )
    assert json.loads(requests[0].content) == expected_body


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
    server, requests = _mock_server(
        httpx.Response(200, json={"tags": [], "aliases": []})
    )

    getattr(server, method_name)(req)

    assert len(requests) == 1
    assert (requests[0].method, requests[0].url.path) == ("GET", expected_path)
    assert dict(requests[0].url.params) == {"project_id": PROJECT}


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
    server, requests = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    getattr(server, method_name)(req)

    assert len(requests) == 1
    assert (requests[0].method, requests[0].url.path) == ("DELETE", expected_path)
    assert dict(requests[0].url.params) == {"digests": "abc123"}


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
    server, requests = _mock_server(httpx.Response(200, json=V2_RESPONSE))

    getattr(server, method_name)(req)

    assert len(requests) == 1
    assert json.loads(requests[0].content) == expected_body


def test_call_end_reads_an_empty_response_body():
    """Test that a route generated as returning a bare `object` is read back."""
    server, requests = _mock_server(httpx.Response(200, json={}))

    res = server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=PROJECT,
                id="call-id",
                ended_at="2026-08-20T00:00:00Z",
                summary={},
            )
        )
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/call/end"
    assert res == tsi.CallEndRes()


def test_call_start_batch_reads_the_response_list():
    """Test that the batch response is read from the field the route returns."""
    server, requests = _mock_server(
        httpx.Response(
            200, json={"res": [{"id": "call-id", "trace_id": "trace-id"}, {}]}
        )
    )
    start, end = generate_call_start_end_pair(id="call-id")

    res = server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(req=start),
                tsi.CallBatchEndMode(req=end),
            ]
        )
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/call/upsert_batch"
    assert res.res == [
        tsi.CallStartRes(id="call-id", trace_id="trace-id"),
        tsi.CallEndRes(),
    ]


@pytest.mark.parametrize(
    ("method_name", "req", "expected_path", "rows", "expected"),
    [
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
    server, requests = _mock_server(
        httpx.Response(
            200,
            content="\n".join(json.dumps(row) for row in rows).encode(),
            headers={"content-type": "application/jsonl"},
        )
    )

    res = list(getattr(server, method_name)(req))

    assert len(requests) == 1
    assert requests[0].url.path == expected_path
    assert res == expected


def test_file_content_read_keeps_bytes():
    """Test that a non-text file comes back as the bytes the server sent."""
    content = b"\x89PNG\r\n\x1a\n\xff\xfe"
    server, requests = _mock_server(
        httpx.Response(
            200, content=content, headers={"content-type": "application/octet-stream"}
        )
    )

    res = server.file_content_read(
        tsi.FileContentReadReq(project_id=PROJECT, digest="abc123")
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/file/content"
    assert res.content == content


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
        pytest.param(
            "file_create",
            tsi.FileCreateReq(project_id=PROJECT, name="pic.png", content=b"\x89PNG"),
            id="file_create",
        ),
    ],
)
def test_route_missing_from_the_spec_raises(method_name: str, req: BaseModel):
    """Test that a method with no usable generated route says so."""
    server, requests = _mock_server(httpx.Response(200, json={}))

    with pytest.raises(NotImplementedError):
        getattr(server, method_name)(req)

    assert requests == []
