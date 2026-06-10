"""Tests for the feedback aggregate query builder."""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from weave.trace_server.feedback_agg_query_builder import (
    _any_prefix_clause,
    _build_where_sql,
    _object_id_match_clause,
    _ref_object_id_sql,
    build_feedback_aggregate_query,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    DAY_IN_MS,
    FEEDBACK_AGGREGATE_GROUP_BY_COLUMNS,
    FeedbackAggregateReq,
)

# 2024-01-01 and 2024-01-02 UTC, in unix epoch ms (a 1-day window).
_AFTER_MS = 1704067200000
_BEFORE_MS = 1704153600000
_BUCKET_SECONDS = 21600


def _make_pb() -> ParamBuilder:
    return ParamBuilder(prefix="pb")


def _normalize_sql(sql: str) -> str:
    return "\n".join(
        line.rstrip() for line in textwrap.dedent(sql).strip().splitlines()
    )


def _make_req(**kwargs) -> FeedbackAggregateReq:
    defaults: dict = {
        "project_id": "entity/project",
        "after_ms": _AFTER_MS,
        "before_ms": _BEFORE_MS,
        "time_bucket_seconds": _BUCKET_SECONDS,
    }
    defaults.update(kwargs)
    return FeedbackAggregateReq(**defaults)


def test_build_feedback_aggregate_query():
    """Happy path: a grouped, tag-filtered request yields the expected SQL + params.

    Edge: with no group_by the dimension drops out of SELECT/GROUP BY and columns.
    """
    pb = _make_pb()
    result = build_feedback_aggregate_query(
        _make_req(group_by=["scorer_id"], tags=["nsfw"]), pb
    )
    # scorer_id is derived from runnable_ref's object id (no ref exposed).
    assert _normalize_sql(result.sql) == _normalize_sql(
        """
        SELECT toStartOfInterval(created_at, toIntervalSecond({pb_3:Int64}), 'UTC') AS bucket,
               splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1] AS scorer_id,
               sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags)) AS tag_counts,
               sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings)) AS rating_sums,
               sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings))) AS rating_counts,
               count() AS total_count,
               countIf(notEmpty(scorer_tags)
                       OR notEmpty(scorer_ratings)) AS scored_count
        FROM feedback
        WHERE project_id = {pb_0:String}
          AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})
          AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})
          AND hasAny(scorer_tags, {pb_4:Array(String)})
        GROUP BY bucket,
                 scorer_id
        ORDER BY bucket
        """
    )
    assert pb.get_params() == {
        "pb_0": "entity/project",
        "pb_1": _AFTER_MS,
        "pb_2": _BEFORE_MS,
        "pb_3": _BUCKET_SECONDS,
        "pb_4": ["nsfw"],
    }

    # Edge: with no group_by the dimension drops out of SELECT/GROUP BY/columns,
    # leaving just the bucket + aggregates.
    no_group = build_feedback_aggregate_query(_make_req(), _make_pb())
    assert _normalize_sql(no_group.sql) == _normalize_sql(
        """
        SELECT toStartOfInterval(created_at, toIntervalSecond({pb_3:Int64}), 'UTC') AS bucket,
               sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags)) AS tag_counts,
               sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings)) AS rating_sums,
               sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings))) AS rating_counts,
               count() AS total_count,
               countIf(notEmpty(scorer_tags)
                       OR notEmpty(scorer_ratings)) AS scored_count
        FROM feedback
        WHERE project_id = {pb_0:String}
          AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})
          AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})
        GROUP BY bucket
        ORDER BY bucket
        """
    )
    assert no_group.columns == [
        "bucket",
        "tag_counts",
        "rating_sums",
        "rating_counts",
        "total_count",
        "scored_count",
    ]

    # Edge: every allowlisted dimension lands in the SELECT, GROUP BY, and columns
    # in the same shape. Stored columns select as-is; scorer_id is derived from
    # runnable_ref's object id and aliased back to the dimension name.
    for col in sorted(FEEDBACK_AGGREGATE_GROUP_BY_COLUMNS):
        grouped = build_feedback_aggregate_query(_make_req(group_by=[col]), _make_pb())
        dim_select = (
            "splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1] AS scorer_id"
            if col == "scorer_id"
            else col
        )
        assert _normalize_sql(grouped.sql) == _normalize_sql(
            "SELECT toStartOfInterval(created_at, toIntervalSecond({pb_3:Int64}), 'UTC') AS bucket,\n"
            f"       {dim_select},\n"
            "       sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags)) AS tag_counts,\n"
            "       sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings)) AS rating_sums,\n"
            "       sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings))) AS rating_counts,\n"
            "       count() AS total_count,\n"
            "       countIf(notEmpty(scorer_tags)\n"
            "               OR notEmpty(scorer_ratings)) AS scored_count\n"
            "FROM feedback\n"
            "WHERE project_id = {pb_0:String}\n"
            "  AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})\n"
            "  AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})\n"
            "GROUP BY bucket,\n"
            f"         {col}\n"
            "ORDER BY bucket"
        )
        assert grouped.columns == [
            "bucket",
            col,
            "tag_counts",
            "rating_sums",
            "rating_counts",
            "total_count",
            "scored_count",
        ]

    # Edge: time_bucket_seconds=None drops the bucket entirely; group/order by the
    # dimensions instead.
    unbucketed = build_feedback_aggregate_query(
        _make_req(time_bucket_seconds=None, group_by=["scorer_id"]), _make_pb()
    )
    assert _normalize_sql(unbucketed.sql) == _normalize_sql(
        """
        SELECT splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1] AS scorer_id,
               sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags)) AS tag_counts,
               sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings)) AS rating_sums,
               sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings))) AS rating_counts,
               count() AS total_count,
               countIf(notEmpty(scorer_tags)
                       OR notEmpty(scorer_ratings)) AS scored_count
        FROM feedback
        WHERE project_id = {pb_0:String}
          AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})
          AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})
        GROUP BY scorer_id
        ORDER BY scorer_id
        """
    )
    assert unbucketed.columns == [
        "scorer_id",
        "tag_counts",
        "rating_sums",
        "rating_counts",
        "total_count",
        "scored_count",
    ]

    # Edge: no bucket and no group_by -> one global rollup, no GROUP BY / ORDER BY.
    global_rollup = build_feedback_aggregate_query(
        _make_req(time_bucket_seconds=None), _make_pb()
    )
    assert _normalize_sql(global_rollup.sql) == _normalize_sql(
        """
        SELECT sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags)) AS tag_counts,
               sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings)) AS rating_sums,
               sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings))) AS rating_counts,
               count() AS total_count,
               countIf(notEmpty(scorer_tags)
                       OR notEmpty(scorer_ratings)) AS scored_count
        FROM feedback
        WHERE project_id = {pb_0:String}
          AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})
          AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})
        """
    )
    assert global_rollup.columns == [
        "tag_counts",
        "rating_sums",
        "rating_counts",
        "total_count",
        "scored_count",
    ]


def test_ref_object_id_sql():
    """Extracts the object id: the last path segment's name, before any ':digest'."""
    assert _ref_object_id_sql("trigger_ref") == (
        "splitByChar(':', splitByChar('/', ifNull(trigger_ref, ''))[-1])[1]"
    )
    assert _ref_object_id_sql("runnable_ref") == (
        "splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1]"
    )


def test_object_id_match_clause():
    """Exact match by default; a trailing '*' opts into prefix match.

    Both forms reuse the same object-id expression (digest stripped).
    """
    object_id = "splitByChar(':', splitByChar('/', ifNull(trigger_ref, ''))[-1])[1]"

    pb = _make_pb()
    exact = _object_id_match_clause("trigger_ref", ["mon"], pb)
    assert exact == f"({object_id} = {{pb_0:String}})"
    assert pb.get_params() == {"pb_0": "mon"}

    pb = _make_pb()
    prefix = _object_id_match_clause("trigger_ref", ["mon*"], pb)
    assert prefix == f"(startsWith({object_id}, {{pb_0:String}}))"
    assert pb.get_params() == {"pb_0": "mon"}  # '*' stripped before binding

    # Multiple values OR together, mixing exact and prefix.
    pb = _make_pb()
    mixed = _object_id_match_clause("trigger_ref", ["a", "b*"], pb)
    assert mixed == (
        f"({object_id} = {{pb_0:String}} OR startsWith({object_id}, {{pb_1:String}}))"
    )
    assert pb.get_params() == {"pb_0": "a", "pb_1": "b"}


def test_any_prefix_clause():
    """Happy path: values are OR'd as startsWith checks.

    Edge: a trailing '*' decoration is stripped from each value before binding.
    """
    pb = _make_pb()
    clause = _any_prefix_clause("feedback_type", ["wandb.runnable.*", "custom"], pb)
    assert clause == (
        "(startsWith(feedback_type, {pb_0:String})"
        " OR startsWith(feedback_type, {pb_1:String}))"
    )
    assert pb.get_params() == {"pb_0": "wandb.runnable.", "pb_1": "custom"}


def test_build_where_sql():
    """Happy path: each typed filter contributes a clause.

    Edges: with no filters only project + time bounds remain; rating bounds emit a
    guarded _rating_ lookup only when set (defaults are None).
    """
    pb = _make_pb()
    project = pb.add_param("entity/project")
    after = pb.add_param(_AFTER_MS)
    before = pb.add_param(_BEFORE_MS)
    where = _build_where_sql(
        _make_req(
            feedback_types=["wandb.agent_monitor"],
            monitor_ids=["mon"],
            scorer_ids=["sc"],
            span_agent_names=["agent_a"],
            span_types=["agent_turn"],
            tags=["nsfw"],
            rating_min=0.5,
            rating_max=0.9,
        ),
        project,
        after,
        before,
        pb,
    )
    assert where == (
        "project_id = {pb_0:String}"
        " AND created_at >= fromUnixTimestamp64Milli({pb_1:Int64})"
        " AND created_at < fromUnixTimestamp64Milli({pb_2:Int64})"
        " AND (startsWith(feedback_type, {pb_3:String}))"
        " AND (splitByChar(':', splitByChar('/', ifNull(trigger_ref, ''))[-1])[1] = {pb_4:String})"
        " AND (splitByChar(':', splitByChar('/', ifNull(runnable_ref, ''))[-1])[1] = {pb_5:String})"
        " AND span_agent_name IN {pb_6:Array(String)}"
        " AND (splitByChar('/', weave_ref)[-2] = {pb_7:String})"
        " AND hasAny(scorer_tags, {pb_8:Array(String)})"
        " AND mapContains(scorer_ratings, {pb_9:String})"
        " AND scorer_ratings[{pb_9:String}] >= {pb_10:Float64}"
        " AND scorer_ratings[{pb_9:String}] <= {pb_11:Float64}"
    )
    assert pb.get_params() == {
        "pb_0": "entity/project",
        "pb_1": _AFTER_MS,
        "pb_2": _BEFORE_MS,
        "pb_3": "wandb.agent_monitor",
        "pb_4": "mon",
        "pb_5": "sc",
        "pb_6": ["agent_a"],
        "pb_7": "agent_turn",
        "pb_8": ["nsfw"],
        "pb_9": "_rating_",
        "pb_10": 0.5,
        "pb_11": 0.9,
    }

    # Edge: no filters -> just the project + time-range bounds.
    bare = _build_where_sql(_make_req(), project, after, before, _make_pb())
    assert bare == (
        f"project_id = {{{project}:String}}"
        f" AND created_at >= fromUnixTimestamp64Milli({{{after}:Int64}})"
        f" AND created_at < fromUnixTimestamp64Milli({{{before}:Int64}})"
    )

    # Edge: rating bounds default to None -> no rating clause emitted.
    no_rating = _build_where_sql(_make_req(), project, after, before, _make_pb())
    assert "scorer_ratings" not in no_rating


def test_feedback_aggregate_req_validation():
    """The request model validates the window, bucket count, and group_by allowlist."""
    # Happy path: a sane request constructs cleanly.
    assert _make_req().time_bucket_seconds == _BUCKET_SECONDS

    # before_ms must be strictly after after_ms.
    with pytest.raises(ValidationError):
        _make_req(before_ms=_AFTER_MS)

    # Range cannot exceed the 31-day cap (this request buckets, so it stays capped).
    with pytest.raises(ValidationError):
        _make_req(after_ms=0, before_ms=DAY_IN_MS * 32, time_bucket_seconds=86_400)

    # All-time total: a bare project-wide rollup (no bucket, no group_by, no
    # filters) lifts the 31-day cap, so the client can request from the epoch.
    assert (
        _make_req(
            after_ms=0, before_ms=DAY_IN_MS * 365, time_bucket_seconds=None
        ).after_ms
        == 0
    )

    # The exemption is only for that bare total. Over the cap, the request is
    # rejected if it adds a group_by, a time bucket, or any filter.
    over_cap = {"after_ms": 0, "before_ms": DAY_IN_MS * 365}
    for disqualifier in (
        {"time_bucket_seconds": None, "group_by": ["scorer_id"]},
        {"time_bucket_seconds": 3600},
        {"time_bucket_seconds": None, "feedback_types": ["wandb.agent_monitor"]},
        {"time_bucket_seconds": None, "tags": ["nsfw"]},
        {"time_bucket_seconds": None, "scorer_ids": ["sc"]},
        {"time_bucket_seconds": None, "rating_min": 0.5},
    ):
        with pytest.raises(ValidationError):
            _make_req(**over_cap, **disqualifier)

    # Bucket count is capped (1 day at 1s buckets = 86,400 buckets).
    with pytest.raises(ValidationError):
        _make_req(time_bucket_seconds=1)

    # time_bucket_seconds is optional; None aggregates over the whole range and
    # skips the bucket-count cap (which the 1s window above would otherwise trip).
    assert _make_req(time_bucket_seconds=None).time_bucket_seconds is None

    # A positive bucket is still required when present (gt=0).
    with pytest.raises(ValidationError):
        _make_req(time_bucket_seconds=0)

    # group_by is an allowlist; unknown columns are rejected.
    with pytest.raises(ValidationError):
        _make_req(group_by=["payload_dump"])
