# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["GtOperation"]


class GtOperation(BaseModel):
    """Greater than comparison.

    Example:
        ```
        {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    gt: List[object] = FieldInfo(alias="$gt")
