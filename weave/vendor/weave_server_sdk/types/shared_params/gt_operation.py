# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["GtOperation"]


class GtOperation(TypedDict, total=False):
    """Greater than comparison.

    Example:
        ```
        {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    gt: Required[Annotated[Iterable[object], PropertyInfo(alias="$gt")]]
