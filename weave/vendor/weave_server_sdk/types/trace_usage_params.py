# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from typing_extensions import Required, Annotated, TypeAlias, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .shared_params.eq_operation import EqOperation
from .shared_params.gt_operation import GtOperation
from .shared_params.in_operation import InOperation
from .shared_params.gte_operation import GteOperation
from .shared_params.not_operation import NotOperation

__all__ = ["TraceUsageParams", "Filter", "Query", "QueryExpr", "QueryExprLtOperation", "QueryExprLteOperation"]


class TraceUsageParams(TypedDict, total=False):
    project_id: Required[str]

    filter: Optional[Filter]
    """Filter to select calls. Typically use trace_ids to get all calls in a trace."""

    include_costs: bool
    """If true, include cost calculations in the usage."""

    limit: int
    """Maximum number of calls to process.

    Acts as a safety limit to prevent unbounded memory usage.
    """

    query: Optional[Query]
    """Additional query conditions for filtering calls."""


class Filter(TypedDict, total=False):
    """Filter to select calls. Typically use trace_ids to get all calls in a trace."""

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
    """Additional query conditions for filtering calls."""

    expr: Required[Annotated[QueryExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


from .shared_params.or_operation import OrOperation
from .shared_params.and_operation import AndOperation
from .shared_params.contains_operation import ContainsOperation
