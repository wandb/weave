import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.in_memory_trace_server import (
    _ch_has_token,
    _orm_eval_query,
    _QueryFilterEvaluator,
)
from weave.trace_server.orm import Column, Table


@pytest.mark.parametrize(
    ("haystack", "needle", "case_insensitive", "expected"),
    [
        ("the example row", "example", False, True),  # whole-token hit
        ("examples", "example", False, False),  # substring is not a token
        ("Example", "example", True, True),  # case-insensitive match
        ("a.b-c", "b", False, True),  # separator-split tokenization
        (123, "example", False, False),  # non-string haystack guard
        ("example", 123, False, False),  # non-string needle guard
    ],
)
def test_ch_has_token_semantics(haystack, needle, case_insensitive, expected) -> None:
    """Whole-token match only; non-strings never match (hasToken semantics)."""
    assert _ch_has_token(haystack, needle, case_insensitive) is expected


def _token_table() -> Table:
    return Table(
        "calls",
        [
            Column("id", "string"),
            Column("op_name", "string"),
            Column("input_refs", "array_string"),
        ],
    )


def _token_query(field: str, needle: str, case_insensitive: bool = False) -> tsi.Query:
    return tsi.Query.model_validate(
        {
            "$expr": {
                "$containsToken": {
                    "input": {"$getField": field},
                    "substr": {"$literal": needle},
                    "case_insensitive": case_insensitive,
                }
            }
        }
    )


_NESTED_AND_QUERY = tsi.Query.model_validate(
    {
        "$expr": {
            "$and": [
                {
                    "$containsToken": {
                        "input": {"$getField": "op_name"},
                        "substr": {"$literal": "example"},
                    }
                }
            ]
        }
    }
)


@pytest.mark.parametrize(
    ("row", "query", "expected"),
    [
        # String column: hasToken whole-token match, case-sensitive then -insensitive.
        ({"op_name": "the example row"}, _token_query("op_name", "example"), True),
        ({"op_name": "examples"}, _token_query("op_name", "example"), False),
        (
            {"op_name": "Example"},
            _token_query("op_name", "example", case_insensitive=True),
            True,
        ),
        # Array(String) column: membership, case-sensitive (hit + miss), -insensitive, empty.
        ({"input_refs": ["alpha", "beta"]}, _token_query("input_refs", "alpha"), True),
        ({"input_refs": ["alphas"]}, _token_query("input_refs", "alpha"), False),
        (
            {"input_refs": ["Alpha"]},
            _token_query("input_refs", "alpha", case_insensitive=True),
            True,
        ),
        ({"input_refs": []}, _token_query("input_refs", "alpha"), False),
        # Nested under $and: exercises the operand-dispatch branch.
        ({"op_name": "the example row"}, _NESTED_AND_QUERY, True),
    ],
)
def test_orm_eval_query_contains_token(row, query, expected) -> None:
    """_orm_eval_query mirrors hasToken for strings and array membership for
    Array(String) columns (case-sensitive and -insensitive).
    """
    assert bool(_orm_eval_query(_token_table(), row, query)) is expected


@pytest.mark.parametrize(
    ("value", "needle", "case_insensitive", "expected"),
    [
        ("the example row", "example", False, True),  # token hit
        ("examples", "example", False, False),  # token miss
        ("Example", "example", True, True),  # case-insensitive match
    ],
)
def test_query_filter_evaluator_contains_token(
    value, needle, case_insensitive, expected
) -> None:
    """The shared filter evaluator mirrors hasToken token semantics."""
    evaluator = _QueryFilterEvaluator(lambda field_path, cast: value)
    assert (
        evaluator.matches(_token_query("display_name", needle, case_insensitive))
        is expected
    )
