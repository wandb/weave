from typing import Any, TypeAlias

from weave_server_sdk.models import (
    AndOperation,
    ContainsOperation,
    ConvertOperation,
    EqOperation,
    GetFieldOperator,
    GteOperation,
    GtOperation,
    InOperation,
    LiteralOperation,
    NotOperation,
    OrOperation,
)

# The tsi query module exported an `Operand` union alias; the generated SDK
# inlines the union instead, so spell it out here.
Operand: TypeAlias = (
    LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation
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
