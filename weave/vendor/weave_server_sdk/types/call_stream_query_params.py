# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .shared_params.eq_operation import EqOperation
from .shared_params.gt_operation import GtOperation
from .shared_params.in_operation import InOperation
from .shared_params.gte_operation import GteOperation
from .shared_params.not_operation import NotOperation

__all__ = [
    "CallStreamQueryParams",
    "Filter",
    "Query",
    "QueryExpr",
    "QueryExprLtOperation",
    "QueryExprLteOperation",
    "SortBy",
]


class CallStreamQueryParams(TypedDict, total=False):
    project_id: Required[str]

    columns: Optional[SequenceNotStr[str]]

    expand_columns: Optional[SequenceNotStr[str]]
    """Columns to expand, i.e. refs to other objects"""

    filter: Optional[Filter]

    include_costs: Optional[bool]
    """Beta, subject to change.

    If true, the response will include any model costs for each call.
    """

    include_feedback: Optional[bool]
    """Beta, subject to change.

    If true, the response will include feedback for each call.
    """

    include_storage_size: Optional[bool]
    """Beta, subject to change.

    If true, the response will include the storage size for a call.
    """

    include_total_storage_size: Optional[bool]
    """Beta, subject to change.

    If true, the response will include the total storage size for a trace.
    """

    include_usernames: Optional[bool]
    """
    If true, the response will attempt to resolve each call's wb_user_id to a
    username for the duration of this request.
    """

    limit: Optional[int]

    offset: Optional[int]

    query: Optional[Query]

    return_expanded_column_values: Optional[bool]
    """If true, the response will include raw values for expanded columns.

    If false, the response expand_columns will only be used for filtering and
    ordering. This is useful for clients that want to resolve refs themselves, e.g.
    for performance reasons.
    """

    sort_by: Optional[Iterable[SortBy]]

    accept: str


class Filter(TypedDict, total=False):
    call_ids: Optional[SequenceNotStr[str]]

    input_refs: Optional[SequenceNotStr[str]]

    op_names: Optional[SequenceNotStr[str]]

    output_refs: Optional[SequenceNotStr[str]]

    parent_ids: Optional[SequenceNotStr[str]]

    thread_ids: Optional[SequenceNotStr[str]]

    trace_ids: Optional[SequenceNotStr[str]]

    trace_roots_only: Optional[bool]

    turn_ids: Optional[SequenceNotStr[str]]

    wb_run_ids: Optional[SequenceNotStr[str]]

    wb_user_ids: Optional[SequenceNotStr[str]]


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


class SortBy(TypedDict, total=False):
    direction: Required[Literal["asc", "desc"]]

    field: Required[str]


from .shared_params.or_operation import OrOperation
from .shared_params.and_operation import AndOperation
from .shared_params.contains_operation import ContainsOperation
