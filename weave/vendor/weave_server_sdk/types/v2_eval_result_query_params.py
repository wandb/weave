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
    "V2EvalResultQueryParams",
    "Filter",
    "FilterQuery",
    "FilterQueryExpr",
    "FilterQueryExprLtOperation",
    "FilterQueryExprLteOperation",
    "SortBy",
]


class V2EvalResultQueryParams(TypedDict, total=False):
    entity: Required[str]

    evaluation_call_ids: Optional[SequenceNotStr[str]]
    """Evaluation root call IDs to include."""

    evaluation_run_ids: Optional[SequenceNotStr[str]]
    """Alias for evaluation call IDs from the Evaluation Runs API."""

    filter_logic_operator: Literal["and", "or"]
    """
    How to combine filters across evaluations: 'and' (Match All - row must match in
    ALL evals) or 'or' (Match Any - row must match in ANY eval). Defaults to 'or'
    (Match Any).
    """

    filters: Optional[Iterable[Filter]]
    """Filters applied to grouped rows. Multiple filters are AND'd together."""

    include_costs: bool
    """
    When true, price each trial's predict call so rows and summary report
    predict-only cost (`total_cost` / `predict_total_cost`); scorer costs are
    excluded. Opt-in: other callers skip the cost computation.
    """

    include_predict_and_score_children: bool
    """
    When true (default), fetch child calls (predict/score) of each predict_and_score
    call to populate predict_call_id, scorer_call_ids, and more precise
    latency/token data. When false, these fields are derived from the
    predict_and_score call itself (predict_call_id and scorer_call_ids will be
    null/empty).
    """

    include_raw_data_rows: bool
    """When true, populate raw_data_row on each result row.

    Inline rows are returned as their dict value; dataset-referenced rows are
    returned as the ref string unless resolve_row_refs is also true.
    """

    include_rows: bool
    """
    When true, include grouped row/trial data in `rows` and compute `total_rows` for
    the requested row-level view.
    """

    include_summary: bool
    """When true, include aggregated scorer/evaluation summary data in `summary`."""

    limit: Optional[int]
    """Optional row-level page size applied after grouping and intersection."""

    offset: int
    """Optional row-level page offset applied after grouping and intersection."""

    require_intersection: bool
    """When true, only include rows present in all requested evaluations."""

    resolve_row_refs: bool
    """
    When true (requires include_raw_data_rows=True), resolve dataset-row reference
    strings to actual row data via a table lookup. When false, dataset-row refs are
    returned as-is.
    """

    sort_by: Optional[Iterable[SortBy]]
    """Sort specification for result rows.

    Supported field prefixes: scores.<name>, inputs.<path>, outputs.<path>. When
    null, rows are sorted by row_digest ASC.
    """

    summary_require_intersection: Optional[bool]
    """Optional intersection behavior for the summary section.

    When null, the value of `require_intersection` is used.
    """


class FilterQueryExprLtOperation(TypedDict, total=False):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: Required[Annotated[Iterable[object], PropertyInfo(alias="$lt")]]


class FilterQueryExprLteOperation(TypedDict, total=False):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: Required[Annotated[Iterable[object], PropertyInfo(alias="$lte")]]


FilterQueryExpr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    FilterQueryExprLtOperation,
    GteOperation,
    FilterQueryExprLteOperation,
    InOperation,
    "ContainsOperation",
]


class FilterQuery(TypedDict, total=False):
    """Filter expression.

    Supported field prefixes: scores.<name>, inputs.<path>, outputs.<path>.
    """

    expr: Required[Annotated[FilterQueryExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


class Filter(TypedDict, total=False):
    """A filter scoped to an optional evaluation."""

    query: Required[FilterQuery]
    """Filter expression.

    Supported field prefixes: scores.<name>, inputs.<path>, outputs.<path>.
    """

    evaluation_call_id: Optional[str]
    """When set, filter fields are scoped to this evaluation's data."""


class SortBy(TypedDict, total=False):
    """Sort specification for evaluation results, extending SortBy"""

    direction: Required[Literal["asc", "desc"]]

    field: Required[str]

    evaluation_call_id: Optional[str]
    """Scope the sort to a specific evaluation's scores."""

    mode: Literal["value", "difference"]
    """When 'value', sort by the field value for the specified evaluation.

    When 'difference', sort by max-min spread of the field across all evaluations
    (evaluation_call_id is ignored).
    """


from .shared_params.or_operation import OrOperation
from .shared_params.and_operation import AndOperation
from .shared_params.contains_operation import ContainsOperation
