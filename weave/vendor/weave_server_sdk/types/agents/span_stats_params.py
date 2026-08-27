# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Iterable, Optional
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
    "SpanStatsParams",
    "BucketBy",
    "BucketByAgentSpanStatsTimeBucketSpec",
    "BucketByAgentSpanStatsNumericBucketSpec",
    "BucketByAgentSpanStatsNumericBucketSpecGroupBy",
    "BucketByAgentSpanStatsNumericBucketSpecMeasure",
    "BucketByAgentSpanStatsNumericBucketSpecMeasureFilter",
    "BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExpr",
    "BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLtOperation",
    "BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLteOperation",
    "BucketByAgentSpanStatsNumericBucketSpecMeasureValue",
    "BucketByAgentSpanStatsNumericBucketSpecValue",
    "GroupBy",
    "GroupFilter",
    "GroupFilterMeasure",
    "GroupFilterMeasureFilter",
    "GroupFilterMeasureFilterExpr",
    "GroupFilterMeasureFilterExprLtOperation",
    "GroupFilterMeasureFilterExprLteOperation",
    "GroupFilterMeasureValue",
    "GroupFilterGroupBy",
    "Metric",
    "MetricValue",
    "Query",
    "QueryExpr",
    "QueryExprLtOperation",
    "QueryExprLteOperation",
    "SignalFilters",
    "SignalFiltersRating",
]


class SpanStatsParams(TypedDict, total=False):
    project_id: Required[str]

    start: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    bucket_by: Optional[BucketBy]
    """Bucket stats rows by started_at time intervals."""

    end: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    granularity: Optional[int]

    group_by: Iterable[GroupBy]

    group_filters: Iterable[GroupFilter]

    group_limit: int

    metrics: Iterable[Metric]

    query: Optional[Query]

    signal_filters: Optional[SignalFilters]

    timezone: str


class BucketByAgentSpanStatsTimeBucketSpec(TypedDict, total=False):
    """Bucket stats rows by started_at time intervals."""

    type: Literal["time"]


class BucketByAgentSpanStatsNumericBucketSpecGroupBy(TypedDict, total=False):
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


class BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLtOperation(TypedDict, total=False):
    """Less than comparison.

    Example:
        ```
        {"$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lt: Required[Annotated[Iterable[object], PropertyInfo(alias="$lt")]]


class BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLteOperation(TypedDict, total=False):
    """Less than or equal comparison.

    Example:
        ```
        {"$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]}
        ```
    """

    lte: Required[Annotated[Iterable[object], PropertyInfo(alias="$lte")]]


BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExpr: TypeAlias = Union[
    "AndOperation",
    "OrOperation",
    NotOperation,
    EqOperation,
    GtOperation,
    BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLtOperation,
    GteOperation,
    BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExprLteOperation,
    InOperation,
    "ContainsOperation",
]


class BucketByAgentSpanStatsNumericBucketSpecMeasureFilter(TypedDict, total=False):
    expr: Required[Annotated[BucketByAgentSpanStatsNumericBucketSpecMeasureFilterExpr, PropertyInfo(alias="$expr")]]
    """Logical AND. All conditions must evaluate to true.

    Example:
    ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
    """


class BucketByAgentSpanStatsNumericBucketSpecMeasureValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class BucketByAgentSpanStatsNumericBucketSpecMeasure(TypedDict, total=False):
    """One aggregate measure computed over spans in a group or bucket."""

    aggregation: Required[Literal["sum", "avg", "min", "max", "count", "count_distinct", "count_true", "count_false"]]

    alias: Required[str]

    filter: Optional[BucketByAgentSpanStatsNumericBucketSpecMeasureFilter]

    value: Optional[BucketByAgentSpanStatsNumericBucketSpecMeasureValue]
    """Reference to a span field or typed custom attribute map value."""

    value_type: Optional[Literal["datetime", "number", "boolean", "string"]]


class BucketByAgentSpanStatsNumericBucketSpecValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class BucketByAgentSpanStatsNumericBucketSpec(TypedDict, total=False):
    """Bucket stats rows by ranges of one numeric span or grouped value."""

    alias: str

    bins: int

    group_by: Iterable[BucketByAgentSpanStatsNumericBucketSpecGroupBy]

    max: Optional[float]

    measure: Optional[BucketByAgentSpanStatsNumericBucketSpecMeasure]
    """One aggregate measure computed over spans in a group or bucket."""

    min: Optional[float]

    type: Literal["number"]

    value: Optional[BucketByAgentSpanStatsNumericBucketSpecValue]
    """Reference to a span field or typed custom attribute map value."""


BucketBy: TypeAlias = Union[BucketByAgentSpanStatsTimeBucketSpec, BucketByAgentSpanStatsNumericBucketSpec]


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


class MetricValue(TypedDict, total=False):
    """Reference to a span field or typed custom attribute map value."""

    key: Required[str]

    source: Literal[
        "field", "derived", "custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"
    ]


class Metric(TypedDict, total=False):
    """Metric to extract from each matching span and aggregate into chart rows."""

    alias: Required[str]

    value: Required[MetricValue]
    """Reference to a span field or typed custom attribute map value."""

    value_type: Required[Literal["datetime", "number", "boolean", "string"]]

    aggregations: List[Literal["sum", "avg", "min", "max", "count", "count_distinct", "count_true", "count_false"]]

    percentiles: Iterable[float]


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


from ..shared_params.or_operation import OrOperation
from ..shared_params.and_operation import AndOperation
from ..shared_params.contains_operation import ContainsOperation
