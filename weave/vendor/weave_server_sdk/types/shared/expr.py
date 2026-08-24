# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from typing_extensions import TypeAlias

from pydantic import Field as FieldInfo

from ..._models import BaseModel
from .eq_operation import EqOperation
from .gt_operation import GtOperation
from .in_operation import InOperation
from .gte_operation import GteOperation
from .not_operation import NotOperation

__all__ = ["Expr", "LtOperation", "LteOperation"]


class LtOperation(BaseModel):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: List[object] = FieldInfo(alias="$lt")


class LteOperation(BaseModel):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: List[object] = FieldInfo(alias="$lte")


Expr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    LtOperation,
    GteOperation,
    LteOperation,
    InOperation,
    "ContainsOperation",
]

from .or_operation import OrOperation
from .and_operation import AndOperation
from .contains_operation import ContainsOperation
