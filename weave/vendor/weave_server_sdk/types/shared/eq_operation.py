# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["EqOperation"]


class EqOperation(BaseModel):
    """Equality check between two operands.

    Example:
        ```
        {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}
        ```
    """

    eq: List[object] = FieldInfo(alias="$eq")
