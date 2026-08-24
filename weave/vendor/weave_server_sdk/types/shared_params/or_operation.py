# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["OrOperation"]


class OrOperation(TypedDict, total=False):
    """Logical OR. At least one condition must be true.

    Example:
        ```
        {
            "$or": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "a"}]},
                {"$eq": [{"$getField": "op_name"}, {"$literal": "b"}]},
            ]
        }
        ```
    """

    or_: Required[Annotated[Iterable["Operation"], PropertyInfo(alias="$or")]]


from .operation import Operation
