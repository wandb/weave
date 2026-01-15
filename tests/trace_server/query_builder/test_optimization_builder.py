from weave.trace_server.calls_query_builder.calls_query_builder import Condition
from weave.trace_server.calls_query_builder.optimization_builder import (
    process_query_to_optimization_sql,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable


def test_condition_is_heavy_calls_complete() -> None:
    """Ensure heavy-field detection works for calls_complete."""
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

    assert heavy_condition.is_heavy(ReadTable.CALLS_COMPLETE) is True
    assert light_condition.is_heavy(ReadTable.CALLS_COMPLETE) is False


def test_optimization_skips_sortable_datetime_calls_complete() -> None:
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
