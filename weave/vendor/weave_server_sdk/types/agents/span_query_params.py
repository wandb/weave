# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo
from ..shared_params.eq_operation import EqOperation
from ..shared_params.gt_operation import GtOperation
from ..shared_params.in_operation import InOperation
from ..shared_params.gte_operation import GteOperation
from ..shared_params.not_operation import NotOperation

__all__ = [
    "SpanQueryParams",
    "CustomAttrColumn",
    "GroupBy",
    "GroupDistribution",
    "GroupDistributionValue",
    "GroupFilter",
    "GroupFilterMeasure",
    "GroupFilterMeasureFilter",
    "GroupFilterMeasureFilterExpr",
    "GroupFilterMeasureFilterExprLtOperation",
    "GroupFilterMeasureFilterExprLteOperation",
    "GroupFilterMeasureValue",
    "GroupFilterGroupBy",
    "Measure",
    "MeasureFilter",
    "MeasureFilterExpr",
    "MeasureFilterExprLtOperation",
    "MeasureFilterExprLteOperation",
    "MeasureValue",
    "Query",
    "QueryExpr",
    "QueryExprLtOperation",
    "QueryExprLteOperation",
    "SignalFilters",
    "SignalFiltersRating",
    "SortBy",
]


class SpanQueryParams(TypedDict, total=False):
    project_id: Required[str]

    custom_attr_columns: Iterable[CustomAttrColumn]

    group_by: Optional[Iterable[GroupBy]]

    group_distributions: Iterable[GroupDistribution]

    group_filters: Iterable[GroupFilter]

    include_costs: bool

    include_details: bool

    limit: int

    measures: Iterable[Measure]

    offset: int

    query: Optional[Query]

    signal_filters: Optional[SignalFilters]

    sort_by: Optional[Iterable[SortBy]]

    started_after: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    started_before: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]


class CustomAttrColumn(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class GroupBy(TypedDict, total=False):
    """Reference to a field or map-key that spans should be grouped by.

    `source="field"` targets a semantic span field (`agent.name`) or direct
    span column (`agent_name`), allowlisted server-side. `source="column"` is
    accepted for existing callers.
    The other sources target keys inside the typed custom attribute Map columns,
    which accept arbitrary user-defined keys.
    """

    key: Required[str]

    alias: Optional[str]

    source: Literal[
        "field", "column", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class GroupDistributionValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class GroupDistribution(TypedDict, total=False):
    """One custom attribute distribution to compute per returned span group."""

    alias: Required[str]

    value: Required[GroupDistributionValue]
    """Reference to a span field or typed custom attribute map value."""

    bins: int

    top_n: int


class GroupFilterMeasureFilterExprLtOperation(TypedDict, total=False):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: Required[Annotated[Iterable[object], PropertyInfo(alias="$lt")]]


class GroupFilterMeasureFilterExprLteOperation(TypedDict, total=False):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: Required[Annotated[Iterable[object], PropertyInfo(alias="$lte")]]


GroupFilterMeasureFilterExpr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    GroupFilterMeasureFilterExprLtOperation,
    GteOperation,
    GroupFilterMeasureFilterExprLteOperation,
    InOperation,
    "ContainsOperation",
]


class GroupFilterMeasureFilter(TypedDict, total=False):
    expr: Required[Annotated[GroupFilterMeasureFilterExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


class GroupFilterMeasureValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class GroupFilterMeasure(TypedDict, total=False):
    """One aggregate measure computed over spans in a group or bucket."""

    aggregation: Required[Literal["sum", "avg", "min", "max", "count", "count_distinct", "count_true", "count_false"]]

    alias: Required[str]

    filter: Optional[GroupFilterMeasureFilter]

    value: Optional[GroupFilterMeasureValue]
    """Reference to a span field or typed custom attribute map value."""

    value_type: Optional[Literal["datetime", "number", "boolean", "string"]]


class GroupFilterGroupBy(TypedDict, total=False):
    """Reference to a field or map-key that spans should be grouped by.

    `source="field"` targets a semantic span field (`agent.name`) or direct
    span column (`agent_name`), allowlisted server-side. `source="column"` is
    accepted for existing callers.
    The other sources target keys inside the typed custom attribute Map columns,
    which accept arbitrary user-defined keys.
    """

    key: Required[str]

    alias: Optional[str]

    source: Literal[
        "field", "column", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class GroupFilter(TypedDict, total=False):
    """Range filter over one grouped span measure."""

    measure: Required[GroupFilterMeasure]
    """One aggregate measure computed over spans in a group or bucket."""

    group_by: Iterable[GroupFilterGroupBy]

    max: Annotated[Union[float, Union[str, datetime], None], PropertyInfo(format="iso8601")]

    min: Annotated[Union[float, Union[str, datetime], None], PropertyInfo(format="iso8601")]


class MeasureFilterExprLtOperation(TypedDict, total=False):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: Required[Annotated[Iterable[object], PropertyInfo(alias="$lt")]]


class MeasureFilterExprLteOperation(TypedDict, total=False):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: Required[Annotated[Iterable[object], PropertyInfo(alias="$lte")]]


MeasureFilterExpr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    MeasureFilterExprLtOperation,
    GteOperation,
    MeasureFilterExprLteOperation,
    InOperation,
    "ContainsOperation",
]


class MeasureFilter(TypedDict, total=False):
    expr: Required[Annotated[MeasureFilterExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


class MeasureValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class Measure(TypedDict, total=False):
    """One aggregate measure computed over spans in a group or bucket."""

    aggregation: Required[Literal["sum", "avg", "min", "max", "count", "count_distinct", "count_true", "count_false"]]

    alias: Required[str]

    filter: Optional[MeasureFilter]

    value: Optional[MeasureValue]
    """Reference to a span field or typed custom attribute map value."""

    value_type: Optional[Literal["datetime", "number", "boolean", "string"]]


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


class SignalFiltersRating(TypedDict, total=False):
    op: Required[Literal["gte", "gt", "lte", "lt", "eq"]]

    scorer_key: Required[str]

    value: Required[float]


class SignalFilters(TypedDict, total=False):
    ratings: Iterable[SignalFiltersRating]

    tags: SequenceNotStr[str]


class SortBy(TypedDict, total=False):
    """Sort specification for agent query endpoints."""

    field: Required[str]

    direction: Literal["asc", "desc"]


from ..shared_params.or_operation import OrOperation
from ..shared_params.and_operation import AndOperation
from ..shared_params.contains_operation import ContainsOperation
