from typing import Any

from weave.trace_server.interface.query import (
    GetFieldOperator,
    LiteralOperation,
    NotOperation,
    Operand,
)


def get_field_expr(field: str) -> GetFieldOperator:
    return GetFieldOperator.model_validate({"$getField": field})


def literal_expr(value: Any) -> LiteralOperation:
    return LiteralOperation.model_validate({"$literal": value})


def exists_expr(expr: Operand) -> NotOperation:
    return NotOperation.model_validate(
        {
            "$not": [
                {
                    "$eq": [
                        expr,
                        literal_expr(""),
                    ]
                }
            ]
        }
    )
