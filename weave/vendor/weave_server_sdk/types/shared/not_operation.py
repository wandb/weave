# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from pydantic import Field as FieldInfo

from ..._models import BaseModel

__all__ = ["NotOperation"]


class NotOperation(BaseModel):
    """Logical NOT. Inverts the condition.

    Example:
        ```
        {"$not": [{"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}]}
        ```
    """

    not_: List[object] = FieldInfo(alias="$not")
