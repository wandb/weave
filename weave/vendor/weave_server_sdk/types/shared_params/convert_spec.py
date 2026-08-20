# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

__all__ = ["ConvertSpec"]


class ConvertSpec(TypedDict, total=False):
    """Specifies conversion details for `$convert`.

    - `input`: The operand to convert.
    - `to`: The type to convert to.
    """

    input: Required["Operation"]

    to: Required[Literal["double", "string", "int", "bool", "exists"]]


from .operation import Operation
