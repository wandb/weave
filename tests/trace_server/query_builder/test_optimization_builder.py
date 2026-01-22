import pytest

from weave.trace_server.calls_query_builder.calls_query_builder import (
    Condition,
    get_calls_stats_table_name_from_alias,
)
from weave.trace_server.calls_query_builder.optimization_builder import (
    process_query_to_optimization_sql,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable


@pytest.mark.parametrize("table_alias", ["calls_merged", "calls_complete"])
def test_condition_is_heavy(table_alias: str) -> None:
    """Ensure heavy-field detection works for both table types."""
    heavy_condition = Condition(
        operand=tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.param.val"},
                    {"$literal": "hello"},
                ]
            }
        )
    )
    light_condition = Condition(
        operand=tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "wb_user_id"},
                    {"$literal": "user-123"},
                ]
            }
        )
    )

    assert heavy_condition.is_heavy(table_alias) is True
    assert light_condition.is_heavy(table_alias) is False


def test_optimization_skips_sortable_datetime_for_calls_complete() -> None:
    """Ensure sortable_datetime optimizations are skipped for calls_complete."""
    condition = Condition(
        operand=tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": 1709251200},
                ]
            }
        )
    )
    pb = ParamBuilder("pb")
    result = process_query_to_optimization_sql(
        [condition],
        pb,
        "calls_complete",
        ReadTable.CALLS_COMPLETE,
    )

    assert result.sortable_datetime_filters_sql is None


def test_optimization_includes_sortable_datetime_for_calls_merged() -> None:
    """Ensure sortable_datetime optimizations are applied for calls_merged."""
    condition = Condition(
        operand=tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": 1709251200},
                ]
            }
        )
    )
    pb = ParamBuilder("pb")
    result = process_query_to_optimization_sql(
        [condition],
        pb,
        "calls_merged",
        ReadTable.CALLS_MERGED,
    )

    assert result.sortable_datetime_filters_sql is not None


@pytest.mark.parametrize(
    ("table_alias", "expected_stats_table"),
    [
        ("calls_merged", "calls_merged_stats"),
        ("calls_complete", "calls_complete_stats"),
    ],
)
def test_get_calls_stats_table_name_from_alias(
    table_alias: str, expected_stats_table: str
) -> None:
    """Ensure stats table name is correctly derived from table alias."""
    assert get_calls_stats_table_name_from_alias(table_alias) == expected_stats_table
