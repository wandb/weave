# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["NotOperation"]


class NotOperation(TypedDict, total=False):
    """Logical NOT. Inverts the condition.

    Example:
        ```
        {"$not": [{"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}]}
        ```
    """

    not_: Required[Annotated[Iterable[object], PropertyInfo(alias="$not")]]
