# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypeAlias, TypedDict

from ..._utils import PropertyInfo
from ..shared_params.eq_operation import EqOperation
from ..shared_params.gt_operation import GtOperation
from ..shared_params.in_operation import InOperation
from ..shared_params.gte_operation import GteOperation
from ..shared_params.not_operation import NotOperation

__all__ = ["SpanCustomAttrsSchemaParams", "Query", "QueryExpr", "QueryExprLtOperation", "QueryExprLteOperation"]


class SpanCustomAttrsSchemaParams(TypedDict, total=False):
    project_id: Required[str]

    limit: int

    offset: int

    query: Optional[Query]

    started_after: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    started_before: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]


class QueryExprLtOperation(TypedDict, total=False):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: Required[Annotated[Iterable[object], PropertyInfo(alias="$lt")]]


class QueryExprLteOperation(TypedDict, total=False):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: Required[Annotated[Iterable[object], PropertyInfo(alias="$lte")]]


QueryExpr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    QueryExprLtOperation,
    GteOperation,
    QueryExprLteOperation,
    InOperation,
    "ContainsOperation",
]


class Query(TypedDict, total=False):
    expr: Required[Annotated[QueryExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


from ..shared_params.or_operation import OrOperation
from ..shared_params.and_operation import AndOperation
from ..shared_params.contains_operation import ContainsOperation
