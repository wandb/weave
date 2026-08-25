# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["ConvertOperation"]


class ConvertOperation(TypedDict, total=False):
    """Convert the input value to a specific type (e.g., `int`, `bool`, `string`).

    Example:
        ```
        {"$convert": {"input": {"$getField": "inputs.value"}, "to": "int"}}
        ```
    """

    convert: Required[Annotated["ConvertSpec", PropertyInfo(alias="$convert")]]
    """Specifies conversion details for `$convert`.

    - `input`: The operand to convert.
    - `to`: The type to convert to.
    """


from .convert_spec import ConvertSpec
