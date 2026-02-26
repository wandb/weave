"""Tests for feedback stats and schema discovery."""

from __future__ import annotations

import datetime
import textwrap

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
from weave.trace_server.methods.feedback_stats import _parse_window_stat_col
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    AggregationType,
    FeedbackMetricSpec,
    FeedbackStatsReq,
)

# ---------------------------------------------------------------------------
# discover_payload_schema
# ---------------------------------------------------------------------------


class TestDiscoverPaths:
    def test_flat_dict(self):
        result = _discover_paths({"score": 0.9, "passed": True})
        assert "score" in result
        assert float in result["score"]
        assert "passed" in result
        assert bool in result["passed"]

    def test_nested_dict(self):
        result = _discover_paths({"output": {"score": 0.9}})
        assert "output.score" in result
        assert float in result["output.score"]

    def test_skips_keys_with_dot(self):
        result = _discover_paths({"a.b": 1})
        assert not result

    def test_skips_empty_key(self):
        result = _discover_paths({"": 1})
        assert not result

    def test_list_of_scalars(self):
        # A dict with a list-of-scalars value produces a path keyed by the field name
        result = _discover_paths({"scores": [0.1, 0.2]})
        assert "scores" in result
        assert float in result["scores"]

    def test_none_value(self):
        result = _discover_paths({"x": None})
        assert "x" in result
        assert type(None) in result["x"]


class TestInferValueType:
    def test_numeric(self):
        assert _infer_value_type({int, float}) == "numeric"
        assert _infer_value_type({int}) == "numeric"
        assert _infer_value_type({float, type(None)}) == "numeric"

    def test_boolean(self):
        assert _infer_value_type({bool}) == "boolean"
        assert _infer_value_type({bool, type(None)}) == "boolean"

    def test_categorical_when_mixed(self):
        assert _infer_value_type({str}) == "categorical"
        assert _infer_value_type({int, str}) == "categorical"

    def test_empty(self):
        # No types seen → default to numeric
        assert _infer_value_type(set()) == "numeric"

    def test_bool_not_confused_with_int(self):
        # bool is subclass of int; {bool} must resolve to "boolean", not "numeric"
        assert _infer_value_type({bool}) == "boolean"
        # Mixed bool+int → categorical (ambiguous)
        assert _infer_value_type({bool, int}) == "categorical"


class TestDiscoverPayloadSchema:
    def test_basic(self):
        paths = discover_payload_schema(['{"output": {"score": 0.9}}'])
        assert len(paths) == 1
        assert paths[0].json_path == "output.score"
        assert paths[0].value_type == "numeric"

    def test_boolean_field(self):
        paths = discover_payload_schema(['{"passed": true}'])
        assert paths[0].json_path == "passed"
        assert paths[0].value_type == "boolean"

    def test_multiple_payloads_merged(self):
        payloads = ['{"score": 1.0}', '{"score": 0.5, "label": "good"}']
        paths = discover_payload_schema(payloads)
        path_map = {p.json_path: p.value_type for p in paths}
        assert "score" in path_map
        assert path_map["score"] == "numeric"
        assert "label" in path_map
        assert path_map["label"] == "categorical"

    def test_skips_array_index_paths(self):
        paths = discover_payload_schema(['{"items": [1, 2, 3]}'])
        # Array-index paths like "items[0]" are filtered out
        for p in paths:
            assert "[" not in p.json_path

    def test_invalid_json_skipped(self):
        paths = discover_payload_schema(["not json", '{"score": 1.0}'])
        assert len(paths) == 1
        assert paths[0].json_path == "score"

    def test_empty_strings_skipped(self):
        paths = discover_payload_schema(["", "   ", '{"x": 1}'])
        assert len(paths) == 1

    def test_paths_sorted(self):
        payloads = ['{"z": 1, "a": 2, "m": 3}']
        paths = discover_payload_schema(payloads)
        names = [p.json_path for p in paths]
        assert names == sorted(names)

    def test_path_with_unsafe_chars_excluded(self):
        # Paths with spaces or special chars must be excluded
        paths = discover_payload_schema(['{"a b": 1, "c": 2}'])
        names = [p.json_path for p in paths]
        assert "a b" not in names
        assert "c" in names


# ---------------------------------------------------------------------------
# JSON path helpers
# ---------------------------------------------------------------------------


class TestJsonPathHelpers:
    def test_slug_replaces_dots(self):
        assert _json_path_to_metric_slug("output.score") == "output_score"

    def test_slug_single_key(self):
        assert _json_path_to_metric_slug("score") == "score"

    def test_extraction_numeric(self):
        sql = _json_path_to_extraction_sql("output.score", "numeric")
        assert (
            sql
            == "toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score'))"
        )

    def test_extraction_boolean(self):
        sql = _json_path_to_extraction_sql("passed", "boolean")
        assert (
            sql
            == "if(JSONExtractRaw(payload_dump, 'passed') = 'true', 1, if(JSONExtractRaw(payload_dump, 'passed') = 'false', 0, NULL))"
        )

    def test_extraction_categorical(self):
        sql = _json_path_to_extraction_sql("label", "categorical")
        assert sql == "JSONExtractString(payload_dump, 'label')"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError, match="json_path may only contain"):
            _json_path_to_metric_slug("output score")

    def test_empty_path_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _json_path_to_metric_slug("")


class TestJsonPathPattern:
    def test_valid(self):
        assert JSON_PATH_PATTERN.match("output.score")
        assert JSON_PATH_PATTERN.match("score")
        assert JSON_PATH_PATTERN.match("a_b.c_d")

    def test_invalid(self):
        assert not JSON_PATH_PATTERN.match("output score")
        assert not JSON_PATH_PATTERN.match("a[0]")
        assert not JSON_PATH_PATTERN.match("")


# ---------------------------------------------------------------------------
# trigger_ref_where_clause
# ---------------------------------------------------------------------------


class TestTriggerRefWhereClause:
    def test_exact_match(self):
        pb = _make_pb()
        sql = trigger_ref_where_clause("my-monitor:v1", pb)
        assert sql == "trigger_ref = {pb_0:String}"
        assert pb.get_params() == {"pb_0": "my-monitor:v1"}

    def test_prefix_match(self):
        pb = _make_pb()
        sql = trigger_ref_where_clause("my-monitor:*", pb)
        assert sql == "startsWith(trigger_ref, {pb_0:String})"
        assert pb.get_params() == {"pb_0": "my-monitor"}


# ---------------------------------------------------------------------------
# build_feedback_stats_query
# ---------------------------------------------------------------------------


_START = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
_END = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)


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


class TestBuildFeedbackStatsQuery:
    def test_returns_expected_bucket_query_sql(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        _assert_sql_equal(
            result.sql,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      avgOrNull(m_output_score) AS avg_output_score,
                      maxOrNull(m_output_score) AS max_output_score,
                      quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                      quantileOrNull(0.95)(m_output_score) AS p95_output_score,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(created_at, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
                         toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
                  FROM feedback
                  WHERE project_id = {pb_0:String}
                    AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                    AND created_at < toDateTime({pb_2:Float64}, {pb_3:String}) )
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
            """,
        )
        assert pb.get_params() == {
            "pb_0": "entity/project",
            "pb_1": 1704067200.0,
            "pb_2": 1704153600.0,
            "pb_3": "UTC",
            "pb_4": 21600,
        }

    def test_columns_include_timestamp_and_count(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert "timestamp" in result.columns
        assert "count" in result.columns

    def test_columns_include_agg_aliases(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert "avg_output_score" in result.columns
        assert "max_output_score" in result.columns
        assert "p5_output_score" in result.columns
        assert "p95_output_score" in result.columns

    def test_granularity_respected(self):
        req = _make_req(granularity=1800)
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert result.granularity_seconds == 1800

    def test_granularity_auto_selected_when_none(self):
        req = _make_req(granularity=None)
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert result.granularity_seconds > 0

    def test_feedback_type_filter_matches_expected_sql(self):
        req = _make_req(feedback_type="wandb.runnable.my-scorer")
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        _assert_sql_equal(
            result.sql,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_5:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_5:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      avgOrNull(m_output_score) AS avg_output_score,
                      maxOrNull(m_output_score) AS max_output_score,
                      quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                      quantileOrNull(0.95)(m_output_score) AS p95_output_score,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(created_at, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
                         toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
                  FROM feedback
                  WHERE project_id = {pb_0:String}
                    AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                    AND created_at < toDateTime({pb_2:Float64}, {pb_3:String})
                    AND feedback_type = {pb_4:String} )
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
            """,
        )
        assert pb.get_params()["pb_4"] == "wandb.runnable.my-scorer"

    def test_trigger_ref_exact_filter_matches_expected_sql(self):
        req = _make_req(trigger_ref="weave:///entity/project/op/my-op:v1")
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        _assert_sql_equal(
            result.sql,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_5:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_5:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      avgOrNull(m_output_score) AS avg_output_score,
                      maxOrNull(m_output_score) AS max_output_score,
                      quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                      quantileOrNull(0.95)(m_output_score) AS p95_output_score,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(created_at, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
                         toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
                  FROM feedback
                  WHERE project_id = {pb_0:String}
                    AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                    AND created_at < toDateTime({pb_2:Float64}, {pb_3:String})
                    AND trigger_ref = {pb_4:String} )
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
            """,
        )
        assert pb.get_params()["pb_4"] == "weave:///entity/project/op/my-op:v1"

    def test_trigger_ref_prefix_filter_matches_expected_sql(self):
        req = _make_req(trigger_ref="weave:///entity/project/op/my-op:*")
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        _assert_sql_equal(
            result.sql,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_5:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_5:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      avgOrNull(m_output_score) AS avg_output_score,
                      maxOrNull(m_output_score) AS max_output_score,
                      quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                      quantileOrNull(0.95)(m_output_score) AS p95_output_score,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(created_at, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
                         toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
                  FROM feedback
                  WHERE project_id = {pb_0:String}
                    AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                    AND created_at < toDateTime({pb_2:Float64}, {pb_3:String})
                    AND startsWith(trigger_ref, {pb_4:String}) )
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
            """,
        )
        assert pb.get_params()["pb_4"] == "weave:///entity/project/op/my-op"

    def test_start_and_end_resolved(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert result.start == _START
        assert result.end == _END

    def test_boolean_metric_matches_expected_sql(self):
        req = _make_req(
            metrics=[
                FeedbackMetricSpec(
                    json_path="passed",
                    value_type="boolean",
                    aggregations=[
                        AggregationType.COUNT_TRUE,
                        AggregationType.COUNT_FALSE,
                    ],
                )
            ]
        )
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert "count_true_passed" in result.columns
        assert "count_false_passed" in result.columns
        _assert_sql_equal(
            result.sql,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      countIf(m_passed = 1) AS count_true_passed,
                      countIf(m_passed = 0) AS count_false_passed,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(created_at, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
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
            """,
        )

    def test_multiple_metrics(self):
        req = _make_req(
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
        )
        pb = _make_pb()
        result = build_feedback_stats_query(req, pb)
        assert "avg_score" in result.columns
        assert "count_true_passed" in result.columns


# ---------------------------------------------------------------------------
# build_feedback_stats_window_query
# ---------------------------------------------------------------------------


class TestBuildFeedbackStatsWindowQuery:
    def test_returns_none_for_empty_metrics(self):
        req = _make_req(metrics=[])
        pb = _make_pb()
        assert build_feedback_stats_window_query(req, pb) is None

    def test_returns_result_with_columns(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_window_query(req, pb)
        assert result is not None
        assert "avg_output_score" in result.columns
        assert "max_output_score" in result.columns

    def test_window_query_matches_expected_sql(self):
        req = _make_req()
        pb = _make_pb()
        result = build_feedback_stats_window_query(req, pb)
        assert result is not None
        _assert_sql_equal(
            result.sql,
            """
            SELECT avgOrNull(m_output_score) AS avg_output_score,
                   maxOrNull(m_output_score) AS max_output_score,
                   quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                   quantileOrNull(0.95)(m_output_score) AS p95_output_score
            FROM
              (SELECT toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
               FROM feedback
               WHERE project_id = {pb_0:String}
                 AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                 AND created_at < toDateTime({pb_2:Float64}, {pb_3:String}) )
            """,
        )
        assert pb.get_params() == {
            "pb_0": "entity/project",
            "pb_1": 1704067200.0,
            "pb_2": 1704153600.0,
            "pb_3": "UTC",
        }

    def test_window_query_filters_match_expected_sql(self):
        req = _make_req(feedback_type="wandb.runnable.scorer", trigger_ref="ref:v1")
        pb = _make_pb()
        result = build_feedback_stats_window_query(req, pb)
        assert result is not None
        _assert_sql_equal(
            result.sql,
            """
            SELECT avgOrNull(m_output_score) AS avg_output_score,
                   maxOrNull(m_output_score) AS max_output_score,
                   quantileOrNull(0.05)(m_output_score) AS p5_output_score,
                   quantileOrNull(0.95)(m_output_score) AS p95_output_score
            FROM
              (SELECT toFloat64OrNull(JSONExtractRaw(JSONExtractRaw(payload_dump, 'output'), 'score')) AS m_output_score
               FROM feedback
               WHERE project_id = {pb_0:String}
                 AND created_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                 AND created_at < toDateTime({pb_2:Float64}, {pb_3:String})
                 AND feedback_type = {pb_4:String}
                 AND trigger_ref = {pb_5:String} )
            """,
        )
        assert pb.get_params() == {
            "pb_0": "entity/project",
            "pb_1": 1704067200.0,
            "pb_2": 1704153600.0,
            "pb_3": "UTC",
            "pb_4": "wandb.runnable.scorer",
            "pb_5": "ref:v1",
        }


# ---------------------------------------------------------------------------
# _parse_window_stat_col (the count_true/count_false bug fix)
# ---------------------------------------------------------------------------


class TestParseWindowStatCol:
    def test_avg(self):
        assert _parse_window_stat_col("avg_output_score") == ("avg", "output_score")

    def test_sum(self):
        assert _parse_window_stat_col("sum_output_score") == ("sum", "output_score")

    def test_min(self):
        assert _parse_window_stat_col("min_output_score") == ("min", "output_score")

    def test_max(self):
        assert _parse_window_stat_col("max_output_score") == ("max", "output_score")

    def test_count(self):
        assert _parse_window_stat_col("count_output_score") == ("count", "output_score")

    def test_count_true_multi_word_prefix(self):
        # This was the bug: split("_", 1) gave ("count", "true_output_score")
        assert _parse_window_stat_col("count_true_output_score") == (
            "count_true",
            "output_score",
        )

    def test_count_false_multi_word_prefix(self):
        assert _parse_window_stat_col("count_false_output_score") == (
            "count_false",
            "output_score",
        )

    def test_percentile_p95(self):
        assert _parse_window_stat_col("p95_output_score") == ("p95", "output_score")

    def test_percentile_p5(self):
        assert _parse_window_stat_col("p5_output_score") == ("p5", "output_score")

    def test_slug_with_underscores(self):
        # Metric slugs can contain underscores (converted from dot paths)
        assert _parse_window_stat_col("avg_output_quality_score") == (
            "avg",
            "output_quality_score",
        )

    def test_count_true_slug_with_underscores(self):
        assert _parse_window_stat_col("count_true_output_quality_score") == (
            "count_true",
            "output_quality_score",
        )

    def test_unknown_returns_none(self):
        assert _parse_window_stat_col("unknown_col") is None
        assert _parse_window_stat_col("timestamp") is None
        assert _parse_window_stat_col("count") is None  # no slug portion


# ---------------------------------------------------------------------------
# FeedbackMetricSpec validation (typed aggregations)
# ---------------------------------------------------------------------------


class TestFeedbackMetricSpec:
    def test_valid_aggregation_type(self):
        spec = FeedbackMetricSpec(
            json_path="score",
            aggregations=[AggregationType.AVG, AggregationType.MAX],
        )
        assert spec.aggregations == [AggregationType.AVG, AggregationType.MAX]

    def test_invalid_aggregation_string_rejected(self):
        with pytest.raises(ValueError):
            FeedbackMetricSpec(json_path="score", aggregations=["average"])  # type: ignore[list-item]

    def test_default_aggregations(self):
        spec = FeedbackMetricSpec(json_path="score")
        assert len(spec.aggregations) > 0
        assert all(isinstance(a, AggregationType) for a in spec.aggregations)

    def test_percentiles_accepted(self):
        spec = FeedbackMetricSpec(json_path="score", percentiles=[5, 50, 95])
        assert spec.percentiles == [5, 50, 95]
