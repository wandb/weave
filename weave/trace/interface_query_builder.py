from weave.trace_server.interface.query import (
    NotOperation,
)


def exists_expr(field: str) -> NotOperation:
    return NotOperation.model_validate(
        {
            "$not": [
                {
                    "$eq": [
                        {"$getField": field},
                        {"$literal": ""},
                    ]
                }
            ]
        }
    )
