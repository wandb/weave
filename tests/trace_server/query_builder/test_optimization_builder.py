import pytest

from weave.trace_server.calls_query_builder.calls_query_builder import (
    Condition,
    ParamBuilder,
)
from weave.trace_server.calls_query_builder.optimization_builder import (
    HeavyFieldOptimizationProcessor,
    _maybe_use_null_check,
    apply_processor,
)
from weave.trace_server.calls_query_builder.utils import NotContext
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


class TestMaybeUseNullCheck:
    """Unit tests for _maybe_use_null_check helper."""

    def test_adds_null_check_outside_not(self) -> None:
        result = _maybe_use_null_check(
            "x LIKE '%y%'", "attributes_dump", "t", use_null_check=True
        )
        assert result == "(x LIKE '%y%' OR t.attributes_dump IS NULL)"

    def test_skips_optimization_inside_not(self) -> None:
        with NotContext.not_context():
            result = _maybe_use_null_check(
                "x LIKE '%y%'", "attributes_dump", "t", use_null_check=True
            )
        assert result is None

    def test_passes_through_when_null_check_disabled(self) -> None:
        result = _maybe_use_null_check(
            "x LIKE '%y%'", "attributes_dump", "t", use_null_check=False
        )
        assert result == "x LIKE '%y%'"

    def test_passes_through_for_non_nullable_field(self) -> None:
        result = _maybe_use_null_check(
            "x LIKE '%y%'", "op_name", "t", use_null_check=True
        )
        assert result == "x LIKE '%y%'"

    def test_nested_not_context(self) -> None:
        """AND nested inside NOT doesn't reset or alter the NOT depth."""
        and_body = {
            "$and": [
                {
                    "$eq": [
                        {"$getField": "attributes.key_a"},
                        {"$literal": "val_a"},
                    ]
                },
                {
                    "$eq": [
                        {"$getField": "attributes.key_b"},
                        {"$literal": "val_b"},
                    ]
                },
            ]
        }

        # Bare AND: optimization applies
        pb = ParamBuilder()
        processor = HeavyFieldOptimizationProcessor(
            pb, "calls_merged", use_null_check=True
        )
        op = tsi_query.AndOperation.model_validate(and_body)
        assert apply_processor(processor, op) is not None

        # NOT(AND(...)): single negation, optimization skipped
        pb = ParamBuilder()
        processor = HeavyFieldOptimizationProcessor(
            pb, "calls_merged", use_null_check=True
        )
        op = tsi_query.NotOperation.model_validate({"$not": [and_body]})  # type: ignore [assignment]
        assert apply_processor(processor, op) is None

        # NOT(NOT(AND(...))): double negation cancels, optimization applies
        pb = ParamBuilder()
        processor = HeavyFieldOptimizationProcessor(
            pb, "calls_merged", use_null_check=True
        )
        op = tsi_query.NotOperation.model_validate({"$not": [{"$not": [and_body]}]})  # type: ignore [assignment]
        assert apply_processor(processor, op) is not None

        # NOT(AND(NOT(eq_a), eq_b)): eq_b at depth=1 returns None, so AND
        # bails entirely rather than producing a too-restrictive pre-filter.
        pb = ParamBuilder()
        processor = HeavyFieldOptimizationProcessor(
            pb, "calls_merged", use_null_check=True
        )
        op = tsi_query.NotOperation.model_validate(  # type: ignore [assignment]
            {
                "$not": [
                    {
                        "$and": [
                            {
                                "$not": [
                                    {
                                        "$eq": [
                                            {"$getField": "attributes.a"},
                                            {"$literal": "x"},
                                        ]
                                    }
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "attributes.b"},
                                    {"$literal": "y"},
                                ]
                            },
                        ]
                    }
                ]
            }
        )
        # eq_b at depth=1 can't be optimized, and dropping it from the AND
        # would make the pre-filter too restrictive, so the whole thing bails.
        assert apply_processor(processor, op) is None


def test_heavy_field_eq_with_null_check() -> None:
    """Eq on a heavy start/end field adds OR IS NULL outside NOT context."""
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)

    op = tsi_query.EqOperation.model_validate(
        {"$eq": [{"$getField": "attributes.some_key"}, {"$literal": "value"}]}
    )
    result = apply_processor(processor, op)

    assert result is not None
    assert "LIKE" in result
    assert "OR calls_merged.attributes_dump IS NULL" in result


def test_heavy_field_eq_inside_not_skips_optimization() -> None:
    """Eq on a heavy start/end field inside NOT returns None to skip optimization.

    Without this, De Morgan's law turns `NOT(LIKE ... OR IS NULL)` into
    `NOT LIKE ... AND IS NOT NULL`, which excludes unmerged end rows from
    calls_merged and breaks HAVING filters that depend on merged data.
    """
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)

    op = tsi_query.NotOperation.model_validate(
        {
            "$not": [
                {"$eq": [{"$getField": "attributes.some_key"}, {"$literal": "true"}]}
            ]
        }
    )
    result = apply_processor(processor, op)

    # The optimization should be skipped entirely (returns None → no WHERE clause)
    assert result is None


def test_heavy_field_eq_inside_not_without_null_check() -> None:
    """On calls_complete (use_null_check=False), NOT optimization works normally."""
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(
        pb, "calls_complete", use_null_check=False
    )

    op = tsi_query.NotOperation.model_validate(
        {
            "$not": [
                {"$eq": [{"$getField": "attributes.some_key"}, {"$literal": "true"}]}
            ]
        }
    )
    result = apply_processor(processor, op)

    # No null check needed for calls_complete, so the NOT optimization is safe
    assert result is not None
    assert "NOT" in result
    assert "LIKE" in result
    assert "IS NULL" not in result


def test_heavy_field_contains_inside_not_skips_optimization() -> None:
    """Contains on a heavy field inside NOT also skips optimization."""
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)

    op = tsi_query.NotOperation.model_validate(
        {
            "$not": [
                {
                    "$contains": {
                        "input": {"$getField": "attributes.key"},
                        "substr": {"$literal": "val"},
                    }
                }
            ]
        }
    )
    result = apply_processor(processor, op)

    assert result is None


def test_heavy_field_in_inside_not_skips_optimization() -> None:
    """IN on a heavy field inside NOT also skips optimization."""
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)

    op = tsi_query.NotOperation.model_validate(
        {
            "$not": [
                {
                    "$in": [
                        {"$getField": "attributes.key"},
                        [{"$literal": "a"}, {"$literal": "b"}],
                    ]
                }
            ]
        }
    )
    result = apply_processor(processor, op)

    assert result is None
