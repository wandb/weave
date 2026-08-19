# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union
from typing_extensions import TypeAlias, TypeAliasType

from pydantic import Field as FieldInfo

from ..._compat import PYDANTIC_V1
from ..._models import BaseModel
from .eq_operation import EqOperation
from .gt_operation import GtOperation
from .in_operation import InOperation
from .gte_operation import GteOperation
from .not_operation import NotOperation
from .get_field_operator import GetFieldOperator

__all__ = ["Operation", "LtOperation", "LteOperation"]


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


if TYPE_CHECKING or not PYDANTIC_V1:
    Operation = TypeAliasType(
        "Operation",
        Union[
            "LiteralOperation",
            GetFieldOperator,
            "ConvertOperation",
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
            object,
        ],
    )
else:
    Operation: TypeAlias = Union[
        "LiteralOperation",
        GetFieldOperator,
        "ConvertOperation",
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
        object,
    ]

from .or_operation import OrOperation
from .and_operation import AndOperation
from .convert_operation import ConvertOperation
from .literal_operation import LiteralOperation
from .contains_operation import ContainsOperation
