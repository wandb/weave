"""Tests for feedback stats and schema discovery."""

from __future__ import annotations

import datetime
import json
import textwrap
from unittest.mock import MagicMock

import pytest

from weave.trace_server.feedback_payload_schema import (
    _discover_paths,
    _infer_value_type,
    discover_payload_schema,
)
from weave.trace_server.feedback_stats_query_builder import (
    JSON_PATH_PATTERN,
    _json_path_to_extraction_sql,
    _json_path_to_metric_slug,
    build_feedback_stats_query,
    build_feedback_stats_window_query,
    trigger_ref_where_clause,
)
from weave.trace_server.methods.feedback_stats import (
    _extract_window_stats,
    _parse_window_stat_col,
    feedback_payload_schema,
    feedback_stats,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    AggregationType,
    FeedbackMetricSpec,
    FeedbackPayloadSchemaReq,
    FeedbackStatsReq,
)

_START = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
_END = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# discover_payload_schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "path", "expected_type"),
    [
        ({"score": 0.9, "passed": True}, "score", float),  # flat float
        ({"score": 0.9, "passed": True}, "passed", bool),  # flat bool
        ({"output": {"score": 0.9}}, "output.score", float),  # nested float
        ({"scores": [0.1, 0.2]}, "scores", float),  # list-of-scalars
        ({"x": None}, "x", type(None)),  # None value
    ],
)
def test_discover_paths_value_shapes(payload, path, expected_type):
    result = _discover_paths(payload)
    assert path in result
    assert expected_type in result[path]


@pytest.mark.parametrize("payload", [{"a.b": 1}, {"": 1}])
def test_discover_paths_skips_invalid_keys(payload):
    assert not _discover_paths(payload)


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        ({int, float}, "numeric"),
        ({int}, "numeric"),
        ({float, type(None)}, "numeric"),
        (set(), "numeric"),  # no types seen -> default numeric
        ({bool}, "boolean"),  # bool is subclass of int, must stay boolean
        ({bool, type(None)}, "boolean"),
        ({str}, "categorical"),
        ({int, str}, "categorical"),
        ({bool, int}, "categorical"),  # mixed bool+int is ambiguous
    ],
)
def test_infer_value_type(types, expected):
    assert _infer_value_type(types) == expected


@pytest.mark.parametrize(
    ("payloads", "expected_subset", "excluded", "expected_len"),
    [
        (['{"output": {"score": 0.9}}'], {"output.score": "numeric"}, [], 1),
        (['{"passed": true}'], {"passed": "boolean"}, [], 1),
        (
            ['{"score": 1.0}', '{"score": 0.5, "label": "good"}'],
            {"score": "numeric", "label": "categorical"},
            [],
            2,
        ),
        (['{"items": [1, 2, 3]}'], {}, ["["], None),  # array-index paths filtered
        (["not json", '{"score": 1.0}'], {"score": "numeric"}, [], 1),
        (["", "   ", '{"x": 1}'], {"x": "numeric"}, [], 1),  # empty strings skipped
        (
            ['{"a b": 1, "c": 2}'],
            {"a b": "numeric", "c": "numeric"},
            [],
            2,
        ),  # spaces ok
        (
            ["""{"a'b": 1, "c": 2}"""],
            {"c": "numeric"},
            ["a'b"],
            1,
        ),  # unsafe char excluded
    ],
)
def test_discover_payload_schema(payloads, expected_subset, excluded, expected_len):
    paths = discover_payload_schema(payloads)
    path_map = {p.json_path: p.value_type for p in paths}
    for path, value_type in expected_subset.items():
        assert path_map[path] == value_type
    for substr in excluded:
        assert all(substr not in name for name in path_map)
    if expected_len is not None:
        assert len(paths) == expected_len


def test_discover_payload_schema_paths_sorted():
    paths = discover_payload_schema(['{"z": 1, "a": 2, "m": 3}'])
    names = [p.json_path for p in paths]
    assert names == sorted(names)


def test_classifier_monitor_payload():
    # Classifier monitors use human-readable names as dictionary keys
    payload = json.dumps(
        {
            "output": {
                "classifier_tags": "Low quality, Bug",
                "classifier_meta": {
                    "Low quality": {"confidence": 0.95, "reason": "evidence"},
                    "Bug": {"confidence": 0.80, "reason": "evidence"},
                },
            }
        }
    )
    paths = discover_payload_schema([payload])
    path_map = {p.json_path: p.value_type for p in paths}
    assert "output.classifier_meta.Low quality.confidence" in path_map
    assert path_map["output.classifier_meta.Low quality.confidence"] == "numeric"
    assert "output.classifier_meta.Bug.confidence" in path_map
    assert path_map["output.classifier_meta.Bug.confidence"] == "numeric"


# ---------------------------------------------------------------------------
# JSON path helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("json_path", "value_type", "expected_sql"),
    [
        (
            "output.score",
            "numeric",
            "toFloat64OrNull(JSONExtractRaw(payload_dump, 'output', 'score'))",
        ),
        (
            "a.b.c",
            "numeric",
            "toFloat64OrNull(JSONExtractRaw(payload_dump, 'a', 'b', 'c'))",
        ),
        (
            "passed",
            "boolean",
            "if(JSONExtractRaw(payload_dump, 'passed') = 'true', 1, if(JSONExtractRaw(payload_dump, 'passed') = 'false', 0, NULL))",
        ),
        ("label", "categorical", "JSONExtractString(payload_dump, 'label')"),
        (
            "output.label",
            "categorical",
            "JSONExtractString(payload_dump, 'output', 'label')",
        ),
    ],
)
def test_json_path_to_extraction_sql(json_path, value_type, expected_sql):
    assert _json_path_to_extraction_sql(json_path, value_type) == expected_sql


@pytest.mark.parametrize(
    ("json_path", "expected_slug"),
    [("output.score", "output_score"), ("score", "score")],
)
def test_json_path_to_metric_slug(json_path, expected_slug):
    assert _json_path_to_metric_slug(json_path) == expected_slug


@pytest.mark.parametrize(
    ("json_path", "error_match"),
    [("output'score", "json_path may only contain"), ("", "cannot be empty")],
)
def test_json_path_to_metric_slug_rejects(json_path, error_match):
    with pytest.raises(ValueError, match=error_match):
        _json_path_to_metric_slug(json_path)


@pytest.mark.parametrize(
    ("path", "should_match"),
    [
        ("output.score", True),
        ("score", True),
        ("a_b.c_d", True),
        ("output.classifier_meta.Low quality.confidence", True),
        ("a[0]", False),
        ("", False),
        ("path'injection", False),
    ],
)
def test_json_path_pattern(path, should_match):
    assert bool(JSON_PATH_PATTERN.match(path)) is should_match


# ---------------------------------------------------------------------------
# trigger_ref_where_clause
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("trigger_ref", "expected_sql", "expected_params"),
    [
        ("my-monitor:v1", "trigger_ref = {pb_0:String}", {"pb_0": "my-monitor:v1"}),
        (
            "my-monitor:*",
            "startsWith(trigger_ref, {pb_0:String})",
            {"pb_0": "my-monitor"},  # trailing :* stripped
        ),
    ],
)
def test_trigger_ref_where_clause(trigger_ref, expected_sql, expected_params):
    pb = _make_pb()
    sql = trigger_ref_where_clause(trigger_ref, pb)
    assert sql == expected_sql
    assert pb.get_params() == expected_params


# ---------------------------------------------------------------------------
# build_feedback_stats_query
# ---------------------------------------------------------------------------


_NUMERIC_BUCKET_SQL = """
WITH all_buckets AS
  (SELECT toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), toIntervalSecond({{{idx}:Int64}}), {{pb_3:String}}) + toIntervalSecond(number * {{{idx}:Int64}}) AS bucket
   FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({{pb_2:Float64}}, {{pb_3:String}})) - toUnixTimestamp(toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), toIntervalSecond({{{idx}:Int64}}), {{pb_3:String}}))) / {{{idx}:Float64}})))
   WHERE bucket < toDateTime({{pb_2:Float64}}, {{pb_3:String}}) ),
     aggregated_data AS
  (SELECT bucket,
          avgOrNull(m_output_score) AS avg_output_score,
          maxOrNull(m_output_score) AS max_output_score,
          quantileOrNull(0.05)(m_output_score) AS p5_output_score,
          quantileOrNull(0.95)(m_output_score) AS p95_output_score,
          count() AS count
   FROM
     (SELECT toStartOfInterval(created_at, toIntervalSecond({{{idx}:Int64}}), {{pb_3:String}}) AS bucket,
             toFloat64OrNull(JSONExtractRaw(payload_dump, 'output', 'score')) AS m_output_score
      FROM feedback
      WHERE project_id = {{pb_0:String}}
        AND created_at >= toDateTime({{pb_1:Float64}}, {{pb_3:String}})
        AND created_at < toDateTime({{pb_2:Float64}}, {{pb_3:String}}){filter_clause} )
   GROUP BY bucket)
SELECT all_buckets.bucket AS timestamp,
       COALESCE(aggregated_data.avg_output_score, 0) AS avg_output_score,
       aggregated_data.max_output_score AS max_output_score,
       aggregated_data.p5_output_score AS p5_output_score,
       aggregated_data.p95_output_score AS p95_output_score,
       COALESCE(aggregated_data.count, 0) AS count
FROM all_buckets
LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
ORDER BY all_buckets.bucket
"""

_BOOLEAN_BUCKET_SQL = """
WITH all_buckets AS
  (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), toIntervalSecond({pb_4:Int64}), {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
   FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), toIntervalSecond({pb_4:Int64}), {pb_3:String}))) / {pb_4:Float64})))
   WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
     aggregated_data AS
  (SELECT bucket,
          countIf(m_passed = 1) AS count_true_passed,
          countIf(m_passed = 0) AS count_false_passed,
          count() AS count
   FROM
     (SELECT toStartOfInterval(created_at, toIntervalSecond({pb_4:Int64}), {pb_3:String}) AS bucket,
             if(JSONExtractRaw(payload_dump, 'passed') = 'true', 1, if(JSONExtractRaw(payload_dump, 'passed') = 'false', 0, NULL)) AS m_passed
      FROM feedback
      WHERE project_id = {pb_0:String}
        AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
        AND created_at < toDateTime({pb_2:Float64}, {pb_3:String}) )
   GROUP BY bucket)
SELECT all_buckets.bucket AS timestamp,
       COALESCE(aggregated_data.count_true_passed, 0) AS count_true_passed,
       COALESCE(aggregated_data.count_false_passed, 0) AS count_false_passed,
       COALESCE(aggregated_data.count, 0) AS count
FROM all_buckets
LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
ORDER BY all_buckets.bucket
"""

_BOOLEAN_METRIC = FeedbackMetricSpec(
    json_path="passed",
    value_type="boolean",
    aggregations=[AggregationType.COUNT_TRUE, AggregationType.COUNT_FALSE],
)


@pytest.mark.parametrize(
    ("req_kwargs", "expected_sql", "expected_params"),
    [
        (
            {},
            _NUMERIC_BUCKET_SQL.format(idx="pb_4", filter_clause=""),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": 21600,
            },
        ),
        (
            {"feedback_type": "wandb.runnable.my-scorer"},
            _NUMERIC_BUCKET_SQL.format(
                idx="pb_5", filter_clause="\n        AND feedback_type = {pb_4:String}"
            ),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": "wandb.runnable.my-scorer",
                "pb_5": 21600,
            },
        ),
        (
            {"trigger_ref": "weave:///entity/project/op/my-op:v1"},
            _NUMERIC_BUCKET_SQL.format(
                idx="pb_5", filter_clause="\n        AND trigger_ref = {pb_4:String}"
            ),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": "weave:///entity/project/op/my-op:v1",
                "pb_5": 21600,
            },
        ),
        (
            {"trigger_ref": "weave:///entity/project/op/my-op:*"},
            _NUMERIC_BUCKET_SQL.format(
                idx="pb_5",
                filter_clause="\n        AND startsWith(trigger_ref, {pb_4:String})",
            ),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": "weave:///entity/project/op/my-op",  # trailing :* stripped
                "pb_5": 21600,
            },
        ),
        (
            {"metrics": [_BOOLEAN_METRIC]},  # boolean swaps projection + extraction
            _BOOLEAN_BUCKET_SQL,
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": 21600,
            },
        ),
    ],
)
def test_build_feedback_stats_query_sql(req_kwargs, expected_sql, expected_params):
    req = _make_req(**req_kwargs)
    pb = _make_pb()
    result = build_feedback_stats_query(req, pb)
    _assert_sql_equal(result.sql, expected_sql)
    assert pb.get_params() == expected_params


def test_build_feedback_stats_query_metadata():
    pb = _make_pb()
    result = build_feedback_stats_query(_make_req(), pb)
    assert result.columns == [
        "timestamp",
        "avg_output_score",
        "max_output_score",
        "p5_output_score",
        "p95_output_score",
        "count",
    ]
    assert result.start == _START
    assert result.end == _END

    multi = build_feedback_stats_query(
        _make_req(
            metrics=[
                FeedbackMetricSpec(
                    json_path="score",
                    value_type="numeric",
                    aggregations=[AggregationType.AVG],
                ),
                FeedbackMetricSpec(
                    json_path="passed",
                    value_type="boolean",
                    aggregations=[AggregationType.COUNT_TRUE],
                ),
            ]
        ),
        _make_pb(),
    )
    assert "avg_score" in multi.columns
    assert "count_true_passed" in multi.columns


@pytest.mark.parametrize(
    ("granularity", "predicate"),
    [
        (1800, lambda g: g == 1800),  # explicit value honored
        (None, lambda g: g > 0),  # auto-selected positive
    ],
)
def test_build_feedback_stats_query_granularity(granularity, predicate):
    pb = _make_pb()
    result = build_feedback_stats_query(_make_req(granularity=granularity), pb)
    assert predicate(result.granularity_seconds)


# ---------------------------------------------------------------------------
# build_feedback_stats_window_query
# ---------------------------------------------------------------------------


_WINDOW_SQL = """
SELECT avgOrNull(m_output_score) AS avg_output_score,
       maxOrNull(m_output_score) AS max_output_score,
       quantileOrNull(0.05)(m_output_score) AS p5_output_score,
       quantileOrNull(0.95)(m_output_score) AS p95_output_score
FROM
  (SELECT toFloat64OrNull(JSONExtractRaw(payload_dump, 'output', 'score')) AS m_output_score
   FROM feedback
   WHERE project_id = {{pb_0:String}}
     AND created_at >= toDateTime({{pb_1:Float64}}, {{pb_3:String}})
     AND created_at < toDateTime({{pb_2:Float64}}, {{pb_3:String}}){filter_clause} )
"""


@pytest.mark.parametrize(
    ("req_kwargs", "expected_sql", "expected_params"),
    [
        (
            {},
            _WINDOW_SQL.format(filter_clause=""),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
            },
        ),
        (
            {"feedback_type": "wandb.runnable.scorer", "trigger_ref": "ref:v1"},
            _WINDOW_SQL.format(
                filter_clause="\n     AND feedback_type = {pb_4:String}"
                "\n     AND trigger_ref = {pb_5:String}"
            ),
            {
                "pb_0": "entity/project",
                "pb_1": 1704067200.0,
                "pb_2": 1704153600.0,
                "pb_3": "UTC",
                "pb_4": "wandb.runnable.scorer",
                "pb_5": "ref:v1",
            },
        ),
    ],
)
def test_build_window_query_sql(req_kwargs, expected_sql, expected_params):
    req = _make_req(**req_kwargs)
    pb = _make_pb()
    result = build_feedback_stats_window_query(req, pb)
    assert result is not None
    _assert_sql_equal(result.sql, expected_sql)
    assert pb.get_params() == expected_params
    assert result.columns == [
        "avg_output_score",
        "max_output_score",
        "p5_output_score",
        "p95_output_score",
    ]


def test_window_query_returns_none_for_empty_metrics():
    pb = _make_pb()
    assert build_feedback_stats_window_query(_make_req(metrics=[]), pb) is None


# ---------------------------------------------------------------------------
# _parse_window_stat_col (the count_true/count_false bug fix)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("avg_output_score", ("avg", "output_score")),
        ("sum_output_score", ("sum", "output_score")),
        ("min_output_score", ("min", "output_score")),
        ("max_output_score", ("max", "output_score")),
        ("count_output_score", ("count", "output_score")),
        # count_true/count_false are the regression anchors: split("_", 1) was the bug
        ("count_true_output_score", ("count_true", "output_score")),
        ("count_false_output_score", ("count_false", "output_score")),
        ("p95_output_score", ("p95", "output_score")),
        ("p5_output_score", ("p5", "output_score")),
        ("avg_output_quality_score", ("avg", "output_quality_score")),
        ("count_true_output_quality_score", ("count_true", "output_quality_score")),
        ("unknown_col", None),
        ("timestamp", None),
        ("count", None),  # no slug portion
    ],
)
def test_parse_window_stat_col(column, expected):
    assert _parse_window_stat_col(column) == expected


# ---------------------------------------------------------------------------
# FeedbackMetricSpec validation (typed aggregations)
# ---------------------------------------------------------------------------


def test_feedback_metric_spec():
    explicit = FeedbackMetricSpec(
        json_path="score",
        aggregations=[AggregationType.AVG, AggregationType.MAX],
    )
    assert explicit.aggregations == [AggregationType.AVG, AggregationType.MAX]

    default = FeedbackMetricSpec(json_path="score")
    assert len(default.aggregations) > 0
    assert all(isinstance(a, AggregationType) for a in default.aggregations)

    with_pcts = FeedbackMetricSpec(json_path="score", percentiles=[5, 50, 95])
    assert with_pcts.percentiles == [5, 50, 95]


def test_invalid_aggregation_string_rejected():
    with pytest.raises(ValueError, match="average"):
        FeedbackMetricSpec.model_validate(
            {"json_path": "score", "aggregations": ["average"]}
        )


# ---------------------------------------------------------------------------
# _extract_window_stats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cols", "row", "expected"),
    [
        (["avg_output_score"], (0.5,), {"output_score": {"avg": 0.5}}),
        (
            ["avg_output_score", "max_output_score", "p95_output_score"],
            (0.5, 1.0, 0.95),
            {"output_score": {"avg": 0.5, "max": 1.0, "p95": 0.95}},
        ),
        (
            ["avg_score", "avg_quality"],
            (0.5, 0.8),
            {"score": {"avg": 0.5}, "quality": {"avg": 0.8}},
        ),
        (["avg_output_score"], (None,), {"output_score": {"avg": None}}),  # None kept
        (["unknown_col"], (1.0,), {}),  # unknown column skipped
        (["avg_score", "max_score"], (0.5,), {"score": {"avg": 0.5}}),  # row < cols
        ([], (), {}),  # empty
        (
            ["count_true_passed", "count_false_passed"],
            (10, 5),
            {"passed": {"count_true": 10.0, "count_false": 5.0}},  # float-coerced
        ),
    ],
)
def test_extract_window_stats(cols, row, expected):
    assert _extract_window_stats(cols, row) == expected


# ---------------------------------------------------------------------------
# feedback_stats (methods module, mocked server)
# ---------------------------------------------------------------------------


def test_feedback_stats_empty_metrics_returns_empty_buckets():
    server = _make_mock_server()
    res = feedback_stats(server, _make_req(metrics=[]))
    assert res.buckets == []
    assert res.start == _START
    assert res.granularity == 3600
    server._query.assert_not_called()


def test_feedback_stats_calls_server_and_returns_buckets():
    ts = datetime.datetime(2024, 1, 1, 6, 0, tzinfo=datetime.timezone.utc)
    server = _make_mock_server(bucket_rows=[(ts, 0.75, 1.0, 0.1, 0.95, 5)])
    res = feedback_stats(server, _make_req())
    assert len(res.buckets) == 1
    assert res.buckets[0]["avg_output_score"] == 0.75
    assert res.granularity > 0
    assert server._query.call_count >= 1


@pytest.mark.parametrize(
    ("window_rows", "expects_window_stats"),
    [([(0.6, 1.0, 0.05, 0.98)], True), ([], False)],
)
def test_feedback_stats_window_stats(window_rows, expects_window_stats):
    bucket_rows = [(_START, 0.5, 1.0, 0.1, 0.9, 10)]
    server = _make_mock_server(bucket_rows=bucket_rows, window_rows=window_rows)
    res = feedback_stats(server, _make_req())
    if expects_window_stats:
        assert res.window_stats is not None
        assert res.window_stats["output_score"]["avg"] == 0.6
    else:
        assert res.window_stats is None


@pytest.mark.parametrize(
    ("req_kwargs", "expected_timezone"),
    [
        ({"timezone": "America/New_York"}, "America/New_York"),
        ({}, "UTC"),  # defaults to UTC
    ],
)
def test_feedback_stats_timezone(req_kwargs, expected_timezone):
    server = _make_mock_server()
    res = feedback_stats(server, _make_req(metrics=[], **req_kwargs))
    assert res.timezone == expected_timezone


# ---------------------------------------------------------------------------
# feedback_payload_schema (methods module, mocked server)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result_rows", "expected_subset", "expected_len"),
    [
        (
            [('{"output": {"score": 0.9}}',), ('{"label": "good"}',)],
            {"output.score": "numeric", "label": "categorical"},
            2,
        ),
        ([], {}, 0),
        ([(None,), ("",), ('{"x": 1}',)], {"x": "numeric"}, 1),  # null/empty skipped
    ],
)
def test_feedback_payload_schema(result_rows, expected_subset, expected_len):
    server = MagicMock()
    result = MagicMock()
    result.result_rows = result_rows
    server._query.return_value = result
    req = FeedbackPayloadSchemaReq(project_id="entity/project", start=_START, end=_END)
    res = feedback_payload_schema(server, req)
    path_map = {p.json_path: p.value_type for p in res.paths}
    for path, value_type in expected_subset.items():
        assert path_map[path] == value_type
    assert len(res.paths) == expected_len


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pb() -> ParamBuilder:
    return ParamBuilder(prefix="pb")


def _normalize_sql(sql: str) -> str:
    return "\n".join(
        line.rstrip() for line in textwrap.dedent(sql).strip().splitlines()
    )


def _assert_sql_equal(actual: str, expected: str) -> None:
    assert _normalize_sql(actual) == _normalize_sql(expected)


def _make_req(**kwargs) -> FeedbackStatsReq:
    defaults: dict = {
        "project_id": "entity/project",
        "start": _START,
        "end": _END,
        "metrics": [
            FeedbackMetricSpec(
                json_path="output.score",
                value_type="numeric",
                aggregations=[AggregationType.AVG, AggregationType.MAX],
                percentiles=[5, 95],
            )
        ],
    }
    defaults.update(kwargs)
    return FeedbackStatsReq(**defaults)


def _make_mock_server(
    bucket_rows: list[tuple] | None = None,
    window_rows: list[tuple] | None = None,
) -> MagicMock:
    """Mock ClickHouseTraceServer returning canned bucket then window results."""
    server = MagicMock()
    call_count = 0

    def _query_side_effect(sql: str, parameters: dict) -> MagicMock:
        nonlocal call_count
        result = MagicMock()
        result.result_rows = (
            (bucket_rows or []) if call_count == 0 else (window_rows or [])
        )
        call_count += 1
        return result

    server._query.side_effect = _query_side_effect
    return server
