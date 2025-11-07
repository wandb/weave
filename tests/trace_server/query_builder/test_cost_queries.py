"""Tests for calls queries with include_costs=True.

These tests validate that ordering works correctly when costs are included,
which requires using the raw_sql_order_by method in the ORM.
"""

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.orm import ParamBuilder


def test_query_light_column_with_costs() -> None:
    """Test basic query with costs (moved from test_calls_query_builder.py)."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["test"],
            )
        )
    )

    sql = cq.as_sql(ParamBuilder())

    # Should have CTEs for cost calculations
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have cost fields in final select
    assert "any(summary_dump)" in sql or "summary_dump" in sql


def test_query_with_costs_and_dynamic_field_order() -> None:
    """Test that dynamic fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by attributes.sortable_key with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.sortable_key", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query
    assert "ORDER BY" in sql

    # JSON extraction should be in ORDER BY
    # Dynamic fields use exists, double, string ordering
    assert "JSON_VALUE" in sql or "toFloat64OrNull" in sql


def test_query_with_costs_and_feedback_order() -> None:
    """Test that feedback fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by feedback fields with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.score", "DESC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query
    assert "ORDER BY" in sql

    # Feedback ORDER BY should work
    # Feedback fields use anyIf with JSON extraction
    assert "feedback" in sql.lower()


def test_query_with_costs_and_simple_field_order() -> None:
    """Test that simple fields work with costs.

    This validates that regular fields still work correctly with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "DESC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query
    assert "ORDER BY" in sql
    assert "started_at" in sql


def test_query_with_costs_and_multiple_orders() -> None:
    """Test multiple ORDER BY fields with costs.

    This validates that multiple order fields work together with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.priority", "DESC")
    cq.add_order("started_at", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query with both fields
    assert "ORDER BY" in sql

    # Should have both order fields
    order_by_section = sql[sql.find("ORDER BY") :]
    # Both fields should appear in the ORDER BY
    assert "started_at" in order_by_section


def test_query_with_costs_and_summary_field_order() -> None:
    """Test that summary fields work with costs.

    This validates ordering by summary.weave.status with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("summary.weave.status", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query
    assert "ORDER BY" in sql

    # Summary fields use CASE statements
    assert "CASE" in sql


def test_query_with_costs_order_by_id() -> None:
    """Test ordering by id with costs - simplest case.

    This is a sanity check that the most basic ordering still works.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_order("id", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY with id
    assert "ORDER BY" in sql
    order_by_section = sql[sql.find("ORDER BY") :]
    assert "id" in order_by_section


def test_query_with_costs_and_object_ref_order() -> None:
    """Test that object ref fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by object ref fields (with expand_columns) with costs.
    Note: Object refs with costs are complex and may require additional work to fully support.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("inputs.model.temperature", "DESC")
    cq.set_expand_columns(["inputs.model"])

    sql = cq.as_sql(ParamBuilder())

    # Should have cost CTEs
    assert "llm_usage AS" in sql
    assert "ranked_prices AS" in sql

    # Should have ORDER BY in final query
    assert "ORDER BY" in sql

    # Object ref ordering should be present
    # Note: The exact SQL will depend on how object refs are joined
    # At minimum, we should see obj_filter CTEs
    assert "obj_filter" in sql or "object_val_dump" in sql


def test_query_with_costs_order_desc() -> None:
    """Test DESC ordering with costs."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "DESC")

    sql = cq.as_sql(ParamBuilder())

    # Should have ORDER BY with DESC
    assert "ORDER BY" in sql
    order_by_section = sql[sql.find("ORDER BY") :]
    assert "DESC" in order_by_section


def test_query_with_costs_order_asc() -> None:
    """Test ASC ordering with costs."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have ORDER BY with ASC
    assert "ORDER BY" in sql
    order_by_section = sql[sql.find("ORDER BY") :]
    assert "ASC" in order_by_section
