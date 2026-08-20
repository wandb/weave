# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["GetFieldOperator"]


class GetFieldOperator(TypedDict, total=False):
    """Access a field on the traced call.

    Supports dot notation for nested access, e.g. `summary.usage.tokens`.

    Only works on fields present in the `CallSchema`, including:
    - Top-level fields like `op_name`, `trace_id`, `started_at`
    - Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc.

    Example:
        ```
        {"$getField": "op_name"}
        ```
    """

    get_field: Required[Annotated[str, PropertyInfo(alias="$getField")]]
