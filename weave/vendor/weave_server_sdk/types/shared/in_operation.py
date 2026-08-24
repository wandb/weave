# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["InOperation"]


class InOperation(BaseModel):
    """Membership check.

    Returns true if the left operand is in the list provided as the second operand.

    Example:
        ```
        {"$in": [{"$getField": "op_name"}, [{"$literal": "predict"}, {"$literal": "generate"}]]}
        ```
    """

    in_: List[object] = FieldInfo(alias="$in")
