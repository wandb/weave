from collections.abc import Mapping
from typing import Any


def get_field_expr(field: str) -> dict[str, Any]:
    return {"$getField": field}


def literal_expr(value: Any) -> dict[str, Any]:
    return {"$literal": value}


def exists_expr(expr: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$not": [
            {
                "$eq": [
                    expr,
                    literal_expr(""),
                ]
            }
        ]
    }
