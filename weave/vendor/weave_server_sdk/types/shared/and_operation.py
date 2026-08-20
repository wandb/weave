# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["AndOperation"]


class AndOperation(BaseModel):
    """Logical AND. All conditions must evaluate to true.

    Example:
        ```
        {
            "$and": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]},
                {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]},
            ]
        }
        ```
    """

    and_: List["Operation"] = FieldInfo(alias="$and")


from .operation import Operation
