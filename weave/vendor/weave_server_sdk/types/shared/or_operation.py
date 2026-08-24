# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["OrOperation"]


class OrOperation(BaseModel):
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

    or_: List["Operation"] = FieldInfo(alias="$or")


from .operation import Operation
