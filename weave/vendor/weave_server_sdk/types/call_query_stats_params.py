# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["CallQueryStatsParams", "Filter", "Query"]


class CallQueryStatsParams(TypedDict, total=False):
    project_id: Required[str]

    expand_columns: Optional[SequenceNotStr[str]]
    """
    Columns with refs to objects or table rows that require expansion during
    filtering or ordering.
    """

    filter: Optional[Filter]

    include_total_storage_size: Optional[bool]

    limit: Optional[int]

    query: Optional[Query]


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


class Query(TypedDict, total=False):
    expr: Required[Annotated["Expr", PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


from .shared_params.expr import Expr
