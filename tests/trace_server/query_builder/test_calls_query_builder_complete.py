"""Tests for calls query builder with calls_complete and call_starts tables."""

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.project_version.types import ProjectVersion


def test_calls_complete_baseline() -> None:
    """Test basic query against calls_complete table without running calls."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
        include_running=False,  # Don't include running calls for simple query
    )
    cq.add_field("id")
    # For calls_complete, we should not need grouping
    assert_sql(
        cq,
        """
        SELECT calls_complete.id AS id
        FROM calls_complete
        WHERE calls_complete.project_id = {pb_0:String}
        """,
        {"pb_0": "project"},
    )


def test_calls_complete_with_light_fields() -> None:
    """Test query with light fields that don't need grouping."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
        include_running=False,  # Don't include running calls for simple query
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_field("ended_at")
    cq.add_field("op_name")
    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at,
            calls_complete.ended_at AS ended_at,
            calls_complete.op_name AS op_name
        FROM calls_complete
        WHERE calls_complete.project_id = {pb_0:String}
        """,
        {"pb_0": "project"},
    )


def test_calls_complete_with_heavy_fields_and_filter() -> None:
    """Test query with heavy fields and filters - should use CTE optimization."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
        include_running=False,  # Don't include running calls
    )
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("started_at")
    cq.set_limit(50)
    cq.add_order("started_at", "DESC")

    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT calls_complete.id AS id
            FROM calls_complete
            WHERE calls_complete.project_id = {pb_0:String}
            ORDER BY calls_complete.started_at DESC
            LIMIT 50
        )
        SELECT
            calls_complete.id AS id,
            calls_complete.inputs_dump AS inputs_dump,
            calls_complete.started_at AS started_at
        FROM calls_complete
        WHERE calls_complete.id IN (SELECT id FROM filtered_calls)
        ORDER BY calls_complete.started_at DESC
        LIMIT 50
        """,
        {"pb_0": "project"},
    )


def test_call_starts_with_include_running_baseline() -> None:
    """Test basic query that includes running calls (join with call_starts)."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.set_limit(50)
    cq.add_order("started_at", "DESC")
    # By default, include_running should be True

    # Expected: CTE with union of calls_complete and call_starts
    assert_sql(
        cq,
        """
        WITH complete AS (
            SELECT calls_complete.id AS id
            FROM calls_complete
            WHERE calls_complete.project_id = {pb_0:String}
            ORDER BY calls_complete.started_at DESC
            LIMIT 50
        ),
        starts_only AS (
            SELECT call_starts.id AS id
            FROM call_starts
            WHERE call_starts.project_id = {pb_0:String}
            AND call_starts.id NOT IN (SELECT id FROM calls_complete WHERE project_id = {pb_0:String})                                                      
            ORDER BY call_starts.started_at DESC
            LIMIT 50
        )
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at
        FROM calls_complete
        WHERE calls_complete.id IN (
            SELECT id FROM complete
            UNION ALL
            SELECT id FROM starts_only
        )
        ORDER BY calls_complete.started_at DESC
        LIMIT 50
        """,
        {"pb_0": "project"},
    )


def test_call_starts_with_include_running_false() -> None:
    """Test query that excludes running calls (only calls_complete)."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
        include_running=False,
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.set_limit(50)

    # Should only query calls_complete, no join with call_starts
    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at
        FROM calls_complete
        WHERE calls_complete.project_id = {pb_0:String}
        LIMIT 50
        """,
        {"pb_0": "project"},
    )


def test_call_starts_with_filters() -> None:
    """Test query with filters applied to both tables."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
    )
    cq.add_field("id")
    cq.add_field("op_name")
    cq.set_hardcoded_filter(
        HardCodedFilter(filter=tsi.CallsFilter(op_names=["predict", "score"]))
    )
    cq.set_limit(50)
    cq.add_order("started_at", "DESC")

    # Filters are applied to starts CTE, but not complete CTE when using optimization
    # because we want to push down only light filters to the ID selection
    assert_sql(
        cq,
        """
        WITH complete AS (
            SELECT calls_complete.id AS id
            FROM calls_complete
            WHERE calls_complete.project_id = {pb_0:String}
            ORDER BY calls_complete.started_at DESC
            LIMIT 50
        ),
        starts_only AS (
            SELECT call_starts.id AS id
            FROM call_starts
            WHERE call_starts.project_id = {pb_0:String}
            AND call_starts.id NOT IN (SELECT id FROM calls_complete WHERE project_id = {pb_0:String})                                                      
            AND call_starts.op_name IN {pb_1:Array(String)}
            ORDER BY call_starts.started_at DESC
            LIMIT 50
        )
        SELECT
            calls_complete.id AS id,
            calls_complete.op_name AS op_name
        FROM calls_complete
        WHERE calls_complete.id IN (
            SELECT id FROM complete
        UNION ALL
            SELECT id FROM starts_only
        )
        ORDER BY calls_complete.started_at DESC
        LIMIT 50
        """,
        {
            "pb_0": "project",
            "pb_1": ["predict", "score"],
        },
    )


def test_call_starts_with_heavy_fields() -> None:
    """Test query with heavy fields requiring optimization."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
    )
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("output")
    cq.set_limit(50)
    cq.add_order("started_at", "DESC")

    # With heavy fields, we should still use the CTE pattern
    # but the final select will pull the heavy fields
    assert_sql(
        cq,
        """
        WITH complete AS (
            SELECT calls_complete.id AS id
            FROM calls_complete
            WHERE calls_complete.project_id = {pb_0:String}
            ORDER BY calls_complete.started_at DESC
            LIMIT 50
        ),
        starts_only AS (
            SELECT call_starts.id AS id
            FROM call_starts
            WHERE call_starts.project_id = {pb_0:String}
            AND call_starts.id NOT IN (SELECT id FROM calls_complete WHERE project_id = {pb_0:String})                                                      
            ORDER BY call_starts.started_at DESC
            LIMIT 50
        )
        SELECT
            calls_complete.id AS id,
            calls_complete.inputs_dump AS inputs_dump,
            calls_complete.output_dump AS output_dump
        FROM calls_complete
        WHERE calls_complete.id IN (
            SELECT id FROM complete
            UNION ALL
            SELECT id FROM starts_only
        )
        ORDER BY calls_complete.started_at DESC
        LIMIT 50
        """,
        {"pb_0": "project"},
    )


def test_calls_complete_with_query_conditions() -> None:
    """Test query with query conditions."""
    cq = CallsQuery(
        project_id="project",
        project_version=ProjectVersion.CALLS_COMPLETE_VERSION,
        include_running=False,  # Don't include running calls for simple query
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {"$gt": [{"$getField": "started_at"}, {"$literal": 1749485184.848}]}
        )
    )
    cq.set_limit(50)

    # Query conditions should be applied in WHERE clause
    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at
        FROM calls_complete
        WHERE calls_complete.project_id = {pb_0:String}
        AND ((calls_complete.started_at > {pb_1:Float64}))
        LIMIT 50
        """,
        {"pb_0": "project", "pb_1": 1749485184.848},
    )
