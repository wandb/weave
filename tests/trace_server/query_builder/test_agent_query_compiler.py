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


def _compile(expr: dict) -> tuple[str, dict]:
    """Compile ``{"$expr": <op>}`` and return (condition, params)."""
    pb = ParamBuilder("genai")
    condition = compile_agent_query(Query.model_validate({"$expr": expr}), pb)
    return condition, pb.get_params()


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


class TestFieldResolution:
    def test_semconv_canonical_key(self) -> None:
        sql, params = _compile(
            {"$eq": [{"$getField": "weave.agent.name"}, {"$literal": "bot"}]}
        )
        assert sql == "(s.agent_name = {genai_0:String})"
        assert params == {"genai_0": "bot"}

    def test_semconv_gen_ai_alias(self) -> None:
        sql, _ = _compile(
            {"$eq": [{"$getField": "gen_ai.agent.name"}, {"$literal": "bot"}]}
        )
        assert "s.agent_name" in sql

    def test_semconv_short_form(self) -> None:
        sql, _ = _compile({"$eq": [{"$getField": "agent.name"}, {"$literal": "bot"}]})
        assert "s.agent_name" in sql

    def test_direct_column_name(self) -> None:
        sql, _ = _compile({"$eq": [{"$getField": "trace_id"}, {"$literal": "t1"}]})
        assert "s.trace_id" in sql

    def test_semconv_target_column_by_name(self) -> None:
        # `input_tokens` isn't a semconv key — the canonical key is
        # `weave.usage.input_tokens` — but the column should still resolve
        # because the compiler accepts any column that's a semconv target.
        sql, _ = _compile({"$gt": [{"$getField": "input_tokens"}, {"$literal": 100}]})
        assert "s.input_tokens" in sql

    def test_custom_attr_explicit_prefix_string(self) -> None:
        sql, params = _compile(
            {"$eq": [{"$getField": "custom_attrs_string.env"}, {"$literal": "prod"}]}
        )
        # key param added before value param
        assert "s.custom_attrs_string[{genai_0:String}] = {genai_1:String}" in sql
        assert params == {"genai_0": "env", "genai_1": "prod"}

    def test_custom_attr_explicit_prefix_int(self) -> None:
        sql, params = _compile(
            {"$gt": [{"$getField": "custom_attrs_int.retries"}, {"$literal": 3}]}
        )
        assert "s.custom_attrs_int[{genai_0:String}] > {genai_1:Int64}" in sql
        assert params == {"genai_0": "retries", "genai_1": 3}

    def test_custom_attr_explicit_prefix_float(self) -> None:
        sql, params = _compile(
            {
                "$lt": [
                    {"$getField": "custom_attrs_float.latency"},
                    {"$literal": 1.5},
                ]
            }
        )
        assert "s.custom_attrs_float[{genai_0:String}] < {genai_1:Float64}" in sql
        assert params == {"genai_0": "latency", "genai_1": 1.5}

    def test_custom_attr_unprefixed_sibling_int(self) -> None:
        sql, params = _compile({"$gt": [{"$getField": "retries"}, {"$literal": 3}]})
        # Unknown name + int sibling -> custom_attrs_int map
        assert "s.custom_attrs_int[{genai_0:String}] > {genai_1:Int64}" in sql
        assert params == {"genai_0": "retries", "genai_1": 3}

    def test_custom_attr_unprefixed_sibling_float(self) -> None:
        sql, _ = _compile({"$gt": [{"$getField": "latency_ms"}, {"$literal": 1.5}]})
        assert "s.custom_attrs_float[" in sql

    def test_custom_attr_unprefixed_sibling_str(self) -> None:
        sql, _ = _compile({"$eq": [{"$getField": "env"}, {"$literal": "prod"}]})
        assert "s.custom_attrs_string[" in sql

    def test_custom_attr_explicit_prefix_bool(self) -> None:
        sql, params = _compile(
            {
                "$eq": [
                    {"$getField": "custom_attrs_bool.is_streaming"},
                    {"$literal": True},
                ]
            }
        )
        assert "s.custom_attrs_bool[{genai_0:String}] = {genai_1:Bool}" in sql
        assert params == {"genai_0": "is_streaming", "genai_1": True}

    def test_custom_attr_unprefixed_sibling_bool(self) -> None:
        # Bool sibling -> custom_attrs_bool (not custom_attrs_int, which
        # Python's isinstance(True, int) would suggest if ordering were wrong).
        sql, _ = _compile({"$eq": [{"$getField": "is_cached"}, {"$literal": False}]})
        assert "s.custom_attrs_bool[" in sql

    def test_custom_attr_rejected_field_vs_field(self) -> None:
        # No literal operand => no sibling hint => rejection.
        with pytest.raises(InvalidAgentFilterFieldError, match="cannot resolve"):
            _compile({"$eq": [{"$getField": "foo"}, {"$getField": "bar"}]})


# ---------------------------------------------------------------------------
# Operator shapes
# ---------------------------------------------------------------------------


class TestOperatorShapes:
    def test_eq_with_null(self) -> None:
        sql, _ = _compile({"$eq": [{"$getField": "agent_name"}, {"$literal": None}]})
        assert sql == "(s.agent_name IS NULL)"

    def test_rejects_invalid_table_alias(self) -> None:
        pb = ParamBuilder("genai")
        query = Query.model_validate(
            {"$expr": {"$eq": [{"$getField": "agent_name"}, {"$literal": "bot"}]}}
        )

        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            compile_agent_query(query, pb, table_alias="s; DROP TABLE spans")

    def test_rejects_empty_not(self) -> None:
        pb = ParamBuilder("genai")
        query = Query.model_construct(
            expr_=tsi_query.NotOperation.model_construct(not_=())
        )

        with pytest.raises(ValueError, match="Empty \\$not"):
            compile_agent_query(query, pb)

    def test_not_wraps_in_negation(self) -> None:
        sql, _ = _compile(
            {"$not": [{"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]}]}
        )
        assert sql.startswith("(NOT (")

    def test_and_joins_with_and(self) -> None:
        sql, _ = _compile(
            {
                "$and": [
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]},
                    {"$gt": [{"$getField": "input_tokens"}, {"$literal": 10}]},
                ]
            }
        )
        assert " AND " in sql

    def test_or_joins_with_or(self) -> None:
        sql, _ = _compile(
            {
                "$or": [
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "a"}]},
                    {"$eq": [{"$getField": "agent.name"}, {"$literal": "b"}]},
                ]
            }
        )
        assert " OR " in sql

    def test_in_with_literal_list(self) -> None:
        sql, params = _compile(
            {
                "$in": [
                    {"$getField": "status_code"},
                    [{"$literal": "OK"}, {"$literal": "ERROR"}],
                ]
            }
        )
        assert "s.status_code IN (" in sql
        assert params == {"genai_0": "OK", "genai_1": "ERROR"}

    def test_rejects_null_non_eq_comparison(self) -> None:
        with pytest.raises(ValueError, match="Null values are not allowed"):
            _compile({"$gt": [{"$getField": "input_tokens"}, {"$literal": None}]})

    def test_rejects_mixed_in_literal_types(self) -> None:
        with pytest.raises(ValueError, match="same type"):
            _compile(
                {
                    "$in": [
                        {"$getField": "agent_name"},
                        [{"$literal": "bot"}, {"$literal": 1}],
                    ]
                }
            )

    def test_rejects_null_in_literal_list(self) -> None:
        with pytest.raises(ValueError, match="Null values are not allowed"):
            _compile(
                {
                    "$in": [
                        {"$getField": "agent_name"},
                        [{"$literal": "bot"}, {"$literal": None}],
                    ]
                }
            )

    def test_contains_emits_position_gt_zero(self) -> None:
        sql, _ = _compile(
            {
                "$contains": {
                    "input": {"$getField": "reasoning_content"},
                    "substr": {"$literal": "thought"},
                    "case_insensitive": False,
                }
            }
        )
        assert "position(s.reasoning_content, " in sql
        assert sql.endswith(") > 0")

    def test_contains_case_insensitive(self) -> None:
        sql, _ = _compile(
            {
                "$contains": {
                    "input": {"$getField": "reasoning_content"},
                    "substr": {"$literal": "thought"},
                    "case_insensitive": True,
                }
            }
        )
        assert "positionCaseInsensitive(" in sql

    def test_convert_forces_custom_attr_map(self) -> None:
        # ``to: "int"`` on a custom_attrs_string field routes to custom_attrs_int
        # and wraps in toInt64OrNull.
        sql, params = _compile(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "retries"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            }
        )
        assert "toInt64OrNull(s.custom_attrs_int[" in sql
        assert params["genai_0"] == "retries"
