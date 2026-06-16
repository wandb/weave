import pytest

from weave.trace_server.calls_query_builder.calls_query_builder import (
    Condition,
    ParamBuilder,
)
from weave.trace_server.calls_query_builder.optimization_builder import (
    HeavyFieldOptimizationProcessor,
    _maybe_use_null_check,
    apply_processor,
    process_query_to_optimization_sql,
)
from weave.trace_server.calls_query_builder.utils import NotContext
from weave.trace_server.interface import query as tsi_query
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


@pytest.mark.parametrize(
    ("sql", "field", "alias", "use_null_check", "inside_not", "expected"),
    [
        (
            "x LIKE '%y%'",
            "attributes_dump",
            "t",
            True,
            False,
            "(x LIKE '%y%' OR t.attributes_dump IS NULL)",
        ),
        ("x LIKE '%y%'", "attributes_dump", "t", True, True, None),
        ("x LIKE '%y%'", "attributes_dump", "t", False, False, "x LIKE '%y%'"),
        ("x LIKE '%y%'", "op_name", "t", True, False, "x LIKE '%y%'"),
    ],
)
def test_maybe_use_null_check(
    sql: str,
    field: str,
    alias: str,
    use_null_check: bool,
    inside_not: bool,
    expected: str | None,
) -> None:
    """Null-check wrapping: applies outside NOT for nullable fields, else passthrough/None."""
    if inside_not:
        with NotContext.not_context():
            result = _maybe_use_null_check(
                sql, field, alias, use_null_check=use_null_check
            )
    else:
        result = _maybe_use_null_check(sql, field, alias, use_null_check=use_null_check)
    assert result == expected


def test_nested_not_context() -> None:
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
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)
    and_op = tsi_query.AndOperation.model_validate(and_body)
    assert apply_processor(processor, and_op) is not None

    # NOT(AND(...)): single negation, optimization skipped
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)
    not_op = tsi_query.NotOperation.model_validate({"$not": [and_body]})
    assert apply_processor(processor, not_op) is None

    # NOT(NOT(AND(...))): double negation cancels, optimization applies
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)
    double_not_op = tsi_query.NotOperation.model_validate(
        {"$not": [{"$not": [and_body]}]}
    )
    assert apply_processor(processor, double_not_op) is not None

    # NOT(AND(NOT(eq_a), eq_b)): eq_b at depth=1 returns None, so AND
    # bails entirely rather than producing a too-restrictive pre-filter.
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)
    mixed_op = tsi_query.NotOperation.model_validate(
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
    assert apply_processor(processor, mixed_op) is None


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


@pytest.mark.parametrize(
    "inner_op",
    [
        pytest.param(
            {"$eq": [{"$getField": "attributes.some_key"}, {"$literal": "true"}]},
            id="eq",
        ),
        pytest.param(
            {
                "$contains": {
                    "input": {"$getField": "attributes.key"},
                    "substr": {"$literal": "val"},
                }
            },
            id="contains",
        ),
        pytest.param(
            {
                "$in": [
                    {"$getField": "attributes.key"},
                    [{"$literal": "a"}, {"$literal": "b"}],
                ]
            },
            id="in",
        ),
    ],
)
def test_heavy_field_inside_not_skips_optimization(inner_op: dict) -> None:
    """Heavy field ($eq/$contains/$in) inside NOT returns None to skip optimization.

    Without this, De Morgan's law turns `NOT(LIKE ... OR IS NULL)` into
    `NOT LIKE ... AND IS NOT NULL`, which excludes unmerged end rows from
    calls_merged and breaks HAVING filters that depend on merged data.
    """
    pb = ParamBuilder()
    processor = HeavyFieldOptimizationProcessor(pb, "calls_merged", use_null_check=True)

    op = tsi_query.NotOperation.model_validate({"$not": [inner_op]})
    result = apply_processor(processor, op)

    assert result is None


@pytest.mark.parametrize(
    "inner_op",
    [
        pytest.param(
            {"$eq": [{"$getField": "inputs.x"}, {"$literal": "wandb"}]},
            id="eq",
        ),
        pytest.param(
            {
                "$contains": {
                    "input": {"$getField": "inputs.turn.wandb_entity"},
                    "substr": {"$literal": "wandb"},
                }
            },
            id="contains",
        ),
        pytest.param(
            {
                "$in": [
                    {"$getField": "inputs.x"},
                    [{"$literal": "a"}, {"$literal": "b"}],
                ]
            },
            id="in",
        ),
    ],
)
def test_not_heavy_field_skips_pre_filter_on_calls_complete(inner_op: dict) -> None:
    """Regression for WB-34043: NOT($contains/$eq/$in heavy) over-filtered.

    The heavy-field LIKE pattern is a SUPERSET of the real predicate (it
    can match the literal in any key/value of the JSON dump). The
    pre-aggregation contract in `process_query_to_optimization_sql`
    requires the optimizer SQL to be identical or LESS restrictive than
    the post-aggregation HAVING. Wrapping a superset in NOT yields a
    SUBSET, which violates the contract and drops valid rows.

    The reporter ran `not contains "wandb"` on inputs.turn.wandb_entity
    and got 13 rows instead of ~142; the LIKE pattern `%"%wandb%"%` also
    matched the JSON key `"wandb_entity"` present in every row.

    This test reproduces the exact query shape (gt started_at AND not
    <heavy op>) through the public optimizer entry point. It must emit
    no heavy-field pre-filter, on both `calls_complete` (the bug path,
    use_null_check=False) and `calls_merged` (already covered indirectly
    by the null-check branch, asserted here for symmetry).
    """
    conditions = [
        Condition(
            operand=tsi_query.GtOperation.model_validate(
                {"$gt": [{"$getField": "started_at"}, {"$literal": 1775275200}]}
            )
        ),
        Condition(operand=tsi_query.NotOperation.model_validate({"$not": [inner_op]})),
    ]

    pb_complete = ParamBuilder()
    result_complete = process_query_to_optimization_sql(
        conditions, pb_complete, "calls_complete", ReadTable.CALLS_COMPLETE
    )
    assert result_complete.heavy_filter_opt_sql is None, (
        f"calls_complete: pre-filter inside NOT would emit a SUBSET and "
        f"over-filter, got: {result_complete.heavy_filter_opt_sql}"
    )

    pb_merged = ParamBuilder()
    result_merged = process_query_to_optimization_sql(
        conditions, pb_merged, "calls_merged", ReadTable.CALLS_MERGED
    )
    assert result_merged.heavy_filter_opt_sql is None, (
        f"calls_merged: pre-filter inside NOT would emit a SUBSET and "
        f"over-filter, got: {result_merged.heavy_filter_opt_sql}"
    )
