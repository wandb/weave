import pytest

from weave.trace_server.calls_query_builder.calls_query_builder import Condition
from weave.trace_server.interface import query as tsi_query


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
