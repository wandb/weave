"""Request and response types for the Weave Agents observability API.

Weave Agents groups OpenTelemetry GenAI spans into a higher-level model that
mirrors how agentic applications actually run. The same shapes flow through
every layer of the stack: the FastAPI endpoints in `services/weave-trace`,
the ClickHouse query handlers in
`weave/trace_server/clickhouse_trace_server_batched.py`, the in-memory
fake server, and the SDK bindings. Every type below is a Pydantic
`BaseModel` so requests validate on the way in and responses serialize the
same way on every backend.

Domain model
------------
* **Agent** — an agentic application identified by `agent_name`. Multiple
  versions and traces roll up under one agent.
* **Agent version** — an `(agent_name, agent_version)` pair. Versions let
  you compare behavior across releases of the same agent.
* **Span** — a single OpenTelemetry GenAI span. Each span captures one unit
  of work: an agent invocation, an LLM call, a tool execution, a context
  compaction, and so on.
* **Turn** — the chat-style trajectory of one trace. A turn is the linear
  sequence of user, assistant, tool, and lifecycle messages that explains
  what happened from the user's prompt through the final response.
* **Conversation** — an ordered list of turns sharing the same
  `conversation_id`. Conversations let you replay a multi-turn dialog as it
  appeared to the user.

For the user-facing concepts and instrumentation patterns, see
https://docs.wandb.ai/weave/guides/tracking/trace-agents.

Request and response pairs
--------------------------
The query endpoints come in `*Req`/`*Res` pairs that share the same
prefix. Common pairings:

* List agents — `AgentsQueryReq` -> `AgentsQueryRes`
* List versions — `AgentVersionsQueryReq` -> `AgentVersionsQueryRes`
* List or aggregate spans — `AgentSpansQueryReq` -> `AgentSpansQueryRes`
* Chart-ready stats — `AgentSpanStatsReq` -> `AgentSpanStatsRes`
* Single-trace chat view — `AgentTraceChatReq` -> `AgentTraceChatRes`
* Multi-turn chat view — `AgentConversationChatReq` ->
  `AgentConversationChatRes`
* Message search — `AgentSearchReq` -> `AgentSearchRes`
* Custom attribute discovery — `AgentCustomAttrsSchemaReq` ->
  `AgentCustomAttrsSchemaRes`
* OTel ingest — `GenAIOTelExportReq` -> `GenAIOTelExportRes`
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from weave.trace_server.agents import semconv
from weave.trace_server.agents.constants import (
    DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT,
    DEFAULT_AGENT_QUERY_LIMIT,
    DEFAULT_AGENT_STATS_GROUP_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_BINS,
    MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_SPECS,
    MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_TOP_N,
    MAX_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT,
    MAX_AGENT_QUERY_LIMIT,
    MAX_AGENT_STATS_GROUP_LIMIT,
    MAX_AGENT_STATS_RANGE_DAYS,
    MAX_CONVERSATION_CHAT_TURNS,
    MAX_SEARCH_LIMIT,
    SPAN_GROUP_RESULT_COLS,
)
from weave.trace_server.agents.schema import (
    NormalizedMessage,
    SpanKindLiteral,
    StatusCodeLiteral,
)
from weave.trace_server.interface.query import Query

if TYPE_CHECKING:
    from weave.trace_server.trace_server_interface import ProcessedResourceSpans
else:
    ProcessedResourceSpans = Any

SearchMessageRole = Literal[
    "",
    "user",
    "assistant",
    "system",
    "tool",
    "tool_call",
    "tool_result",
]

AgentSpanStatsValueType = Literal["datetime", "number", "boolean", "string"]
AgentSpanStatsColumnValueType = Literal["datetime", "number", "boolean", "string"]
AgentSpanStatsCell = datetime.datetime | str | int | float | bool | None
AgentSpanStatsAggregation = Literal[
    "sum",
    "avg",
    "min",
    "max",
    "count",
    "count_distinct",
    "count_true",
    "count_false",
]
AgentSpanStatsDerivedMetric = Literal[
    "duration_ms",
    "total_tokens",
    "is_error",
    "is_invocation",
    # Query-time costs (USD). Computed by joining the span's model against
    # llm_token_prices; only resolvable when the query's span source is
    # cost-augmented. Mirror of span_costs.COST_DERIVED_METRIC_NAMES — keep the
    # two in sync. See weave/trace_server/agents/span_costs.py.
    "total_cost_usd",
    "input_cost_usd",
    "output_cost_usd",
]
AgentSpanValueSource = Literal[
    "field",
    "derived",
    "custom_attrs_string",
    "custom_attrs_int",
    "custom_attrs_float",
    "custom_attrs_bool",
]
AgentCustomAttrSource = Literal[
    "custom_attrs_string",
    "custom_attrs_int",
    "custom_attrs_float",
    "custom_attrs_bool",
]
AgentCustomAttrValueType = Literal["string", "int", "float", "bool"]
AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES: dict[
    AgentCustomAttrSource, AgentCustomAttrValueType
] = {
    "custom_attrs_string": "string",
    "custom_attrs_int": "int",
    "custom_attrs_float": "float",
    "custom_attrs_bool": "bool",
}
AGENT_CUSTOM_ATTR_SOURCES: frozenset[AgentCustomAttrSource] = frozenset(
    AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES
)

_IDENT_RE = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
# AgentGroupByRef sources that resolve to a plain span column rather than a
# typed custom-attribute map; used to pick alias/value resolution paths.
_FIELD_GROUP_BY_SOURCES = {"field", "column"}
AGENT_SPAN_STATS_DERIVED_VALUE_TYPES: dict[
    AgentSpanStatsDerivedMetric, AgentSpanStatsValueType
] = {
    "duration_ms": "number",
    "total_tokens": "number",
    "is_error": "boolean",
    "is_invocation": "boolean",
    "total_cost_usd": "number",
    "input_cost_usd": "number",
    "output_cost_usd": "number",
}
_ALLOWED_AGGS_BY_TYPE: dict[AgentSpanStatsValueType, set[AgentSpanStatsAggregation]] = {
    "datetime": {"min", "max", "count", "count_distinct"},
    "number": {"sum", "avg", "min", "max", "count", "count_distinct"},
    "boolean": {"count", "count_distinct", "count_true", "count_false"},
    "string": {"count", "count_distinct"},
}


def _derived_value_type(key: str) -> AgentSpanStatsValueType:
    for metric, value_type in AGENT_SPAN_STATS_DERIVED_VALUE_TYPES.items():
        if metric == key:
            return value_type
    raise ValueError(f"unknown derived span value: {key!r}")


def _as_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class AgentSpanValueRef(BaseModel):
    """Reference to a value pulled out of an agent span.

    The same pointer shows up wherever a stats, group, or distribution
    expression has to name "the thing to read off a span." Set `source`
    to choose where the value comes from, then `key` to choose which one:

    * `field` — a semconv span field like `agent.name` or a direct span
      column like `agent_name`. The query builder resolves the alias.
    * `derived` — a query-time derived metric whose name appears in
      `AGENT_SPAN_STATS_DERIVED_VALUE_TYPES` (for example, `duration_ms`,
      `total_tokens`, or one of the `*_cost_usd` keys).
    * `custom_attrs_string` / `custom_attrs_int` / `custom_attrs_float` /
      `custom_attrs_bool` — a user-defined key inside the matching typed
      custom attribute Map column on the span row.

    Used by `AgentSpanMeasureSpec`, `AgentSpanStatsMetricSpec`,
    `AgentSpanGroupDistributionSpec`, and the bucket specs to point at
    a single value per span.

    Raises:
        ValueError: When `source` is `derived` but `key` isn't a known
            derived metric.
    """

    source: AgentSpanValueSource = "field"
    key: str

    @model_validator(mode="after")
    def validate_value_ref(self) -> AgentSpanValueRef:
        if (
            self.source == "derived"
            and self.key not in AGENT_SPAN_STATS_DERIVED_VALUE_TYPES
        ):
            raise ValueError(f"unknown derived span value: {self.key!r}")
        return self


class AgentSpanMeasureSpec(BaseModel):
    """One aggregate measure computed across the spans in a group or bucket.

    A measure pairs an `AgentSpanValueRef` with an aggregation function so the
    server can roll a column up to a single number per group or bucket. Use
    it on `AgentSpansQueryReq.measures` for grouped span queries and on
    `AgentSpanGroupFilter.measure` for "spans where the aggregated value is
    in this range" filters.

    Attributes:
        alias: Output column name. Must be a valid Python-style identifier
            and must not collide with the reserved aggregate fields on
            `AgentSpanGroupRow`.
        aggregation: Aggregation function. `count` is the only one that may
            omit `value`. The allowed set depends on `value_type`: see
            `_ALLOWED_AGGS_BY_TYPE` for the mapping.
        value: The span value to aggregate. Required for every aggregation
            except `count`.
        value_type: The expected type of `value` (`number`, `boolean`,
            `string`, or `datetime`). Used to enforce that the chosen
            aggregation is legal for the column type. Optional for `count`
            measures and for derived metrics whose type is already known.
        filter: Optional Mongo-style `Query` restricting which spans
            contribute to this measure. Applied on top of the request-level
            filter.

    Raises:
        ValueError: When the combination of `aggregation`, `value`, and
            `value_type` isn't internally consistent (for example, a `sum`
            measure with no `value`, or an `avg` on a `string` column).
    """

    alias: str = Field(pattern=_IDENT_RE)
    aggregation: AgentSpanStatsAggregation
    value: AgentSpanValueRef | None = None
    value_type: AgentSpanStatsValueType | None = None
    filter: Query | None = None

    @model_validator(mode="after")
    def validate_measure_spec(self) -> AgentSpanMeasureSpec:
        if self.value is None and self.aggregation != "count":
            raise ValueError("only count measures may omit value")

        if self.value is not None and self.value.source == "derived":
            expected_type = _derived_value_type(self.value.key)
            if self.value_type is not None and self.value_type != expected_type:
                raise ValueError(
                    f"derived value {self.value.key!r} has value_type "
                    f"{expected_type!r}, got {self.value_type!r}"
                )

        if self.value_type is not None:
            allowed = _ALLOWED_AGGS_BY_TYPE[self.value_type]
            if self.aggregation not in allowed:
                raise ValueError(
                    f"aggregation {self.aggregation!r} is not valid for "
                    f"value_type {self.value_type!r}"
                )
        elif self.aggregation in {"sum", "avg", "min", "max", "count_distinct"}:
            if self.value is None:
                raise ValueError(f"aggregation {self.aggregation!r} requires a value")

        return self


class AgentSpanStatsMetricSpec(BaseModel):
    """One metric to chart from agent spans across buckets and groups.

    Pass these on `AgentSpanStatsReq.metrics` to drive the stats endpoint.
    Each spec emits one column per (aggregation or percentile) in the
    response `AgentSpanStatsRes.rows`, named `{alias}__{aggregation}` or
    `{alias}__p{percentile}`.

    Attributes:
        alias: Stable prefix for the column names this metric produces. Must
            be a valid Python-style identifier.
        value_type: Type of the underlying span value. The server uses it to
            validate the chosen aggregations and to type response cells.
        aggregations: Aggregation functions to compute. When both
            `aggregations` and `percentiles` are empty, the server defaults
            to `sum` for `number` and `count` for everything else.
        percentiles: Percentile cutoffs, each in the closed interval
            `[0, 100]`. Only valid for `value_type="number"`. Use this
            instead of `aggregations` when you want quantile lines on the
            chart.
        value: Span value pointer the aggregations apply to.

    Raises:
        ValueError: When aggregations don't match `value_type`, when
            percentiles are out of range or non-unique, or when percentiles
            are requested for a non-numeric metric.
    """

    alias: str = Field(pattern=_IDENT_RE)
    value_type: AgentSpanStatsValueType
    aggregations: list[AgentSpanStatsAggregation] = Field(default_factory=list)
    percentiles: list[float] = Field(default_factory=list)
    value: AgentSpanValueRef

    @model_validator(mode="after")
    def validate_metric_spec(self) -> AgentSpanStatsMetricSpec:
        if self.value.source == "derived":
            expected_type = _derived_value_type(self.value.key)
            if self.value_type != expected_type:
                raise ValueError(
                    f"derived metric {self.value.key!r} has value_type "
                    f"{expected_type!r}, got {self.value_type!r}"
                )

        allowed = _ALLOWED_AGGS_BY_TYPE[self.value_type]
        invalid_aggs = [agg for agg in self.aggregations if agg not in allowed]
        if invalid_aggs:
            raise ValueError(
                f"aggregations {invalid_aggs!r} are not valid for "
                f"value_type {self.value_type!r}"
            )
        if len(set(self.aggregations)) != len(self.aggregations):
            raise ValueError("metric aggregations must be unique")

        if self.percentiles:
            if self.value_type != "number":
                raise ValueError("percentiles are only valid for number metrics")
            invalid_percentiles = [p for p in self.percentiles if p < 0 or p > 100]
            if invalid_percentiles:
                raise ValueError(
                    f"percentiles must be between 0 and 100, got "
                    f"{invalid_percentiles!r}"
                )
            if len(set(self.percentiles)) != len(self.percentiles):
                raise ValueError("metric percentiles must be unique")

        if not self.aggregations and not self.percentiles:
            self.aggregations = ["sum"] if self.value_type == "number" else ["count"]

        return self


class AgentSpanStatsColumn(BaseModel):
    """Schema for one column in an `AgentSpanStatsRes` row.

    Stats responses are returned as untyped dict rows so the wire format
    stays compact; this column list tells clients how to label and render
    each cell.

    Attributes:
        name: Key used in `AgentSpanStatsRes.rows[i]`.
        role: Where the column came from. `time` is the time bucket
            boundary, `bucket` is a numeric bucket boundary, `group` is a
            group-by ref, and `metric` is one aggregation or percentile of a
            metric spec.
        value_type: Cell type for this column.
        metric: Originating metric `alias` for `metric` columns. `None`
            for `time`, `bucket`, and `group` columns.
        aggregation: Aggregation function (or `pNN` percentile label) for
            `metric` columns. `None` for the other roles.
    """

    name: str
    role: Literal["time", "bucket", "group", "metric"]
    value_type: AgentSpanStatsColumnValueType
    metric: str | None = None
    aggregation: str | None = None


class AgentSpanGroupFilter(BaseModel):
    """Range filter over an aggregated measure of a span group.

    Use this to keep groups whose aggregated measure falls inside a
    numeric or datetime range. For example: "agents whose error count is
    between 5 and 100" or "conversations whose first span happened after
    yesterday." At least one of `min` or `max` must be set; when both are
    set they must have matching types and `max` must be greater than or
    equal to `min`.

    Attributes:
        group_by: Optional override for the grouping used by this filter.
            When empty, the filter reuses the surrounding request's
            grouping.
        measure: The aggregated measure the range applies to.
        min: Lower bound, inclusive. `None` means no lower bound.
        max: Upper bound, inclusive. `None` means no upper bound.

    Raises:
        ValueError: When both bounds are `None`, when `min` and `max`
            have different types, or when `max < min`.
    """

    group_by: list[AgentGroupByRef] = Field(default_factory=list)
    measure: AgentSpanMeasureSpec
    min: float | datetime.datetime | None = None
    max: float | datetime.datetime | None = None

    @model_validator(mode="after")
    def validate_group_filter(self) -> AgentSpanGroupFilter:
        if self.min is None and self.max is None:
            raise ValueError("group filter must set min or max")
        if self.min is not None and self.max is not None:
            min_value = self.min
            max_value = self.max
            if isinstance(min_value, datetime.datetime):
                if not isinstance(max_value, datetime.datetime):
                    raise TypeError("group filter min and max must use the same type")
                if max_value < min_value:
                    raise ValueError("group filter max must be greater than min")
            else:
                if isinstance(max_value, datetime.datetime):
                    raise TypeError("group filter min and max must use the same type")
                if max_value < min_value:
                    raise ValueError("group filter max must be greater than min")
        return self


class AgentSpanStatsTimeBucketSpec(BaseModel):
    """Bucket stats rows by `started_at` time intervals.

    This is the default bucket type for time-series charts. The bucket
    width is taken from `AgentSpanStatsReq.granularity` (in seconds) or
    chosen by the server when granularity is `None`.

    See also `AgentSpanStatsNumericBucketSpec` for histogram-style charts.
    """

    type: Literal["time"] = "time"


class AgentSpanStatsNumericBucketSpec(BaseModel):
    """Bucket stats rows along a numeric axis instead of time.

    Use this for histograms and grouped distribution charts. Set either
    `value` (histogram of a per-span value) or the `group_by` and `measure`
    pair (histogram of an aggregated measure across groups), but not both.
    `bins` defines how many equal-width buckets cover the `[min, max]`
    range; `min` and `max` default to the data range when omitted.

    Attributes:
        alias: Column name for the bucket boundary in the response.
        bins: Bucket count, between 1 and 200.
        min: Lower bound of the histogram. `None` lets the server use the
            data minimum.
        max: Upper bound of the histogram. `None` lets the server use the
            data maximum.
        value: Numeric span value to bucket. Mutually exclusive with the
            `group_by`/`measure` pair.
        group_by: Group-by refs whose aggregated measure should be
            bucketed. Required together with `measure`.
        measure: Aggregated measure to bucket. Required together with
            `group_by`.

    Raises:
        ValueError: When `value` and the grouped pair are both set or both
            unset, when only one of `group_by`/`measure` is set, when the
            referenced value or measure isn't numeric, or when
            `max < min`.
    """

    type: Literal["number"] = "number"
    alias: str = Field(default="value", pattern=_IDENT_RE)
    bins: int = Field(default=24, ge=1, le=200)
    min: float | None = None
    max: float | None = None
    value: AgentSpanValueRef | None = None
    group_by: list[AgentGroupByRef] = Field(default_factory=list)
    measure: AgentSpanMeasureSpec | None = None

    @model_validator(mode="after")
    def validate_numeric_bucket_spec(self) -> AgentSpanStatsNumericBucketSpec:
        sources = [
            self.value is not None,
            bool(self.group_by) or self.measure is not None,
        ]
        if sum(sources) != 1:
            raise ValueError("exactly one of value or group_by/measure must be set")
        if bool(self.group_by) != (self.measure is not None):
            raise ValueError("numeric group bucket must set both group_by and measure")

        if self.value is not None:
            if self.value.source == "derived":
                expected_type = _derived_value_type(self.value.key)
                if expected_type != "number":
                    raise ValueError(
                        f"derived bucket value {self.value.key!r} has value_type "
                        f"{expected_type!r}, expected 'number'"
                    )
            elif self.value.source not in {"custom_attrs_int", "custom_attrs_float"}:
                # Field refs are validated against storage metadata in the query
                # builder because semconv aliases resolve there.
                if self.value.source != "field":
                    raise ValueError("numeric bucket value must be numeric")
        if self.measure is not None:
            measure_type = self.measure.value_type
            if (
                self.measure.aggregation not in {"count", "count_distinct"}
                and measure_type is not None
                and measure_type != "number"
            ):
                raise ValueError("numeric group bucket measure must produce a number")

        if self.min is not None and self.max is not None and self.max < self.min:
            raise ValueError("numeric bucket max must be greater than or equal to min")

        return self


AgentSpanStatsBucketSpec = Annotated[
    AgentSpanStatsTimeBucketSpec | AgentSpanStatsNumericBucketSpec,
    Field(discriminator="type"),
]


class AgentSpanStatsReq(BaseModel):
    """Request chart-ready aggregations over agent spans.

    Powers time-series and histogram visualizations in the Agents view. The
    server filters spans by `query` and the `[start, end)` window, buckets
    them according to `bucket_by` (defaulting to time buckets at
    `granularity` seconds), optionally groups within each bucket by
    `group_by`, and then computes the metrics.

    Pair with `AgentSpanStatsRes` for the result shape.

    Attributes:
        project_id: Target Weave project, in `entity/project` form.
        query: Optional Mongo-style filter. Fields resolve via the GenAI
            semantic conventions, direct span columns, or typed custom
            attribute keys.
        start: Window start, inclusive. Naive datetimes are interpreted as
            UTC.
        end: Window end, exclusive. Defaults to "now (UTC)" when omitted.
        granularity: Width of each time bucket in seconds. The server picks
            a sensible default when `None`. Ignored for numeric buckets.
        timezone: IANA timezone name for any time-of-day grouping in the
            response. Defaults to `UTC`.
        group_by: Group spans within each bucket by these refs. Mutually
            exclusive with `bucket_by` set to a numeric bucket spec.
        metrics: Metrics to compute per bucket and group. Required unless
            `bucket_by` is a numeric bucket spec that already produces
            counts.
        group_limit: Maximum groups returned per bucket, between 1 and
            `MAX_AGENT_STATS_GROUP_LIMIT`.
        bucket_by: How to bucket rows. `None` is equivalent to
            `AgentSpanStatsTimeBucketSpec()`.
        group_filters: Range filters over aggregated measures. Only
            supported for time buckets and grouped numeric buckets.

    Raises:
        ValueError: When metrics are missing, when metric aliases are
            duplicated, when `end < start`, when the date range exceeds
            `MAX_AGENT_STATS_RANGE_DAYS` for grouped requests, or when
            `group_by`, `metrics`, and `bucket_by` combine incompatibly.
    """

    project_id: str
    query: Query | None = None
    start: datetime.datetime
    end: datetime.datetime | None = None
    granularity: int | None = Field(default=None, gt=0)
    timezone: str = "UTC"
    group_by: list[AgentGroupByRef] = Field(default_factory=list)
    metrics: list[AgentSpanStatsMetricSpec] = Field(default_factory=list)
    group_limit: int = Field(
        default=DEFAULT_AGENT_STATS_GROUP_LIMIT,
        ge=1,
        le=MAX_AGENT_STATS_GROUP_LIMIT,
    )
    bucket_by: AgentSpanStatsBucketSpec | None = None
    group_filters: list[AgentSpanGroupFilter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stats_request(self) -> AgentSpanStatsReq:
        numeric_bucket = (
            self.bucket_by
            if isinstance(self.bucket_by, AgentSpanStatsNumericBucketSpec)
            else None
        )
        if not self.metrics and numeric_bucket is None:
            raise ValueError("at least one metric is required")

        aliases = [metric.alias for metric in self.metrics]
        duplicate_aliases = sorted(
            {alias for alias in aliases if aliases.count(alias) > 1}
        )
        if duplicate_aliases:
            raise ValueError(f"duplicate metric aliases: {duplicate_aliases!r}")

        self.start = _as_utc(self.start)
        if self.end is not None:
            self.end = _as_utc(self.end)

        end = self.end or datetime.datetime.now(datetime.timezone.utc)
        if end < self.start:
            raise ValueError("AgentSpanStatsReq end must be after start")
        # Unfiltered, ungrouped requests are not bound by
        # MAX_AGENT_STATS_RANGE_DAYS.
        apply_max_range_days = (
            bool(self.group_by)
            or bool(self.group_filters)
            or numeric_bucket is not None
        )
        max_range = datetime.timedelta(days=MAX_AGENT_STATS_RANGE_DAYS)
        if apply_max_range_days and end - self.start > max_range:
            raise ValueError(
                "AgentSpanStatsReq date range cannot exceed "
                f"{MAX_AGENT_STATS_RANGE_DAYS} days"
            )

        if numeric_bucket is not None and self.group_by:
            raise ValueError("numeric bucket stats do not support group_by")
        if numeric_bucket is not None and numeric_bucket.group_by and self.metrics:
            raise ValueError(
                "grouped numeric bucket stats do not support explicit metrics"
            )
        if self.group_filters:
            if self.group_by:
                raise ValueError("group_filters do not support group_by")
            if numeric_bucket is not None and not numeric_bucket.group_by:
                raise ValueError(
                    "group_filters are only supported for time stats or "
                    "grouped numeric bucket stats"
                )
        return self


class AgentSpanStatsRes(BaseModel):
    """Response containing chart-ready agent span stats rows.

    `columns` is the schema you use to interpret each cell in `rows`. The
    `start`, `end`, `granularity`, and `timezone` fields echo back what the
    server actually applied so clients can render axes without re-deriving
    them. Empty buckets are omitted from `rows`.

    See `AgentSpanStatsReq` for the request side and `AgentSpanStatsColumn`
    for the column schema.
    """

    start: datetime.datetime
    end: datetime.datetime
    granularity: int | None = None
    timezone: str
    bucket_type: Literal["time", "number"] = "time"
    columns: list[AgentSpanStatsColumn] = Field(default_factory=list)
    rows: list[dict[str, AgentSpanStatsCell]] = Field(default_factory=list)


class AgentSpanSchema(BaseModel):
    """A normalized agent span row returned by the spans query APIs.

    One `AgentSpanSchema` represents one OpenTelemetry GenAI span after
    the server has folded the raw OTel payload into Weave's flattened
    column layout. Same shape regardless of the original instrumentation:
    `weave.start_session()` / `weave.start_turn()` / `weave.start_llm()` /
    `weave.start_tool()`, an OTel exporter, or one of the autopatched
    integrations.

    Many fields are `None` when the producing span didn't emit the
    corresponding GenAI attribute. List fields default to empty.

    Attributes:
        project_id: Owning Weave project in `entity/project` form.
        trace_id: OTel trace ID this span belongs to. All spans in one
            turn share a `trace_id`.
        span_id: OTel span ID. Unique within the trace.
        parent_span_id: Parent span's `span_id`, or `None` for root
            spans.
        span_name: OTel span name, for example `chat gpt-4o` or
            `execute_tool search`.
        span_kind: OTel span kind. `Server`, `Client`, `Internal`, and
            so on.
        started_at: Span start time. UTC.
        ended_at: Span end time. UTC.
        status_code: OTel status. `Ok`, `Error`, or `Unset`.
        status_message: Human-readable status detail (typically the error
            message when `status_code == "Error"`).
        operation_name: GenAI `gen_ai.operation.name`. For example,
            `invoke_agent`, `chat`, or `execute_tool`.
        provider_name: GenAI `gen_ai.provider.name`. For example,
            `openai`, `anthropic`, or `bedrock`.
        agent_name: Agent identifier this span belongs to.
        agent_id: Stable agent ID emitted by the SDK, if any.
        agent_description: Free-form description set on the agent.
        agent_version: Agent version string for grouping by release.
        request_model: Model requested for the LLM call.
        response_model: Model the provider reports actually served the
            response.
        response_id: Provider's response identifier.
        input_tokens: Prompt token count reported by the provider.
        output_tokens: Completion token count reported by the provider.
        reasoning_tokens: Reasoning token count for reasoning-capable
            models.
        cache_creation_input_tokens: Tokens written to a provider prompt
            cache during this call.
        cache_read_input_tokens: Tokens read back from a provider prompt
            cache during this call.
        input_cost_usd: Query-time input-token cost in USD. Populated
            only when `AgentSpansQueryReq.include_costs=True`. `None`
            (not `0`) signals that the span's model had no matching
            price.
        output_cost_usd: Query-time output-token cost in USD. Same
            opt-in and `None` semantics as `input_cost_usd`.
        cache_read_cost_usd: Query-time cost of cached prompt reads in
            USD. Same opt-in and `None` semantics.
        cache_creation_cost_usd: Query-time cost of writing into the
            prompt cache in USD. Same opt-in and `None` semantics.
        total_cost_usd: Sum of the per-direction cost fields above.
            Same opt-in and `None` semantics.
        reasoning_content: Reasoning text captured from a reasoning
            model's response, when available.
        conversation_id: GenAI `gen_ai.conversation.id`. Spans that share
            a `conversation_id` make up one conversation.
        conversation_name: Human-readable conversation label.
        tool_name: Tool name for `execute_tool` spans.
        tool_type: Optional tool classification.
        tool_call_id: ID of the originating `tool_use` request, for
            correlating an LLM's tool call with its execution span.
        tool_description: Tool description captured at call time.
        tool_definitions: Serialized tool catalog the model was given.
        finish_reasons: Provider-reported finish reasons, one per output
            choice.
        error_type: Exception type or provider error code for failed
            spans.
        request_temperature: Sampling temperature for the LLM call.
        request_max_tokens: Maximum completion tokens requested.
        request_top_p: Top-p (nucleus) sampling parameter.
        request_frequency_penalty: Frequency penalty for the LLM call.
        request_presence_penalty: Presence penalty for the LLM call.
        request_seed: Seed passed to the provider for deterministic
            sampling.
        request_stop_sequences: Stop sequences passed to the provider.
        request_choice_count: Number of completions requested.
        output_type: Provider-specific output format (for example,
            `text`, `json_object`).
        input_messages: Normalized input messages sent to the model.
        output_messages: Normalized output messages returned by the
            model.
        system_instructions: System prompts attached to the call.
        tool_call_arguments: JSON string of the tool call arguments for
            `execute_tool` spans.
        tool_call_result: Serialized tool result for `execute_tool`
            spans.
        compaction_summary: Summary text emitted by a context-window
            compaction event.
        compaction_items_before: Item count before compaction.
        compaction_items_after: Item count after compaction.
        content_refs: Refs to detached content blobs (large message
            content stored outside the row).
        artifact_refs: Refs to W&B artifacts attached to the span.
        object_refs: Refs to Weave objects attached to the span.
        custom_attrs_string: User-defined string attributes that didn't
            match a known semconv key.
        custom_attrs_int: User-defined integer attributes.
        custom_attrs_float: User-defined float attributes.
        custom_attrs_bool: User-defined boolean attributes.
        server_address: Provider host or service address recorded on the
            span.
        server_port: Provider port recorded on the span.
        wb_user_id: W&B user who recorded the span.
        wb_run_id: Associated W&B run ID.
        wb_run_step: W&B run step at span start, when available.
        wb_run_step_end: W&B run step at span end, when available.
        raw_span_dump: Full OTel JSON payload for the span. Populated
            only when `AgentSpansQueryReq.include_details=True`.

    See `AgentSpansQueryReq` for the request side and `NormalizedMessage`
    for the shape of message entries.
    """

    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    # TODO: Audit partial-row callers and make this required if every API path
    # can rely on ClickHouse's non-null span_name column.
    span_name: str | None = None
    span_kind: SpanKindLiteral | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    status_code: StatusCodeLiteral | None = None
    status_message: str | None = None
    operation_name: str | None = None
    provider_name: str | None = None
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None
    agent_version: str | None = None
    request_model: str | None = None
    response_model: str | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    # Query-time costs (USD), only populated when AgentSpansQueryReq.include_costs
    # is set. None (not 0) when the span's model has no matching price, so the UI
    # can distinguish "unpriced" from "free". See agents/span_costs.py.
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    cache_read_cost_usd: float | None = None
    cache_creation_cost_usd: float | None = None
    total_cost_usd: float | None = None
    reasoning_content: str | None = None
    conversation_id: str | None = None
    conversation_name: str | None = None
    tool_name: str | None = None
    tool_type: str | None = None
    tool_call_id: str | None = None
    tool_description: str | None = None
    tool_definitions: str | None = None
    finish_reasons: list[str] = Field(default_factory=list)
    error_type: str | None = None
    request_temperature: float | None = None
    request_max_tokens: int | None = None
    request_top_p: float | None = None
    request_frequency_penalty: float | None = None
    request_presence_penalty: float | None = None
    request_seed: int | None = None
    request_stop_sequences: list[str] = Field(default_factory=list)
    request_choice_count: int | None = None
    output_type: str | None = None
    input_messages: list[NormalizedMessage] = Field(default_factory=list)
    output_messages: list[NormalizedMessage] = Field(default_factory=list)
    system_instructions: list[str] = Field(default_factory=list)
    tool_call_arguments: str | None = None
    tool_call_result: str | None = None
    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None
    content_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    custom_attrs_string: dict[str, str] = Field(default_factory=dict)
    custom_attrs_int: dict[str, int] = Field(default_factory=dict)
    custom_attrs_float: dict[str, float] = Field(default_factory=dict)
    custom_attrs_bool: dict[str, bool] = Field(default_factory=dict)
    server_address: str | None = None
    server_port: int | None = None
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None
    # Only populated when AgentSpansQueryReq.include_details is set; the raw
    # OTel JSON dump for the span is large, so it's omitted from list queries
    # by default.
    raw_span_dump: str | None = None


class AgentSortBy(BaseModel):
    """Sort specification for the agent list endpoints.

    Passed to `AgentSpansQueryReq.sort_by`, `AgentsQueryReq.sort_by`, and
    `AgentVersionsQueryReq.sort_by` as an ordered list. Each entry sorts on
    one field; entries are applied left to right.

    Attributes:
        field: Sortable field name. Allowed values are validated per
            endpoint server-side.
        direction: `desc` (default) for newest or largest first, `asc`
            for oldest or smallest first.
    """

    field: str
    direction: Literal["asc", "desc"] = "desc"


class AgentGroupByRef(BaseModel):
    """Reference to a span field or custom attribute key to group by.

    Pass these on `AgentSpansQueryReq.group_by` and
    `AgentSpanStatsReq.group_by` to roll spans up by a column or by a
    user-defined attribute. The aggregated values land in
    `AgentSpanGroupRow.group_keys` keyed by `alias` (or by the resolved
    column name when `alias` is omitted).

    Attributes:
        source: Where the value lives. `field` targets an allowlisted
            semantic span field (`agent.name`) or direct span column
            (`agent_name`); `column` is the legacy alias and behaves the
            same. The four `custom_attrs_*` sources target keys inside
            the matching typed custom attribute Map column on the span
            row.
        key: For `field` and `column`, the canonical field name. For
            `custom_attrs_*`, the user-defined key inside the map.
        alias: Output key in `AgentSpanGroupRow.group_keys`. When `None`,
            the server falls back to the resolved column or the raw
            `key`.

    Use `group_by_ref_alias` to compute the actual output alias for a
    ref without rebuilding the resolution logic.
    """

    source: Literal[
        "field",
        "column",
        "custom_attrs_string",
        "custom_attrs_int",
        "custom_attrs_float",
        "custom_attrs_bool",
    ] = "field"
    key: str
    alias: str | None = None  # output key in AgentSpanGroupRow.group_keys


def group_by_ref_alias(ref: AgentGroupByRef) -> str:
    """Return the output alias the server uses for a group-by ref.

    The request validator and the SQL projection both call this so both
    sides agree on what key shows up in `AgentSpanGroupRow.group_keys`.

    Args:
        ref: A group-by ref from `AgentSpansQueryReq.group_by` or
            `AgentSpanStatsReq.group_by`.

    Returns:
        The explicit `alias` when set, the semconv-resolved column name
        for `field`/`column` sources, or the raw `key` otherwise.
    """
    if ref.alias is not None:
        return ref.alias
    if ref.source in _FIELD_GROUP_BY_SOURCES:
        return semconv.FILTERABLE_KEY_TO_COLUMN.get(ref.key, ref.key)
    return ref.key


class AgentSpanGroupDistributionSpec(BaseModel):
    """A custom attribute distribution to compute per returned span group.

    For each span group in `AgentSpansQueryRes.groups`, the server adds an
    `AgentSpanGroupDistributionItem` summarizing the values observed for
    one custom attribute. Numeric attributes are returned as a histogram of
    up to `bins` equal-width buckets, and string/boolean attributes as the
    `top_n` most common values.

    Attributes:
        alias: Output key for this distribution in
            `AgentSpanGroupRow.distributions`.
        value: Pointer to the custom attribute. Must use a
            `custom_attrs_*` source.
        bins: Histogram bin count for numeric attributes, between 1 and
            `MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_BINS`. Ignored for
            categorical attributes.
        top_n: Maximum categorical values returned, between 1 and
            `MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_TOP_N`. Ignored for
            numeric histograms.

    Raises:
        ValueError: When `value.source` isn't one of the
            `custom_attrs_*` sources.
    """

    alias: str = Field(pattern=_IDENT_RE)
    value: AgentSpanValueRef
    bins: int = Field(default=12, ge=1, le=MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_BINS)
    top_n: int = Field(default=5, ge=1, le=MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_TOP_N)

    @model_validator(mode="after")
    def validate_distribution_spec(self) -> AgentSpanGroupDistributionSpec:
        if self.value.source not in AGENT_CUSTOM_ATTR_SOURCES:
            raise ValueError("distribution specs must reference custom attr sources")
        return self

    def custom_attr_source(self) -> AgentCustomAttrSource:
        """Return ``value.source`` narrowed to ``AgentCustomAttrSource``.

        The model validator guarantees this at construction time; this helper
        re-checks each literal so callers avoid `cast()` at use sites.
        """
        source = self.value.source
        if source == "custom_attrs_string":
            return source
        if source == "custom_attrs_int":
            return source
        if source == "custom_attrs_float":
            return source
        if source == "custom_attrs_bool":
            return source
        raise ValueError(f"distribution spec source is not custom attr: {source!r}")


class AgentSpanGroupDistributionBin(BaseModel):
    """One bucket of a numeric custom attribute histogram in a span group.

    Attributes:
        index: 0-based bucket position within the histogram. Clients
            render bins in `index` order, so it doubles as a stable sort
            key.
        min: Lower bound of the bucket, inclusive.
        max: Upper bound of the bucket, exclusive (inclusive on the final
            bucket).
        count: Number of spans with values that fell inside the bucket.
    """

    index: int
    min: float
    max: float
    count: int


class AgentSpanGroupDistributionValue(BaseModel):
    """One categorical custom attribute value count in a span group.

    Attributes:
        value: The observed attribute value, stringified.
        count: How many spans in the group had this value.
    """

    value: str
    count: int


class AgentSpanGroupDistributionItem(BaseModel):
    """Distribution data for one span-group / custom-attribute pair.

    Returned inside `AgentSpanGroupRow.distributions` keyed by the
    distribution spec's `alias`. Numeric attributes populate `bins`;
    categorical attributes populate `values`. The four `*_count` fields
    are always populated and sum to `total_count`.

    Attributes:
        alias: Echoes `AgentSpanGroupDistributionSpec.alias`.
        source: The custom attribute source that produced this
            distribution.
        key: The attribute key inside the source map.
        value_type: Inferred attribute type.
        total_count: Total spans evaluated for the distribution.
        present_count: Spans where the attribute was set.
        missing_count: Spans where the attribute was absent.
        other_count: Spans whose values fell outside `bins` or below the
            `top_n` cutoff.
        bins: Histogram bins for numeric attributes. Empty for
            categorical attributes.
        values: Top categorical values for string and boolean
            attributes. Empty for numeric attributes.
    """

    alias: str
    source: AgentCustomAttrSource
    key: str
    value_type: AgentCustomAttrValueType
    total_count: int = 0
    present_count: int = 0
    missing_count: int = 0
    other_count: int = 0
    bins: list[AgentSpanGroupDistributionBin] = Field(default_factory=list)
    values: list[AgentSpanGroupDistributionValue] = Field(default_factory=list)


class AgentConversationMessagePreview(BaseModel):
    """A truncated first or last message snippet on a conversation group row.

    Populated on `AgentSpanGroupRow.first_message` and `last_message` when
    grouping by `conversation_id`, so the conversation list can render
    teaser text without a follow-up hydration query.

    Attributes:
        role: Chat-timeline message type (for example, `user_message` or
            `assistant_message`). Matches the values used in
            `AgentChatMessage.type` so clients can style previews like
            the full chat view.
        text: Trimmed, length-capped preview content. Empty when no
            renderable text was available.
    """

    role: str = ""
    text: str = ""


class AgentSpanGroupRow(BaseModel):
    """One aggregated row in a grouped `AgentSpansQueryRes`.

    Returned in `AgentSpansQueryRes.groups` when the request supplies
    `group_by`. The fixed aggregate bundle is always present; `metrics`
    and `distributions` are populated when the request asks for measures
    or distribution specs.

    Attributes:
        group_keys: Group-by values for this row, keyed by each ref's
            alias (see `group_by_ref_alias`).
        span_count: Total spans in the group.
        invocation_count: Spans where `operation_name == "invoke_agent"`
            (turns and sub-agent invocations).
        conversation_count: Distinct `conversation_id` values.
        total_input_tokens: Sum of `input_tokens`.
        total_cache_creation_input_tokens: Sum of
            `cache_creation_input_tokens`.
        total_cache_read_input_tokens: Sum of `cache_read_input_tokens`.
        total_output_tokens: Sum of `output_tokens`.
        total_reasoning_tokens: Sum of `reasoning_tokens`.
        total_duration_ms: Sum of span wall-clock durations in
            milliseconds.
        error_count: Spans with `status_code == "Error"`.
        total_cost_usd: Sum of `total_cost_usd` across the group's
            spans. Populated only when
            `AgentSpansQueryReq.include_costs=True`. `None` (not `0`)
            signals that no span in the group had a matching model
            price.
        total_input_cost_usd: Sum of `input_cost_usd`. Same opt-in and
            `None` semantics.
        total_output_cost_usd: Sum of `output_cost_usd`. Same opt-in and
            `None` semantics.
        agent_names: Distinct `agent_name` values seen in the group.
        agent_versions: Distinct `agent_version` values.
        provider_names: Distinct `provider_name` values.
        request_models: Distinct `request_model` values.
        conversation_names: Distinct `conversation_name` values.
        first_seen: Earliest `started_at` in the group.
        last_seen: Latest `started_at` in the group.
        first_message: Preview of the earliest renderable message in the
            group. Populated only when grouping by `conversation_id`.
        last_message: Preview of the latest renderable message in the
            group. Populated only when grouping by `conversation_id`.
        metrics: Per-measure aggregates keyed by
            `AgentSpanMeasureSpec.alias`.
        distributions: Per-distribution data keyed by
            `AgentSpanGroupDistributionSpec.alias`.
    """

    group_keys: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    span_count: int = 0
    invocation_count: int = 0  # countIf(operation_name = 'invoke_agent')
    conversation_count: int = 0
    total_input_tokens: int = 0
    total_cache_creation_input_tokens: int = 0
    total_cache_read_input_tokens: int = 0
    total_output_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    # Summed query-time costs (USD) across the group's spans. Only populated
    # when AgentSpansQueryReq.include_costs is set; None when no span in the
    # group had a matching model price. See agents/span_costs.py.
    total_cost_usd: float | None = None
    total_input_cost_usd: float | None = None
    total_output_cost_usd: float | None = None
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    conversation_names: list[str] = Field(default_factory=list)
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None
    # First/last message previews, populated when grouping by conversation_id so
    # the conversations table needs no per-row hydration. None when the earliest/
    # latest span carried no renderable message text.
    first_message: AgentConversationMessagePreview | None = None
    last_message: AgentConversationMessagePreview | None = None
    metrics: dict[str, AgentSpanStatsCell] = Field(default_factory=dict)
    distributions: dict[str, AgentSpanGroupDistributionItem] = Field(
        default_factory=dict
    )


class AgentSpansQueryReq(BaseModel):
    """Request to list or aggregate agent spans for a project.

    The same endpoint covers two modes:

    * **List mode** (`group_by` empty or omitted): the response's `spans`
      list contains one `AgentSpanSchema` per matched span.
    * **Group mode** (`group_by` non-empty): the response's `groups`
      list contains one `AgentSpanGroupRow` per group, with optional
      `measures` and `distributions`.

    Use `include_details` for single-trace drill-downs (large payload),
    `include_costs` to attach query-time USD costs, and `custom_attr_columns`
    to project extra typed custom attributes alongside the standard columns.

    Pair with `AgentSpansQueryRes` for the result shape.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        query: Optional Mongo-style filter. Fields resolve via GenAI
            semantic conventions, direct span columns, or typed custom
            attribute keys.
        group_by: Group by these refs. Setting any group-only field
            (`measures`, `group_filters`, `group_distributions`) without
            also setting `group_by` is a validation error.
        measures: Aggregated measures to compute per group.
        group_filters: Range filters applied to aggregated measures.
        group_distributions: Per-group custom attribute distributions.
            Currently limited to one `group_by` ref.
        custom_attr_columns: Extra custom attribute values to project on
            each span row. Only valid in list mode.
        include_details: Include large fields (messages, tool payloads,
            `raw_span_dump`) on each span. Intended for single-trace
            detail fetches.
        include_costs: Compute query-time USD costs by joining each
            span's model against `llm_token_prices`. Adds the
            `*_cost_usd` fields to `AgentSpanSchema` rows or the
            `total_*_cost_usd` fields to `AgentSpanGroupRow` rows.
        sort_by: Sort order. Allowed fields are validated server-side.
        limit: Maximum rows returned, between 0 and
            `MAX_AGENT_QUERY_LIMIT`.
        offset: Number of rows to skip.
        started_after: Only include spans with `started_at >= start`.
        started_before: Only include spans with `started_at < end`.

    Raises:
        ValueError: When grouped-only fields are set without `group_by`,
            when `custom_attr_columns` or `include_details` is combined
            with `group_by`, when `group_distributions` has more than one
            `group_by` ref, or when measure/distribution aliases are
            duplicated or collide with reserved row fields.
    """

    project_id: str
    # Mongo-style filter expression. Field names resolve via semconv, direct
    # span columns, or the typed custom attribute Map columns.
    query: Query | None = None
    group_by: list[AgentGroupByRef] | None = None
    measures: list[AgentSpanMeasureSpec] = Field(default_factory=list)
    group_filters: list[AgentSpanGroupFilter] = Field(default_factory=list)
    group_distributions: list[AgentSpanGroupDistributionSpec] = Field(
        default_factory=list,
        max_length=MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_SPECS,
    )
    custom_attr_columns: list[AgentSpanValueRef] = Field(default_factory=list)
    # When true, include heavy fields (messages, tool payloads, raw_span_dump,
    # etc.) in each row. Intended for single-trace detail fetches; do not set
    # for broad list queries.
    include_details: bool = False
    # When true, compute per-span costs (USD) by joining each span's model
    # against llm_token_prices. Adds input_cost_usd/output_cost_usd/.../total_cost_usd to
    # ungrouped span rows, or summed total_cost_usd/total_input_cost_usd/
    # total_output_cost_usd to grouped rows. See agents/span_costs.py.
    include_costs: bool = False
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    started_after: datetime.datetime | None = None  # filter started_at >= start
    started_before: datetime.datetime | None = None  # filter started_at < end

    @model_validator(mode="after")
    def validate_spans_query_request(self) -> AgentSpansQueryReq:
        if (
            self.measures or self.group_filters or self.group_distributions
        ) and not self.group_by:
            raise ValueError(
                "grouped measures, distributions, and filters require group_by"
            )
        if self.group_distributions and len(self.group_by or []) != 1:
            raise ValueError("group_distributions currently support one group_by ref")
        if self.group_by and self.custom_attr_columns:
            raise ValueError(
                "custom_attr_columns are only supported for ungrouped spans"
            )
        if self.group_by and self.include_details:
            raise ValueError("include_details is only supported for ungrouped spans")
        invalid_custom_attr_columns = [
            col.source
            for col in self.custom_attr_columns
            if col.source not in AGENT_CUSTOM_ATTR_SOURCES
        ]
        if invalid_custom_attr_columns:
            raise ValueError("custom_attr_columns must reference custom attr sources")
        aliases = [measure.alias for measure in self.measures]
        duplicate_aliases = sorted(
            {alias for alias in aliases if aliases.count(alias) > 1}
        )
        if duplicate_aliases:
            raise ValueError(f"duplicate measure aliases: {duplicate_aliases!r}")
        if self.group_by:
            group_aliases = [group_by_ref_alias(ref) for ref in self.group_by]
            reserved = SPAN_GROUP_RESULT_COLS.union(frozenset(group_aliases))
            measure_alias_collisions = sorted(
                {
                    measure.alias
                    for measure in self.measures
                    if measure.alias in reserved
                }
            )
            if measure_alias_collisions:
                raise ValueError(
                    "measure aliases collide with grouped row fields: "
                    f"{measure_alias_collisions!r}"
                )
        distribution_aliases = [
            distribution.alias for distribution in self.group_distributions
        ]
        duplicate_distribution_aliases = sorted(
            {
                alias
                for alias in distribution_aliases
                if distribution_aliases.count(alias) > 1
            }
        )
        if duplicate_distribution_aliases:
            raise ValueError(
                f"duplicate distribution aliases: {duplicate_distribution_aliases!r}"
            )
        return self


class AgentSpansQueryRes(BaseModel):
    """Response from `AgentSpansQueryReq`.

    Exactly one of `spans` or `groups` is populated, depending on whether
    the request asked for list mode or group mode.

    Attributes:
        spans: Raw `AgentSpanSchema` rows. Populated in list mode.
        groups: Aggregated `AgentSpanGroupRow` rows. Populated in group
            mode.
        total_count: Total rows that matched the filter before
            `limit`/`offset`.
    """

    spans: list[AgentSpanSchema] = Field(default_factory=list)
    groups: list[AgentSpanGroupRow] = Field(default_factory=list)
    total_count: int = 0


class AgentCustomAttrsSchemaReq(BaseModel):
    """Discover typed custom attribute keys present on matching spans.

    Custom attributes are user-defined keys that don't fit into the GenAI
    semantic conventions. They land in the four typed Map columns on each
    span row (`custom_attrs_string`, `custom_attrs_int`, `custom_attrs_float`,
    `custom_attrs_bool`). This endpoint lets clients discover which keys
    exist so they can offer filters, group-bys, and distributions for them.

    Pair with `AgentCustomAttrsSchemaRes` for the result shape.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        query: Optional Mongo-style filter to narrow which spans
            contribute to the discovery scan.
        started_after: Only consider spans with `started_at >= start`.
        started_before: Only consider spans with `started_at < end`.
        limit: Maximum keys returned, between 1 and
            `MAX_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT`.
        offset: Number of keys to skip for pagination.
    """

    project_id: str
    query: Query | None = None
    started_after: datetime.datetime | None = None
    started_before: datetime.datetime | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT,
        ge=1,
        le=MAX_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT,
    )
    offset: int = Field(default=0, ge=0)


class AgentCustomAttrSchemaItem(BaseModel):
    """A single discovered custom attribute key.

    Attributes:
        source: Which typed map the key lives in on the span row.
        key: The attribute key, as recorded by the producing span.
        value_type: Inferred value type for the key.
        span_count: Number of matching spans that carried the key.
    """

    source: AgentCustomAttrSource
    key: str
    value_type: AgentCustomAttrValueType
    span_count: int


class AgentCustomAttrsSchemaRes(BaseModel):
    """Discovered custom attribute keys for spans queries.

    The resulting keys can be passed back into
    `AgentSpansQueryReq.custom_attr_columns`,
    `AgentSpansQueryReq.group_by`, and `AgentSpanStatsReq.metrics` via the
    matching `custom_attrs_*` source.

    Attributes:
        attributes: One entry per discovered key.
        limit: Echoes the request limit.
        offset: Echoes the request offset.
        has_more: `True` when at least one more page of keys is
            available.
    """

    attributes: list[AgentCustomAttrSchemaItem] = Field(default_factory=list)
    limit: int = DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT
    offset: int = 0
    has_more: bool = False


# ---------------------------------------------------------------------------
# Agent full-text search
# ---------------------------------------------------------------------------


class AgentSearchReq(BaseModel):
    """Search agent messages by content or by structured filters.

    Scans the `messages` table (one row per occurrence, fed by a materialized
    view over span input and output messages) and returns matching messages
    grouped by conversation. Two modes:

    * **Full-text search**: set `query` to a substring. The other filters
      narrow the scope (for example, "only assistant messages from agent X
      in the last week").
    * **Structured retrieval**: leave `query` empty and rely on the
      filters. For example, set `trace_id` to fetch every message that
      occurred in one trace, with `truncate_content=False` to get the full
      bodies.

    Pair with `AgentSearchRes` for the result shape.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        query: Substring matched against message content. Empty means
            "no content filter," which turns the call into structured
            retrieval.
        trace_id: Restrict to messages in this trace.
        roles: Restrict to these message roles.
        conversation_id: Restrict to messages in this conversation.
        agent_name: Restrict to messages from this agent.
        provider_name: Restrict to messages from this provider.
        request_model: Restrict to messages emitted by this model.
        truncate_content: When `True` (default), the response carries
            content previews. Set `False` to retrieve full message
            bodies.
        started_after: Only include messages with `started_at >= start`.
        started_before: Only include messages with `started_at < end`.
        limit: Maximum messages returned, between 0 and
            `MAX_SEARCH_LIMIT`.
        offset: Number of messages to skip for pagination.
    """

    project_id: str
    # Substring match on message content. Empty matches all (no content filter),
    # turning this into structured retrieval over the filters below.
    query: str = ""

    trace_id: str | None = None
    roles: list[SearchMessageRole] | None = None
    conversation_id: str | None = None
    agent_name: str | None = None
    provider_name: str | None = None
    request_model: str | None = None
    # Truncate message content to a preview (default) to keep search-UI payloads
    # small; set False to return full content (e.g. for structured retrieval).
    truncate_content: bool = True
    started_after: datetime.datetime | None = None
    started_before: datetime.datetime | None = None

    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=0, le=MAX_SEARCH_LIMIT)
    offset: int = Field(default=0, ge=0)


class AgentSearchMatchedMessage(BaseModel):
    """A single message that matched an `AgentSearchReq`.

    Attributes:
        span_id: ID of the span that produced the message.
        trace_id: Trace containing the span.
        role: Message role (`user`, `assistant`, `tool`, and so on).
        content_preview: Trimmed preview of the message content. When the
            request sets `truncate_content=False`, this holds the full
            body.
        content_digest: Stable digest of the full content. Useful for
            deduplicating identical messages across re-runs.
        started_at: Time the producing span started. UTC.
    """

    span_id: str
    trace_id: str
    role: SearchMessageRole
    content_preview: str
    content_digest: str
    started_at: datetime.datetime


class AgentSearchConversationResult(BaseModel):
    """A conversation containing messages that matched an `AgentSearchReq`.

    Attributes:
        conversation_id: Conversation identifier shared by the matching
            messages.
        conversation_name: Human-readable conversation label.
        agent_name: Agent that owns the conversation.
        matched_messages: Messages that matched the search, in
            chronological order.
        last_activity: Time of the most recent matching message. UTC.
    """

    conversation_id: str
    conversation_name: str
    agent_name: str
    matched_messages: list[AgentSearchMatchedMessage]
    last_activity: datetime.datetime


class AgentSearchRes(BaseModel):
    """Response from an `AgentSearchReq`.

    Attributes:
        results: One entry per conversation that contained a matching
            message.
        total_conversations: Total conversations that matched before
            `limit`/`offset`.
    """

    results: list[AgentSearchConversationResult]
    total_conversations: int = 0


AgentChatMessageType = Literal[
    "user_message",
    "assistant_message",
    "tool_call",
    "agent_handoff",
    "agent_start",
    "context_compacted",
]


class AgentChatUserMessage(BaseModel):
    """Payload for a user prompt in the chat timeline.

    Set on `AgentChatMessage.user_message` when
    `AgentChatMessage.type == "user_message"`.

    Attributes:
        text: Rendered user prompt text.
        content_refs: Refs to detached content blobs attached to the
            prompt (for example, images uploaded with the message).
    """

    text: str
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAssistantMessage(BaseModel):
    """Payload for assistant text emitted by an agent or LLM span.

    Set on `AgentChatMessage.assistant_message` when
    `AgentChatMessage.type == "assistant_message"`. The `*_cost_usd`
    fields are filled in by the chat-view assembler when query-time cost
    computation is enabled.

    Attributes:
        text: Rendered assistant response text.
        model: Model that produced the response.
        reasoning_content: Reasoning text from a reasoning-capable
            model, when available.
        reasoning_tokens: Reasoning token count for this message.
        input_tokens: Prompt tokens consumed by the producing span.
        output_tokens: Completion tokens emitted by the producing span.
        input_cost_usd: Input-token cost in USD for the producing span
            (summed across the subtree for aggregated agent turns).
            `None` (not `0`) signals that no priced model matched.
        output_cost_usd: Output-token cost in USD. Same `None`
            semantics.
        total_cost_usd: Sum of input and output costs. Same `None`
            semantics.
        duration_ms: Wall-clock duration of the producing span.
        status: OTel status code from the producing span.
        content_refs: Refs to detached content blobs (for example, image
            attachments).
    """

    text: str
    model: str | None = None
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    # Query-time costs (USD) for this message's span (or, for aggregated agent
    # turns, summed across the subtree). None when the model has no price.
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    total_cost_usd: float | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatToolCall(BaseModel):
    """Payload for a tool call timeline event.

    Set on `AgentChatMessage.tool_call` when
    `AgentChatMessage.type == "tool_call"`. Combines the assistant's
    tool-call request and the tool's execution result into one timeline
    event.

    Attributes:
        tool_name: Tool name as registered with the agent.
        tool_arguments: JSON-encoded arguments passed to the tool.
        tool_result: Serialized tool result.
        duration_ms: Wall-clock duration of the `execute_tool` span.
        status: OTel status code from the `execute_tool` span.
        content_refs: Refs to detached content blobs attached to the
            call or result.
    """

    tool_name: str | None = None
    tool_arguments: str | None = None
    tool_result: str | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAgentStart(BaseModel):
    """Payload for an agent lifecycle boundary in the chat timeline.

    Marks the start of an `invoke_agent` span and carries the system
    instructions and tool catalog the model was given. Set on
    `AgentChatMessage.agent_start` when
    `AgentChatMessage.type == "agent_start"`.

    Attributes:
        model: Model bound to the agent for this invocation.
        system_instructions: System prompt set on the agent.
        tool_definitions: Serialized tool catalog provided to the agent.
        status: OTel status code from the `invoke_agent` span.
    """

    model: str | None = None
    system_instructions: str | None = None
    tool_definitions: str | None = None
    status: StatusCodeLiteral | None = None


class AgentChatAgentHandoff(BaseModel):
    """Payload for a future agent-to-agent handoff event.

    Reserved for handoff semantics in multi-agent frameworks. Set on
    `AgentChatMessage.agent_handoff` when
    `AgentChatMessage.type == "agent_handoff"`. Currently has no fields.
    """


class AgentChatContextCompacted(BaseModel):
    """Payload for a context-window compaction event.

    Emitted when an agent rewrites its context window to fit within the
    model's token budget. Set on `AgentChatMessage.context_compacted` when
    `AgentChatMessage.type == "context_compacted"`.

    Attributes:
        compaction_summary: Summary of what was compacted.
        compaction_items_before: Number of message items before
            compaction.
        compaction_items_after: Number of message items after
            compaction.
    """

    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None


class AgentChatMessage(BaseModel):
    """One event in the structured agent trajectory / chat view.

    The chat view flattens an agent's span tree into a linear timeline
    that's easier to render and reason about than the underlying graph.
    Each `AgentChatMessage` is one of several event kinds, distinguished
    by `type` (see `AgentChatMessageType`). The matching payload field
    holds the type-specific data; all other payload fields must be
    `None`.

    Common fields like `span_id`, `agent_name`, and `started_at` live at
    the top level so callers can render headers and filters without
    drilling into the payload.

    Attributes:
        type: Event kind. Drives which payload field is populated.
        span_id: ID of the producing span, when one exists.
        agent_name: Agent that produced the event.
        agent_version: Agent version that produced the event.
        status_code: OTel status code from the producing span.
        started_at: Time the event started. UTC.
        user_message: Payload for `type="user_message"`.
        assistant_message: Payload for `type="assistant_message"`.
        tool_call: Payload for `type="tool_call"`.
        agent_start: Payload for `type="agent_start"`.
        agent_handoff: Payload for `type="agent_handoff"`.
        context_compacted: Payload for `type="context_compacted"`.
        feedback: Optional list of feedback rows attached to this event.
            Populated only when the parent request set
            `include_feedback=True`.

    Raises:
        ValueError: When the payload field matching `type` is missing or
            another payload field is also set.
    """

    type: AgentChatMessageType
    span_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    status_code: StatusCodeLiteral | None = None
    started_at: datetime.datetime | None = None

    user_message: AgentChatUserMessage | None = None
    assistant_message: AgentChatAssistantMessage | None = None
    tool_call: AgentChatToolCall | None = None
    agent_start: AgentChatAgentStart | None = None
    agent_handoff: AgentChatAgentHandoff | None = None
    context_compacted: AgentChatContextCompacted | None = None

    @model_validator(mode="after")
    def validate_single_payload(self) -> AgentChatMessage:
        expected_field = self.type
        payload_fields = (
            "user_message",
            "assistant_message",
            "tool_call",
            "agent_handoff",
            "agent_start",
            "context_compacted",
        )
        missing_expected = getattr(self, expected_field) is None
        unexpected_fields = [
            field
            for field in payload_fields
            if field != expected_field and getattr(self, field) is not None
        ]

        if missing_expected or unexpected_fields:
            raise ValueError(
                f"AgentChatMessage type={self.type!r} must set only "
                f"{expected_field!r}; unexpected payloads={unexpected_fields!r}"
            )
        return self

    feedback: list[dict[str, Any]] | None = None


class AgentTraceChatReq(BaseModel):
    """Request the structured chat / trajectory view for a single trace.

    Returns the timeline of one turn: user prompts, assistant responses,
    tool calls, lifecycle events, and any compaction or handoff events
    that occurred under the trace's root span. Pair with
    `AgentTraceChatRes`.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        trace_id: OTel trace ID for the turn to render.
        include_feedback: Attach feedback rows on the response and on
            each message that has any. Defaults to `False` to keep the
            payload small.
    """

    project_id: str
    trace_id: str
    include_feedback: bool = False


class AgentTraceChatRes(BaseModel):
    """Structured chat / trajectory view for one trace (turn).

    The response gives a header (`root_span_name`, `agent_name`,
    `agent_version`, `provider`, status, duration, cost) plus a linear
    `messages` list ready to render top-to-bottom.

    `AgentConversationChatRes.turns` reuses this shape, so the same UI
    code renders a single-turn view and a per-turn slice of a
    conversation.

    Attributes:
        trace_id: OTel trace ID echoed from the request.
        root_span_name: Name of the trace's root span.
        agent_name: Agent that owns the trace.
        agent_version: Agent version that produced the trace.
        status_code: OTel status of the root span.
        provider: Provider name reported by the root span.
        total_duration_ms: Wall-clock duration of the trace root span,
            in milliseconds. This is the root span's own duration, not
            a sum across descendants.
        total_cost_usd: Sum of `total_cost_usd` across every span in
            the trace, in USD. `None` (not `0`) signals that no priced
            model matched.
        messages: The chat timeline, in chronological order.
        feedback: Trace-level feedback rows. Populated only when the
            request set `include_feedback=True`.
    """

    trace_id: str
    root_span_name: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    status_code: StatusCodeLiteral | None = None
    provider: str | None = None
    total_duration_ms: int | None = Field(
        default=None,
        description=(
            "Wall-clock duration of the trace root span in milliseconds. "
            "This is not a sum of child span durations."
        ),
    )
    # Summed query-time cost (USD) across all spans in the trace. Unlike
    # duration, this IS a sum across spans. None when no span had a price.
    total_cost_usd: float | None = None
    messages: list[AgentChatMessage] = Field(default_factory=list)
    feedback: list[dict[str, Any]] | None = None


class AgentConversationChatReq(BaseModel):
    """Request the multi-turn chat view for one conversation.

    The conversation is identified by `conversation_id`, the value Weave
    extracts from `gen_ai.conversation.id` on each span. Pair with
    `AgentConversationChatRes`.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        conversation_id: Conversation identifier.
        limit: Maximum number of turns to return per page, between 0
            and `MAX_CONVERSATION_CHAT_TURNS`.
        offset: Number of most-recent turns to skip. Results inside the
            selected page are returned in chronological order.
        include_feedback: Attach feedback rows to each turn and message
            that has any. Defaults to `False` to keep the payload small.
    """

    project_id: str
    conversation_id: str
    limit: int = Field(
        default=MAX_CONVERSATION_CHAT_TURNS,
        ge=0,
        le=MAX_CONVERSATION_CHAT_TURNS,
        description="Maximum number of conversation turns to return.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of most-recent turns to skip. Results are returned in "
            "chronological order within the selected page."
        ),
    )
    include_feedback: bool = False


class AgentConversationChatRes(BaseModel):
    """Multi-turn chat view for one conversation.

    Each entry in `turns` is one trace, which Weave treats as one
    conversation turn. A turn can contain zero, one, or many
    `invoke_agent` spans, so this isn't a one-to-one mapping with
    `invoke_agent`. Clients can render a divider between entries and
    reuse `AgentTraceChatRes` rendering for each turn.

    Attributes:
        conversation_id: Conversation identifier echoed from the
            request.
        turns: Per-turn chat views in chronological order. Each entry
            is a complete `AgentTraceChatRes`.
        total_turns: Total turns in the conversation before
            `limit`/`offset`.
        has_more: `True` when at least one more page of turns is
            available.
        limit: Echoes the request limit.
        offset: Echoes the request offset.
        total_cost_usd: Sum of `total_cost_usd` across the returned
            turns. `None` (not `0`) signals that no priced model
            matched.
        feedback: Conversation-level feedback rows. Populated only when
            the request set `include_feedback=True`.
    """

    conversation_id: str
    turns: list[AgentTraceChatRes] = Field(default_factory=list)
    total_turns: int = 0
    has_more: bool = False
    limit: int = MAX_CONVERSATION_CHAT_TURNS
    offset: int = 0
    # Summed query-time cost (USD) across the returned turns. None when no turn
    # had a priced span.
    total_cost_usd: float | None = None
    feedback: list[dict[str, Any]] | None = None


class AgentSchema(BaseModel):
    """Aggregated stats for one agent in a project.

    Returned in `AgentsQueryRes.agents`. One row per `agent_name`,
    summarizing every span attributed to that agent across all versions
    and conversations.

    Attributes:
        project_id: Owning Weave project in `entity/project` form.
        agent_name: Agent identifier.
        invocation_count: Number of `invoke_agent` spans attributed to
            the agent.
        span_count: Total spans attributed to the agent.
        total_input_tokens: Sum of `input_tokens` across the agent's
            spans.
        total_output_tokens: Sum of `output_tokens` across the agent's
            spans.
        total_duration_ms: Sum of span wall-clock durations in
            milliseconds.
        error_count: Spans with `status_code == "Error"`.
        first_seen: Earliest `started_at` for the agent. UTC.
        last_seen: Latest `started_at` for the agent. UTC.
        total_cost_usd: Summed query-time cost in USD, populated only
            when the request sets `include_costs=True`. The agents
            materialized view doesn't store cost, so the handler fills
            this from a supplementary grouped spans query. `None`
            signals that costs weren't requested or no priced model
            matched.
    """

    project_id: str
    agent_name: str
    invocation_count: int
    span_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_duration_ms: int
    error_count: int
    first_seen: datetime.datetime | None
    last_seen: datetime.datetime | None
    # Summed query-time cost (USD), populated only when the query sets
    # include_costs. The agents/agent_versions materialized views don't store
    # cost, so the handler fills this from a supplementary grouped spans query.
    # None when costs weren't requested or no span had a price.
    total_cost_usd: float | None = None


class AgentsQueryFilters(BaseModel):
    """Optional filters for `AgentsQueryReq`.

    Attributes:
        agent_name: Exact-match filter on agent name. `None` matches
            all agents in the project.
    """

    agent_name: str | None = None


class AgentsQueryReq(BaseModel):
    """List the agents in a project with their aggregated stats.

    Pair with `AgentsQueryRes`. Use `AgentVersionsQueryReq` to drill into
    the versions of a specific agent.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        filters: Optional filters narrowing which agents are returned.
        sort_by: Sort order. Allowed fields are validated server-side.
        limit: Maximum rows returned, between 0 and
            `MAX_AGENT_QUERY_LIMIT`.
        offset: Number of rows to skip.
        include_costs: Fill `AgentSchema.total_cost_usd` from a
            supplementary grouped spans cost query.
    """

    project_id: str
    filters: AgentsQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    # When true, fill AgentSchema.total_cost_usd from a supplementary grouped spans
    # cost query (the agents materialized view has no cost column).
    include_costs: bool = False


class AgentsQueryRes(BaseModel):
    """Response from `AgentsQueryReq`.

    Attributes:
        agents: One `AgentSchema` per matching agent.
        total_count: Total agents that matched before `limit`/`offset`.
    """

    agents: list[AgentSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# Agent versions (from agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(AgentSchema):
    """Aggregated stats for one (agent, version) pair.

    Extends `AgentSchema` with `agent_version`. One row per distinct
    `(agent_name, agent_version)` observed in the project.

    Attributes:
        agent_version: Version label attached to the producing spans.
    """

    agent_version: str


class AgentVersionsQueryReq(BaseModel):
    """List the versions seen for an agent.

    Use this after `AgentsQueryReq` to compare behavior across releases
    of the same agent. Pair with `AgentVersionsQueryRes`.

    Attributes:
        project_id: Target Weave project in `entity/project` form.
        agent_name: Agent to enumerate versions for.
        sort_by: Sort order. Allowed fields are validated server-side.
        limit: Maximum rows returned, between 0 and
            `MAX_AGENT_QUERY_LIMIT`.
        offset: Number of rows to skip.
        include_costs: Fill `AgentVersionSchema.total_cost_usd` from a
            supplementary grouped spans cost query.
    """

    project_id: str
    agent_name: str
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    # When true, fill AgentVersionSchema.total_cost_usd from a supplementary grouped
    # spans cost query (the agent_versions materialized view has no cost column).
    include_costs: bool = False


class AgentVersionsQueryRes(BaseModel):
    """Response from `AgentVersionsQueryReq`.

    Attributes:
        versions: One `AgentVersionSchema` per `(agent_name,
            agent_version)` pair.
        total_count: Total versions that matched before
            `limit`/`offset`.
    """

    versions: list[AgentVersionSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# OTel ingest types
# ---------------------------------------------------------------------------


class GenAIOTelExportReq(BaseModel):
    """Request for the GenAI OTel ingest endpoint.

    The agent observability ingest path accepts the same
    `ProcessedResourceSpans` payload as the generic OTel endpoint but
    routes the spans through GenAI extraction so they land in the agent
    spans table (and downstream materialized views) with the right
    semconv fields populated.

    Attributes:
        processed_spans: Deserialized OTel resource spans to ingest.
        project_id: Target Weave project in `entity/project` form.
        wb_user_id: Optional W&B user ID to record on each span.

    See `GenAIOTelExportRes` for the result shape.
    """

    model_config = {"arbitrary_types_allowed": True}

    processed_spans: list[ProcessedResourceSpans] = Field(
        ..., description="List of ProcessedResourceSpans from OTel deserialization"
    )
    project_id: str
    wb_user_id: str | None = None


class GenAIOTelExportRes(BaseModel):
    """Response from `GenAIOTelExportReq`.

    Attributes:
        accepted_spans: Spans that passed extraction and were enqueued
            for insertion.
        rejected_spans: Spans the server skipped (for example, when an
            attribute couldn't be parsed). Rejected spans don't block
            the rest of the batch.
        error_message: Short summary of the rejection cause when
            `rejected_spans > 0`. Empty when everything succeeded.
    """

    accepted_spans: int = 0
    rejected_spans: int = 0
    error_message: str = ""
