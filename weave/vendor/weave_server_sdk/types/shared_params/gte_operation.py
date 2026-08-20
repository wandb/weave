# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["GteOperation"]


class GteOperation(TypedDict, total=False):
    """Greater than or equal comparison.

    Example:
        ```
        {"$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    gte: Required[Annotated[Iterable[object], PropertyInfo(alias="$gte")]]
