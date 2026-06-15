"""Unit tests for the agent-spans Query DSL compiler.

Focus is on field resolution (semconv, direct columns, custom_attrs_string with
and without explicit prefix) and operator shape. End-to-end execution
against ClickHouse is exercised separately in
``tests/trace_server/test_genai_agent_queries.py``.
"""

import pytest

from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_compiler import (
    InvalidAgentFilterFieldError,
    compile_agent_query,
)

# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "expected_sql", "expected_params"),
    [
        (
            {"$eq": [{"$getField": "weave.agent.name"}, {"$literal": "bot"}]},
            "(s.agent_name = {genai_0:String})",
            {"genai_0": "bot"},
        ),
        (
            {"$eq": [{"$getField": "gen_ai.agent.name"}, {"$literal": "bot"}]},
            "(s.agent_name = {genai_0:String})",
            {"genai_0": "bot"},
        ),
        (
            {"$eq": [{"$getField": "agent.name"}, {"$literal": "bot"}]},
            "(s.agent_name = {genai_0:String})",
            {"genai_0": "bot"},
        ),
        (
            {"$eq": [{"$getField": "trace_id"}, {"$literal": "t1"}]},
            "(s.trace_id = {genai_0:String})",
            {"genai_0": "t1"},
        ),
        # `input_tokens` isn't a semconv key (canonical is `weave.usage.input_tokens`)
        # but resolves because the column is a semconv target.
        (
            {"$gt": [{"$getField": "input_tokens"}, {"$literal": 100}]},
            "(s.input_tokens > {genai_0:Int64})",
            {"genai_0": 100},
        ),
    ],
)
def test_field_resolution_semconv(
    expr: dict, expected_sql: str, expected_params: dict
) -> None:
    sql, params = _compile(expr)
    assert sql == expected_sql
    assert params == expected_params


@pytest.mark.parametrize(
    ("expr", "expected_sql", "expected_params"),
    [
        (
            {"$eq": [{"$getField": "custom_attrs_string.env"}, {"$literal": "prod"}]},
            "(if(mapContains(s.custom_attrs_string, {genai_0:String}), "
            "s.custom_attrs_string[{genai_0:String}], NULL) = {genai_1:String})",
            {"genai_0": "env", "genai_1": "prod"},
        ),
        (
            {"$gt": [{"$getField": "custom_attrs_int.retries"}, {"$literal": 3}]},
            "(if(mapContains(s.custom_attrs_int, {genai_0:String}), "
            "s.custom_attrs_int[{genai_0:String}], NULL) > {genai_1:Int64})",
            {"genai_0": "retries", "genai_1": 3},
        ),
        (
            {"$lt": [{"$getField": "custom_attrs_float.latency"}, {"$literal": 1.5}]},
            "(if(mapContains(s.custom_attrs_float, {genai_0:String}), "
            "s.custom_attrs_float[{genai_0:String}], NULL) < {genai_1:Float64})",
            {"genai_0": "latency", "genai_1": 1.5},
        ),
        (
            {
                "$eq": [
                    {"$getField": "custom_attrs_bool.is_streaming"},
                    {"$literal": True},
                ]
            },
            "(if(mapContains(s.custom_attrs_bool, {genai_0:String}), "
            "s.custom_attrs_bool[{genai_0:String}], NULL) = {genai_1:Bool})",
            {"genai_0": "is_streaming", "genai_1": True},
        ),
    ],
)
def test_field_resolution_custom_attr_explicit_prefix(
    expr: dict, expected_sql: str, expected_params: dict
) -> None:
    sql, params = _compile(expr)
    assert sql == expected_sql
    assert params == expected_params


@pytest.mark.parametrize(
    ("expr", "expected_sql", "expected_params"),
    [
        (
            {"$gt": [{"$getField": "retries"}, {"$literal": 3}]},
            "(if(mapContains(s.custom_attrs_int, {genai_0:String}), "
            "s.custom_attrs_int[{genai_0:String}], NULL) > {genai_1:Int64})",
            {"genai_0": "retries", "genai_1": 3},
        ),
        (
            {"$gt": [{"$getField": "latency_ms"}, {"$literal": 1.5}]},
            "(if(mapContains(s.custom_attrs_float, {genai_0:String}), "
            "s.custom_attrs_float[{genai_0:String}], NULL) > {genai_1:Float64})",
            {"genai_0": "latency_ms", "genai_1": 1.5},
        ),
        (
            {"$eq": [{"$getField": "env"}, {"$literal": "prod"}]},
            "(if(mapContains(s.custom_attrs_string, {genai_0:String}), "
            "s.custom_attrs_string[{genai_0:String}], NULL) = {genai_1:String})",
            {"genai_0": "env", "genai_1": "prod"},
        ),
        # Bool sibling -> custom_attrs_bool, NOT custom_attrs_int (isinstance(True,
        # int) would mis-route here if literal-type ordering were wrong).
        (
            {"$eq": [{"$getField": "is_cached"}, {"$literal": False}]},
            "(if(mapContains(s.custom_attrs_bool, {genai_0:String}), "
            "s.custom_attrs_bool[{genai_0:String}], NULL) = {genai_1:Bool})",
            {"genai_0": "is_cached", "genai_1": False},
        ),
    ],
)
def test_field_resolution_unprefixed_sibling(
    expr: dict, expected_sql: str, expected_params: dict
) -> None:
    sql, params = _compile(expr)
    assert sql == expected_sql
    assert params == expected_params


def test_custom_attr_rejected_field_vs_field() -> None:
    # No literal operand => no sibling hint => rejection.
    with pytest.raises(InvalidAgentFilterFieldError, match="cannot resolve"):
        _compile({"$eq": [{"$getField": "foo"}, {"$getField": "bar"}]})


# ---------------------------------------------------------------------------
# Operator shapes
# ---------------------------------------------------------------------------


def test_eq_with_null() -> None:
    sql, _ = _compile({"$eq": [{"$getField": "agent_name"}, {"$literal": None}]})
    assert sql == "(s.agent_name IS NULL)"


def test_in_with_literal_list() -> None:
    sql, params = _compile(
        {
            "$in": [
                {"$getField": "status_code"},
                [{"$literal": "OK"}, {"$literal": "ERROR"}],
            ]
        }
    )
    assert sql == "(s.status_code IN ({genai_0:String}, {genai_1:String}))"
    assert params == {"genai_0": "OK", "genai_1": "ERROR"}


@pytest.mark.parametrize(
    ("expr", "expected_sql"),
    [
        (
            {"$not": [{"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]}]},
            "(NOT ((s.agent_name = {genai_0:String})))",
        ),
        (
            {
                "$and": [
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]},
                    {"$gt": [{"$getField": "input_tokens"}, {"$literal": 10}]},
                ]
            },
            "((s.agent_name = {genai_0:String}) AND (s.input_tokens > {genai_1:Int64}))",
        ),
        (
            {
                "$or": [
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]},
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "b"}]},
                ]
            },
            "((s.agent_name = {genai_0:String}) OR (s.agent_name = {genai_1:String}))",
        ),
    ],
)
def test_operator_shapes_boolean_join(expr: dict, expected_sql: str) -> None:
    sql, _ = _compile(expr)
    assert sql == expected_sql


@pytest.mark.parametrize(
    ("case_insensitive", "expected_sql"),
    [
        (False, "position(s.reasoning_content, {genai_0:String}) > 0"),
        (True, "positionCaseInsensitive(s.reasoning_content, {genai_0:String}) > 0"),
    ],
)
def test_operator_shapes_contains(case_insensitive: bool, expected_sql: str) -> None:
    sql, params = _compile(
        {
            "$contains": {
                "input": {"$getField": "reasoning_content"},
                "substr": {"$literal": "thought"},
                "case_insensitive": case_insensitive,
            }
        }
    )
    assert sql == expected_sql
    assert params == {"genai_0": "thought"}


def test_convert_forces_custom_attr_map() -> None:
    # ``to: "int"`` on a custom_attrs_string field routes to custom_attrs_int
    # and wraps in toInt64OrNull.
    sql, params = _compile(
        {
            "$gt": [
                {"$convert": {"input": {"$getField": "retries"}, "to": "int"}},
                {"$literal": 5},
            ]
        }
    )
    assert "toInt64OrNull(if(mapContains(s.custom_attrs_int" in sql
    assert params["genai_0"] == "retries"


@pytest.mark.parametrize(
    ("expr", "expected_error"),
    [
        (
            {"$gt": [{"$getField": "input_tokens"}, {"$literal": None}]},
            "Null values are not allowed",
        ),
        (
            {
                "$in": [
                    {"$getField": "agent_name"},
                    [{"$literal": "bot"}, {"$literal": 1}],
                ]
            },
            "same type",
        ),
        (
            {
                "$in": [
                    {"$getField": "agent_name"},
                    [{"$literal": "bot"}, {"$literal": None}],
                ]
            },
            "Null values are not allowed",
        ),
    ],
)
def test_operator_shapes_rejects_compilable(expr: dict, expected_error: str) -> None:
    with pytest.raises(ValueError, match=expected_error):
        _compile(expr)


def test_rejects_invalid_table_alias() -> None:
    pb = ParamBuilder("genai")
    query = Query.model_validate(
        {"$expr": {"$eq": [{"$getField": "agent_name"}, {"$literal": "bot"}]}}
    )
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        compile_agent_query(query, pb, table_alias="s; DROP TABLE spans")


def test_rejects_empty_not() -> None:
    pb = ParamBuilder("genai")
    query = Query.model_construct(expr_=tsi_query.NotOperation.model_construct(not_=()))
    with pytest.raises(ValueError, match="Empty \\$not"):
        compile_agent_query(query, pb)


def _compile(expr: dict) -> tuple[str, dict]:
    """Compile ``{"$expr": <op>}`` and return (condition, params)."""
    pb = ParamBuilder("genai")
    condition = compile_agent_query(Query.model_validate({"$expr": expr}), pb)
    return condition, pb.get_params()
