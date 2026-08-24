# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["InOperation"]


class InOperation(TypedDict, total=False):
    """Membership check.

    Returns true if the left operand is in the list provided as the second operand.

    Example:
        ```
        {"$in": [{"$getField": "op_name"}, [{"$literal": "predict"}, {"$literal": "generate"}]]}
        ```
    """

    in_: Required[Annotated[Iterable[object], PropertyInfo(alias="$in")]]
