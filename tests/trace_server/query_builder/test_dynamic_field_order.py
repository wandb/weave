"""Test ordering by dynamic fields with extra paths."""

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    get_field_by_name,
)
from weave.trace_server.orm import ParamBuilder


def test_dynamic_field_has_extra_path() -> None:
    """Verify that dynamic fields like attributes.sort_key have extra_path set."""
    field = get_field_by_name("attributes.sort_key")
    assert hasattr(field, "extra_path")
    assert field.extra_path == ["sort_key"]


def test_order_by_dynamic_field_without_costs() -> None:
    """Test ordering by a dynamic field (attributes.sort_key) without costs.

    This should work because the ORDER BY can use JSON extraction directly.
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_order("attributes.sort_key", "ASC")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["test"],
            )
        )
    )

    sql = cq.as_sql(ParamBuilder())

    # Should have JSON extraction in ORDER BY
    assert "JSON_VALUE" in sql or "toFloat64OrNull" in sql
    # attributes_dump itself is not selected (only used in ORDER BY)
    # Because it's an optimization query, attributes_dump should NOT be added to SELECT
    # (it has extra_path, so can't be selected)
    assert sql.count("attributes_dump AS attributes_dump") == 0


def test_order_by_dynamic_field_with_costs() -> None:
    """Test ordering by a dynamic field (attributes.sort_key) with costs.

    This should work because:
    1. attributes_dump (base field) is available in ranked_prices
    2. ORM handles JSON extraction in ORDER BY
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.sort_key", "ASC")

    sql = cq.as_sql(ParamBuilder())

    # Should have all_calls CTE
    assert "all_calls AS" in sql

    # attributes_dump base field should be available via get_calls_merged_columns()
    # but attributes_dump with JSON path extraction should NOT be in SELECT
    # (it has extra_path, so our fix skips it)
    all_calls_section = sql.split("all_calls AS")[1].split("),")[0]
    # Should NOT have attributes_dump in SELECT (has extra_path)
    assert "attributes_dump AS attributes_dump" not in all_calls_section
