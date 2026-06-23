"""Pydantic request and response types for the Weave Agents API.

Every shape that crosses the wire for agent observability lives here. The
FastAPI handlers in `services/weave-trace`, the ClickHouse handler in
`weave/trace_server/clickhouse_trace_server_batched.py`, the in-memory
fake, and the SDK bindings all import from this module so the contract
is one set of definitions, not three.

The domain has five concepts. Read them in order; later concepts
compose earlier ones.

1. **Agent.** Identified by `agent_name`. The container at the top of
   the Agents view.
2. **Agent version.** Identified by `(agent_name, agent_version)`.
   Lets a caller diff behavior across releases of the same agent.
3. **Span.** One OTel GenAI span: an agent invocation, an LLM call, a
   tool execution, a context compaction, or a handoff. The atomic
   unit of recorded activity.
4. **Turn.** One trace's span tree rendered as a linear chat
   timeline. Roughly "one user message and the agent's complete
   response."
5. **Conversation.** Turns that share a `conversation_id`, presented
   as ordered multi-turn chat.

Endpoints come in `*Req` / `*Res` pairs:

* `agent_agents_query` — `AgentsQueryReq` -> `AgentsQueryRes`
* `agent_versions_query` — `AgentVersionsQueryReq` ->
  `AgentVersionsQueryRes`
* `agent_spans_query` — `AgentSpansQueryReq` ->
  `AgentSpansQueryRes` (list mode and group mode share the same
  endpoint, picked by whether `group_by` is set)
* `agent_spans_stats` — `AgentSpanStatsReq` -> `AgentSpanStatsRes`
* `agent_traces_chat` — `AgentTraceChatReq` -> `AgentTraceChatRes`
* `agent_conversation_chat` — `AgentConversationChatReq` ->
  `AgentConversationChatRes`
* `agent_search` — `AgentSearchReq` -> `AgentSearchRes`
* `agent_custom_attrs_schema` — `AgentCustomAttrsSchemaReq` ->
  `AgentCustomAttrsSchemaRes`
* `genai_otel_export` — `GenAIOTelExportReq` ->
  `GenAIOTelExportRes`

For the user-facing concepts and instrumentation patterns behind these
shapes, see https://docs.wandb.ai/weave/guides/tracking/trace-agents.
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
    """Pointer to one value on a span row.

    The primitive that every higher-level spec composes:
    `AgentSpanMeasureSpec`, `AgentSpanStatsMetricSpec`,
    `AgentSpanGroupDistributionSpec`, and
    `AgentSpanStatsNumericBucketSpec` all hold one of these to name
    "the thing to read." The `source` chooses where the value lives:

    1. `field` — a semconv field like `agent.name` or a direct column
       like `agent_name`; resolved through the server's allowlist.
    2. `derived` — a query-time metric from
       `AGENT_SPAN_STATS_DERIVED_VALUE_TYPES` (e.g. `duration_ms`,
       `total_tokens`, `total_cost_usd`).
    3. `custom_attrs_string` / `custom_attrs_int` /
       `custom_attrs_float` / `custom_attrs_bool` — a user-defined key
       inside the matching typed Map column on the span row.

    Args:
        source: Where the value lives. Defaults to `field`.
        key: Field name, derived-metric name, or custom-attribute key,
            interpreted according to `source`.

    Raises:
        ValueError: When `source="derived"` but `key` is not a
            recognized derived metric.

    Examples:
        >>> # Group spans by the request_model field.
        >>> AgentSpanValueRef(source="field", key="request_model")
        >>> # Sum the derived total_cost_usd metric.
        >>> AgentSpanValueRef(source="derived", key="total_cost_usd")
        >>> # Read a user-defined integer attribute named "retries".
        >>> AgentSpanValueRef(source="custom_attrs_int", key="retries")
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
    """Aggregated roll-up of one span value into a single number per group.

    Pairs an `AgentSpanValueRef` with an aggregation function. Used on
    `AgentSpansQueryReq.measures` (per-group measures land in
    `AgentSpanGroupRow.metrics`) and on `AgentSpanGroupFilter.measure`
    (range-filter groups by an aggregated value).

    The aggregation must be legal for `value_type`; see
    `_ALLOWED_AGGS_BY_TYPE`. `count` is the only aggregation that may
    omit `value`.

    Args:
        alias: Output key in `AgentSpanGroupRow.metrics`. Must be a
            valid Python identifier and must not collide with the
            reserved aggregate fields on `AgentSpanGroupRow`.
        aggregation: Roll-up function to apply.
        value: Span value to aggregate. Required for every aggregation
            except `count`.
        value_type: Declared type of `value`. Drives aggregation
            validation. Optional when the aggregation is `count` or
            when `value.source="derived"` (the derived metric pins the
            type).
        filter: Optional Mongo-style `Query` further restricting which
            spans contribute. Applied on top of the request-level
            filter.

    Raises:
        ValueError: When `value` is missing for a non-`count`
            aggregation, when `value_type` disagrees with a derived
            metric's known type, or when the aggregation is not legal
            for `value_type`.

    Examples:
        >>> # Average duration in milliseconds across spans in each group.
        >>> AgentSpanMeasureSpec(
        ...     alias="avg_duration_ms",
        ...     aggregation="avg",
        ...     value=AgentSpanValueRef(source="derived", key="duration_ms"),
        ...     value_type="number",
        ... )
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
    """Chart series for the `agent_spans_stats` endpoint.

    Use on `AgentSpanStatsReq.metrics`. Each spec fans out into one
    response column per aggregation or percentile, named
    `{alias}__{aggregation}` or `{alias}__p{percentile}`.

    Note: when both `aggregations` and `percentiles` are empty, the
    validator picks a default (`sum` for numbers, `count` otherwise).
    Don't rely on that in new code. Pass at least one aggregation
    explicitly.

    Args:
        alias: Prefix shared by every column this metric produces.
            Must be a valid Python identifier.
        value_type: Type of the underlying span value. Drives which
            aggregations are legal.
        aggregations: Aggregations to compute. Must be unique and must
            match `value_type` (see `_ALLOWED_AGGS_BY_TYPE`).
        percentiles: Quantile cutoffs in the closed interval
            `[0, 100]`. Only valid when `value_type="number"`. Must be
            unique.
        value: Span value the aggregations apply to.

    Raises:
        ValueError: When aggregations are non-unique or illegal for
            `value_type`, when percentiles are out of range or
            duplicated, or when percentiles are requested on a
            non-numeric metric.

    Examples:
        >>> # p50 and p99 of duration_ms.
        >>> AgentSpanStatsMetricSpec(
        ...     alias="duration_ms",
        ...     value_type="number",
        ...     percentiles=[50.0, 99.0],
        ...     value=AgentSpanValueRef(source="derived", key="duration_ms"),
        ... )
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
    """Schema entry for one cell in an `AgentSpanStatsRes` row.

    `AgentSpanStatsRes.rows` is a list of untyped dicts so the wire
    format stays compact. This column list, returned alongside, pins
    down the type and meaning of each key in those dicts.

    Args:
        name: Key used inside each row dict.
        role: Provenance of the column. `time` for the time bucket
            boundary, `bucket` for a numeric bucket boundary, `group`
            for a group-by ref, `metric` for one aggregation or
            percentile of a metric.
        value_type: Cell type.
        metric: Originating metric `alias` for `metric` columns.
            `None` for the other roles.
        aggregation: Aggregation name or `pNN` percentile label for
            `metric` columns. `None` for the other roles.

    Examples:
        >>> AgentSpanStatsColumn(
        ...     name="duration_ms__p99",
        ...     role="metric",
        ...     value_type="number",
        ...     metric="duration_ms",
        ...     aggregation="p99",
        ... )
    """

    name: str
    role: Literal["time", "bucket", "group", "metric"]
    value_type: AgentSpanStatsColumnValueType
    metric: str | None = None
    aggregation: str | None = None


class AgentSpanGroupFilter(BaseModel):
    """Keep only groups whose aggregated measure falls in a range.

    Use on `AgentSpansQueryReq.group_filters` (post-grouping filter)
    and `AgentSpanStatsReq.group_filters` (post-bucket filter).
    Examples: "agents whose error count is between 5 and 100" or
    "conversations whose first span happened after yesterday."

    At least one of `min` or `max` must be set. When both are set,
    they must share a type and `max` must be greater than or equal to
    `min`.

    Args:
        group_by: Optional override for the grouping used by this
            filter. Empty reuses the surrounding request's grouping.
        measure: Aggregated measure the range applies to.
        min: Lower bound, inclusive. `None` for no lower bound.
        max: Upper bound, inclusive. `None` for no upper bound.

    Raises:
        ValueError: When both bounds are `None`, when `min` and `max`
            have mismatched types, or when `max < min`.

    Examples:
        >>> # Keep groups whose error count is at least 5.
        >>> AgentSpanGroupFilter(
        ...     measure=AgentSpanMeasureSpec(
        ...         alias="error_count",
        ...         aggregation="count",
        ...         filter=None,
        ...     ),
        ...     min=5,
        ... )
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
    """Time-series bucketing for `agent_spans_stats`.

    Default branch of the `AgentSpanStatsBucketSpec` discriminated
    union. Bucket width comes from `AgentSpanStatsReq.granularity`
    (seconds); when granularity is `None`, the server picks a width
    based on the date range. Use `AgentSpanStatsNumericBucketSpec` for
    histogram-style charts instead.

    Examples:
        >>> AgentSpanStatsTimeBucketSpec()
    """

    type: Literal["time"] = "time"


class AgentSpanStatsNumericBucketSpec(BaseModel):
    """Histogram bucketing for `agent_spans_stats`.

    Numeric branch of `AgentSpanStatsBucketSpec`. Two mutually
    exclusive modes:

    1. **Per-span histogram** — set `value`, leave
       `group_by`/`measure` empty. Each span's `value` lands in one
       bucket.
    2. **Grouped-measure histogram** — set `group_by` and `measure`,
       leave `value` empty. Each group's aggregated measure lands in
       one bucket.

    `bins` divides `[min, max]` into equal-width buckets; `min` and
    `max` default to the data range.

    Args:
        alias: Output column name for the bucket boundary.
        bins: Bucket count, 1 to 200. Defaults to 24.
        min: Lower bound. `None` uses the data minimum.
        max: Upper bound. `None` uses the data maximum.
        value: Per-span numeric value to bucket. Mutually exclusive
            with `group_by`/`measure`.
        group_by: Group-by refs whose aggregated measure should be
            bucketed. Requires `measure`.
        measure: Aggregated measure to bucket. Requires `group_by`.

    Raises:
        ValueError: When the two modes overlap or both are empty,
            when only one of `group_by`/`measure` is set, when a
            non-numeric value or measure is referenced, or when
            `max < min`.

    Examples:
        >>> # Per-span histogram of duration_ms across 20 buckets.
        >>> AgentSpanStatsNumericBucketSpec(
        ...     bins=20,
        ...     value=AgentSpanValueRef(source="derived", key="duration_ms"),
        ... )
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
    """Chart-ready aggregation request for `agent_spans_stats`.

    Five-stage pipeline: filter spans (`query` + `started_at` window),
    bucket (`bucket_by`, default time at `granularity` seconds), group
    within bucket (`group_by`), compute metrics, drop groups failing
    `group_filters`.

    Pair with `AgentSpanStatsRes`.

    Note: grouped requests cap the window at
    `MAX_AGENT_STATS_RANGE_DAYS`. Unfiltered, ungrouped requests are
    exempt because they back cheap top-line counts.

    Args:
        project_id: Target project in `entity/project` form.
        query: Optional Mongo-style filter. Field names resolve via
            GenAI semconv, direct span columns, or typed custom
            attribute keys.
        start: Window start, inclusive. Naive datetimes are read as
            UTC.
        end: Window end, exclusive. Defaults to "now (UTC)" when
            omitted.
        granularity: Time bucket width in seconds. Server picks a
            default when `None`. Ignored for numeric buckets.
        timezone: IANA timezone for time-of-day grouping in the
            response. Defaults to `UTC`.
        group_by: Group within each bucket by these refs. Mutually
            exclusive with `bucket_by` set to a numeric bucket spec.
        metrics: Metrics to compute per bucket and group. Required
            unless a numeric bucket spec already produces counts.
        group_limit: Maximum groups per bucket, 1 to
            `MAX_AGENT_STATS_GROUP_LIMIT`.
        bucket_by: Bucketing strategy. `None` is equivalent to
            `AgentSpanStatsTimeBucketSpec()`.
        group_filters: Range filters over aggregated measures. Valid
            for time buckets and grouped numeric buckets only.

    Raises:
        ValueError: When `metrics` are missing without a numeric
            bucket spec, when metric aliases collide, when
            `end < start`, when a grouped request exceeds
            `MAX_AGENT_STATS_RANGE_DAYS`, or when `group_by`,
            `metrics`, and `bucket_by` combine illegally.

    Examples:
        >>> AgentSpanStatsReq(
        ...     project_id="your-team/your-project",
        ...     start=datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc),
        ...     metrics=[
        ...         AgentSpanStatsMetricSpec(
        ...             alias="duration_ms",
        ...             value_type="number",
        ...             percentiles=[50.0, 99.0],
        ...             value=AgentSpanValueRef(source="derived", key="duration_ms"),
        ...         ),
        ...     ],
        ... )
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
    """Chart-ready response from `agent_spans_stats`.

    Read `columns` first to get the schema, then index each entry in
    `rows` by `AgentSpanStatsColumn.name`. The `start`, `end`,
    `granularity`, and `timezone` fields echo what the server actually
    applied, so clients render axes without re-deriving them. Empty
    buckets are omitted from `rows`.

    Args:
        start: Window start the server used. UTC.
        end: Window end the server used. UTC.
        granularity: Time bucket width the server applied. `None` for
            numeric buckets.
        timezone: IANA timezone echoed from the request.
        bucket_type: Which discriminant of `AgentSpanStatsBucketSpec`
            was applied.
        columns: Schema for cells in each `rows` dict.
        rows: One dict per non-empty bucket-and-group combination.

    Examples:
        >>> res = AgentSpanStatsRes(
        ...     start=datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc),
        ...     end=datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc),
        ...     timezone="UTC",
        ... )
        >>> [col.name for col in res.columns]
        []
    """

    start: datetime.datetime
    end: datetime.datetime
    granularity: int | None = None
    timezone: str
    bucket_type: Literal["time", "number"] = "time"
    columns: list[AgentSpanStatsColumn] = Field(default_factory=list)
    rows: list[dict[str, AgentSpanStatsCell]] = Field(default_factory=list)


class AgentSpanSchema(BaseModel):
    """Normalized agent span row, the unit of `agent_spans_query`.

    One OTel GenAI span flattened into Weave's column layout. Same
    shape regardless of how the span was produced:
    `weave.start_session()` / `weave.start_turn()` /
    `weave.start_llm()` / `weave.start_tool()`, a raw OTel exporter,
    or one of the autopatched integrations.

    Most fields are nullable because the producing span may not have
    emitted the corresponding GenAI attribute. List fields default to
    empty.

    Note: the `*_cost_usd` fields and `raw_span_dump` are opt-in. The
    server populates them only when the request sets
    `include_costs=True` or `include_details=True` respectively. Cost
    fields use `None` (not `0`) to mean "no priced model matched," so
    the UI can distinguish "unpriced" from "free."

    Args:
        project_id: Owning project in `entity/project` form.
        trace_id: OTel trace ID. All spans in one turn share this.
        span_id: OTel span ID. Unique within the trace.
        parent_span_id: Parent span ID, or `None` for root spans.
        span_name: OTel span name (`chat gpt-4o`,
            `execute_tool search`, etc.).
        span_kind: OTel span kind (`Server`, `Client`, `Internal`).
        started_at: Span start time. UTC.
        ended_at: Span end time. UTC.
        status_code: OTel status: `Ok`, `Error`, or `Unset`.
        status_message: Human-readable status detail; typically the
            error message when `status_code == "Error"`.
        operation_name: GenAI `gen_ai.operation.name`
            (`invoke_agent`, `chat`, `execute_tool`).
        provider_name: GenAI `gen_ai.provider.name` (`openai`,
            `anthropic`, etc.).
        agent_name: Identifier of the agent that owns the span.
        agent_id: Stable agent ID emitted by the SDK, if any.
        agent_description: Free-form agent description.
        agent_version: Agent version string for cross-release
            grouping.
        request_model: Model requested.
        response_model: Model the provider reports actually served the
            response.
        response_id: Provider's response identifier.
        input_tokens: Prompt tokens reported by the provider.
        output_tokens: Completion tokens reported by the provider.
        reasoning_tokens: Reasoning tokens for reasoning-capable
            models.
        cache_creation_input_tokens: Tokens written to a provider
            prompt cache.
        cache_read_input_tokens: Tokens read from a provider prompt
            cache.
        input_cost_usd: Query-time input-token cost in USD. Opt-in
            via `include_costs`. See the note above on `None`
            semantics.
        output_cost_usd: Query-time output-token cost in USD. Opt-in.
        cache_read_cost_usd: Query-time cost of cached prompt reads
            in USD. Opt-in.
        cache_creation_cost_usd: Query-time cost of cache writes in
            USD. Opt-in.
        total_cost_usd: Sum of the per-direction cost fields above.
            Opt-in.
        reasoning_content: Reasoning text captured from a reasoning
            model's response.
        conversation_id: GenAI `gen_ai.conversation.id`. Spans
            sharing this value belong to one conversation.
        conversation_name: Human-readable conversation label.
        tool_name: Tool name for `execute_tool` spans.
        tool_type: Optional tool classification.
        tool_call_id: ID of the originating tool-use call; links an
            LLM's tool call to its `execute_tool` span.
        tool_description: Tool description captured at call time.
        tool_definitions: Serialized tool catalog given to the model.
        finish_reasons: Provider finish reasons, one per output
            choice.
        error_type: Exception type or provider error code for failed
            spans.
        request_temperature: Sampling temperature for the LLM call.
        request_max_tokens: Max completion tokens requested.
        request_top_p: Top-p sampling parameter.
        request_frequency_penalty: Frequency penalty.
        request_presence_penalty: Presence penalty.
        request_seed: Provider seed for deterministic sampling.
        request_stop_sequences: Stop sequences.
        request_choice_count: Number of completions requested.
        output_type: Provider-specific output format (`text`,
            `json_object`, etc.).
        input_messages: Normalized input messages sent to the model.
        output_messages: Normalized output messages returned by the
            model.
        system_instructions: System prompts attached to the call.
        tool_call_arguments: JSON-encoded tool call arguments for
            `execute_tool` spans.
        tool_call_result: Serialized tool result.
        compaction_summary: Summary emitted by a context-window
            compaction event.
        compaction_items_before: Items in context before compaction.
        compaction_items_after: Items in context after compaction.
        content_refs: Refs to large message content stored outside
            the row.
        artifact_refs: Refs to W&B artifacts attached to the span.
        object_refs: Refs to Weave objects attached to the span.
        custom_attrs_string: User-defined string attributes.
        custom_attrs_int: User-defined integer attributes.
        custom_attrs_float: User-defined float attributes.
        custom_attrs_bool: User-defined boolean attributes.
        server_address: Provider host recorded on the span.
        server_port: Provider port recorded on the span.
        wb_user_id: W&B user who recorded the span.
        wb_run_id: Associated W&B run ID.
        wb_run_step: W&B run step at span start.
        wb_run_step_end: W&B run step at span end.
        raw_span_dump: Full OTel JSON payload for the span. Opt-in
            via `include_details`.

    Examples:
        >>> span = AgentSpanSchema(
        ...     project_id="your-team/your-project",
        ...     trace_id="t1",
        ...     span_id="s1",
        ...     agent_name="research-bot",
        ...     operation_name="invoke_agent",
        ... )
        >>> span.agent_version is None
        True
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
    """One step of the sort order for list endpoints.

    Pass as an ordered list to `AgentsQueryReq.sort_by`,
    `AgentVersionsQueryReq.sort_by`, and `AgentSpansQueryReq.sort_by`.
    Steps apply left to right; the allowed `field` values are
    validated per endpoint server-side.

    Args:
        field: Sortable field name.
        direction: `desc` (default) sorts newest or largest first;
            `asc` sorts oldest or smallest first.

    Examples:
        >>> # Newest spans first.
        >>> AgentSortBy(field="started_at", direction="desc")
    """

    field: str
    direction: Literal["asc", "desc"] = "desc"


class AgentGroupByRef(BaseModel):
    """Group-by axis for `agent_spans_query` and `agent_spans_stats`.

    Used on `AgentSpansQueryReq.group_by`,
    `AgentSpanStatsReq.group_by`,
    `AgentSpanStatsNumericBucketSpec.group_by`, and
    `AgentSpanGroupFilter.group_by`. The resolved alias appears in
    `AgentSpanGroupRow.group_keys`; compute it with
    `group_by_ref_alias` rather than recomputing the resolution rules.

    Sources split into two families:

    1. **Field / column** (`field`, `column`) — an allowlisted
       semconv field (`agent.name`) or direct span column
       (`agent_name`). `column` is the legacy alias and behaves the
       same as `field`.
    2. **Custom attribute** (`custom_attrs_string`,
       `custom_attrs_int`, `custom_attrs_float`, `custom_attrs_bool`)
       — a user-defined key inside the matching typed Map column on
       the span row.

    Args:
        source: Which family `key` resolves through.
        key: Field name (family 1) or attribute key (family 2).
        alias: Override for the output key in
            `AgentSpanGroupRow.group_keys`. When `None`, the server
            falls back to the resolved column or the raw `key`.

    Examples:
        >>> # Group by agent_name.
        >>> AgentGroupByRef(source="field", key="agent_name")
        >>> # Group by a user-defined string attribute "tenant".
        >>> AgentGroupByRef(source="custom_attrs_string", key="tenant")
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
    """Resolve the output alias the server uses for a group-by ref.

    The single source of truth for the alias resolution rules. Both
    request validation and SQL projection call this so both sides
    agree on what key ends up in `AgentSpanGroupRow.group_keys`.

    Args:
        ref: A group-by ref from `AgentSpansQueryReq.group_by` or
            `AgentSpanStatsReq.group_by`.

    Returns:
        Explicit `ref.alias` when set; the semconv-resolved column
        name for `field`/`column` sources; the raw `ref.key`
        otherwise.

    Examples:
        >>> group_by_ref_alias(
        ...     AgentGroupByRef(source="field", key="agent.name")
        ... )
        'agent_name'
    """
    if ref.alias is not None:
        return ref.alias
    if ref.source in _FIELD_GROUP_BY_SOURCES:
        return semconv.FILTERABLE_KEY_TO_COLUMN.get(ref.key, ref.key)
    return ref.key


class AgentSpanGroupDistributionSpec(BaseModel):
    """Custom attribute distribution attached to each returned span group.

    Pass on `AgentSpansQueryReq.group_distributions`. For each group
    in the response, the server adds an
    `AgentSpanGroupDistributionItem` under
    `AgentSpanGroupRow.distributions[alias]` summarizing the
    distribution of one custom attribute across that group's spans.

    Numeric attributes (`custom_attrs_int`, `custom_attrs_float`)
    produce a `bins`-wide histogram. Categorical attributes
    (`custom_attrs_string`, `custom_attrs_bool`) produce a `top_n`
    list.

    Note: currently limited to a single `group_by` ref on the parent
    request. See `AgentSpansQueryReq.validate_spans_query_request`.

    Args:
        alias: Output key in `AgentSpanGroupRow.distributions`.
        value: Custom attribute to summarize. `value.source` must be
            one of the `custom_attrs_*` sources.
        bins: Histogram bin count for numeric attributes, 1 to
            `MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_BINS`. Ignored for
            categorical attributes.
        top_n: Maximum categorical values returned, 1 to
            `MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_TOP_N`. Ignored for
            numeric attributes.

    Raises:
        ValueError: When `value.source` is not a custom attribute
            source.

    Examples:
        >>> # Top 10 values of a string attribute named "tenant".
        >>> AgentSpanGroupDistributionSpec(
        ...     alias="tenants",
        ...     value=AgentSpanValueRef(
        ...         source="custom_attrs_string", key="tenant"
        ...     ),
        ...     top_n=10,
        ... )
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

    Args:
        index: 0-based bucket position within the histogram. Clients
            render bins in `index` order, so this doubles as a stable
            sort key.
        min: Lower bound, inclusive.
        max: Upper bound, exclusive (inclusive on the final bucket).
        count: Spans whose attribute value fell in this bucket.

    Examples:
        >>> AgentSpanGroupDistributionBin(index=0, min=0.0, max=10.0, count=42)
    """

    index: int
    min: float
    max: float
    count: int


class AgentSpanGroupDistributionValue(BaseModel):
    """One observed value in a categorical distribution.

    Args:
        value: The attribute value, stringified for transport.
        count: Spans in the group that carried this value.

    Examples:
        >>> AgentSpanGroupDistributionValue(value="prod", count=17)
    """

    value: str
    count: int


class AgentSpanGroupDistributionItem(BaseModel):
    """Distribution result inside an `AgentSpanGroupRow`.

    Returned in `AgentSpanGroupRow.distributions` keyed by the
    requesting `AgentSpanGroupDistributionSpec.alias`. Numeric
    attribute requests populate `bins`; categorical requests populate
    `values`. The four `*_count` fields always sum to `total_count`.

    Args:
        alias: Echoes the requesting spec's `alias`.
        source: Custom attribute source that produced the
            distribution.
        key: Attribute key inside the source map.
        value_type: Inferred attribute type.
        total_count: Spans evaluated for the distribution.
        present_count: Spans where the attribute was set.
        missing_count: Spans where the attribute was absent.
        other_count: Spans whose values fell outside `bins` or below
            the `top_n` cutoff.
        bins: Histogram bins. Populated for numeric distributions
            only.
        values: Top values. Populated for categorical distributions
            only.

    Examples:
        >>> item = AgentSpanGroupDistributionItem(
        ...     alias="tenants",
        ...     source="custom_attrs_string",
        ...     key="tenant",
        ...     value_type="string",
        ... )
        >>> item.total_count
        0
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
    """Length-capped message snippet on a conversation group row.

    Populated on `AgentSpanGroupRow.first_message` and
    `AgentSpanGroupRow.last_message` when grouping by
    `conversation_id`. Lets the conversations table render teaser text
    without a per-row hydration query.

    Args:
        role: Chat-timeline message type (`user_message`,
            `assistant_message`, etc.). Matches `AgentChatMessage.type`
            so previews style identically to the full chat view.
        text: Trimmed preview content. Empty when no renderable text
            was available on the source span.

    Examples:
        >>> AgentConversationMessagePreview(
        ...     role="user_message", text="Hello, can you help me?"
        ... )
    """

    role: str = ""
    text: str = ""


class AgentSpanGroupRow(BaseModel):
    """One aggregated row in `AgentSpansQueryRes.groups`.

    Returned by `agent_spans_query` in group mode. The fixed aggregate
    bundle (`span_count`, the `total_*_tokens` family, `first_seen`,
    `last_seen`, etc.) is always present; `metrics` and
    `distributions` are populated when the request supplied the
    corresponding spec.

    Note: `first_message` and `last_message` are populated only when
    grouping by `conversation_id`. Cost fields use `None` (not `0`)
    to mean "no priced model matched in this group."

    Args:
        group_keys: Group-by values for the row, keyed by the
            resolved alias (see `group_by_ref_alias`).
        span_count: Total spans in the group.
        invocation_count: Spans where
            `operation_name == "invoke_agent"`.
        conversation_count: Distinct `conversation_id` values in the
            group.
        total_input_tokens: Sum of `input_tokens`.
        total_cache_creation_input_tokens: Sum of
            `cache_creation_input_tokens`.
        total_cache_read_input_tokens: Sum of
            `cache_read_input_tokens`.
        total_output_tokens: Sum of `output_tokens`.
        total_reasoning_tokens: Sum of `reasoning_tokens`.
        total_duration_ms: Sum of span wall-clock durations.
        error_count: Spans with `status_code == "Error"`.
        total_cost_usd: Sum of `total_cost_usd` across the group's
            spans. Opt-in via `include_costs`.
        total_input_cost_usd: Sum of `input_cost_usd`. Opt-in.
        total_output_cost_usd: Sum of `output_cost_usd`. Opt-in.
        agent_names: Distinct `agent_name` values in the group.
        agent_versions: Distinct `agent_version` values.
        provider_names: Distinct `provider_name` values.
        request_models: Distinct `request_model` values.
        conversation_names: Distinct `conversation_name` values.
        first_seen: Earliest `started_at` in the group. UTC.
        last_seen: Latest `started_at` in the group. UTC.
        first_message: Preview of the earliest renderable message in
            the group. Conversation grouping only.
        last_message: Preview of the latest renderable message in
            the group. Conversation grouping only.
        metrics: Per-measure aggregates keyed by
            `AgentSpanMeasureSpec.alias`.
        distributions: Per-distribution data keyed by
            `AgentSpanGroupDistributionSpec.alias`.

    Examples:
        >>> row = AgentSpanGroupRow(
        ...     group_keys={"agent_name": "research-bot"},
        ...     span_count=128,
        ...     invocation_count=64,
        ...     error_count=2,
        ... )
        >>> row.metrics
        {}
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
    """Two-mode span query for the `agent_spans_query` endpoint.

    One endpoint, two output shapes, picked by `group_by`:

    1. **List mode** — `group_by` empty or omitted. Returns one
       `AgentSpanSchema` per matched span in
       `AgentSpansQueryRes.spans`. Backs the spans table and
       single-trace drill-downs.
    2. **Group mode** — `group_by` set. Returns one
       `AgentSpanGroupRow` per group in `AgentSpansQueryRes.groups`,
       with optional `measures` and `distributions`. Backs the
       agents, versions, and conversations lists (group by
       `conversation_id`).

    Note: `group_by` is the discriminator. Setting any group-only
    field (`measures`, `group_filters`, `group_distributions`)
    without `group_by` is a validation error. `include_details` and
    `custom_attr_columns` are list-mode only.

    Args:
        project_id: Target project in `entity/project` form.
        query: Optional Mongo-style filter. Field names resolve via
            GenAI semconv, direct span columns, or typed custom
            attribute keys.
        group_by: Refs to group by. Triggers group mode when
            non-empty.
        measures: Aggregated measures per group.
        group_filters: Range filters applied to aggregated measures.
        group_distributions: Per-group custom attribute
            distributions. Limited to one `group_by` ref.
        custom_attr_columns: Extra custom attribute values to project
            on each span row. List mode only.
        include_details: Include large fields (messages, tool
            payloads, `raw_span_dump`) on each span row. List mode
            only; intended for single-trace fetches, not list views.
        include_costs: Compute query-time USD costs by joining each
            span's model against `llm_token_prices`.
        sort_by: Sort steps. Allowed fields validated server-side.
        limit: Max rows, 0 to `MAX_AGENT_QUERY_LIMIT`.
        offset: Rows to skip.
        started_after: Filter `started_at >= start`.
        started_before: Filter `started_at < end`.

    Raises:
        ValueError: When group-only fields are set without
            `group_by`, when `custom_attr_columns` or
            `include_details` is combined with `group_by`, when
            `group_distributions` has more than one `group_by` ref,
            when `custom_attr_columns` aren't custom-attr sources,
            or when measure/distribution aliases collide or
            duplicate.

    Examples:
        >>> # List the conversations for one agent, grouped by id.
        >>> AgentSpansQueryReq(
        ...     project_id="your-team/your-project",
        ...     group_by=[
        ...         AgentGroupByRef(source="field", key="conversation_id"),
        ...     ],
        ...     include_costs=True,
        ... )
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
    """Response from `agent_spans_query`.

    Exactly one of `spans` or `groups` is populated, mirroring the
    request's list/group mode discriminator.

    Args:
        spans: Raw span rows. Populated in list mode.
        groups: Aggregated group rows. Populated in group mode.
        total_count: Total rows that matched the filter before
            `limit`/`offset`.

    Examples:
        >>> res = AgentSpansQueryRes(total_count=1)
        >>> res.spans, res.groups
        ([], [])
    """

    spans: list[AgentSpanSchema] = Field(default_factory=list)
    groups: list[AgentSpanGroupRow] = Field(default_factory=list)
    total_count: int = 0


class AgentCustomAttrsSchemaReq(BaseModel):
    """Discovery request for custom attribute keys.

    Run before constructing filters, group-bys, or distributions that
    target user-defined attributes. The response tells the client
    which `(source, key, value_type)` triples actually exist in the
    data.

    Args:
        project_id: Target project in `entity/project` form.
        query: Optional Mongo-style filter narrowing the discovery
            scan.
        started_after: Filter `started_at >= start`.
        started_before: Filter `started_at < end`.
        limit: Maximum keys returned, 1 to
            `MAX_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT`.
        offset: Keys to skip for pagination.

    Examples:
        >>> AgentCustomAttrsSchemaReq(project_id="your-team/your-project")
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
    """One discovered custom attribute key.

    Args:
        source: Which typed Map column the key lives in
            (`custom_attrs_string`/`int`/`float`/`bool`).
        key: Attribute key as recorded by the producing span.
        value_type: Inferred value type.
        span_count: Spans in the discovery scope that carried the
            key.

    Examples:
        >>> AgentCustomAttrSchemaItem(
        ...     source="custom_attrs_string",
        ...     key="tenant",
        ...     value_type="string",
        ...     span_count=42,
        ... )
    """

    source: AgentCustomAttrSource
    key: str
    value_type: AgentCustomAttrValueType
    span_count: int


class AgentCustomAttrsSchemaRes(BaseModel):
    """Response from `agent_custom_attrs_schema`.

    Feed each entry's `(source, key)` back into `AgentSpansQueryReq`
    and `AgentSpanStatsReq` through the matching `custom_attrs_*`
    source on `AgentSpanValueRef`/`AgentGroupByRef`.

    Args:
        attributes: One entry per discovered key.
        limit: Echoes the request limit.
        offset: Echoes the request offset.
        has_more: `True` when at least one more page is available.

    Examples:
        >>> res = AgentCustomAttrsSchemaRes(has_more=False)
        >>> res.attributes
        []
    """

    attributes: list[AgentCustomAttrSchemaItem] = Field(default_factory=list)
    limit: int = DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT
    offset: int = 0
    has_more: bool = False


# ---------------------------------------------------------------------------
# Agent full-text search
# ---------------------------------------------------------------------------


class AgentSearchReq(BaseModel):
    """Two-mode message search for the `agent_search` endpoint.

    Backed by the `messages` materialized view (one row per message
    occurrence, fed from spans). Two ways to use it:

    1. **Full-text search** — set `query` to a substring. The
       structured filters narrow the scope (e.g. "assistant messages
       from agent X in the last week").
    2. **Structured retrieval** — leave `query` empty and use only
       the structured filters (e.g. set `trace_id` to fetch every
       message in a trace). Pair with `truncate_content=False` to
       receive full bodies.

    Note: results are grouped by conversation in the response shape,
    not by trace. One conversation can contain matches from multiple
    traces.

    Args:
        project_id: Target project in `entity/project` form.
        query: Content substring. Empty disables the content filter.
        trace_id: Restrict to messages in this trace.
        roles: Restrict to these message roles.
        conversation_id: Restrict to messages in this conversation.
        agent_name: Restrict to messages from this agent.
        provider_name: Restrict to messages from this provider.
        request_model: Restrict to messages from this model.
        truncate_content: `True` (default) returns previews; `False`
            returns full message bodies. Flip to `False` for
            structured retrieval, not for ad-hoc search UIs because
            payloads get large.
        started_after: Filter `started_at >= start`.
        started_before: Filter `started_at < end`.
        limit: Max messages, 0 to `MAX_SEARCH_LIMIT`.
        offset: Messages to skip for pagination.

    Examples:
        >>> # Full-text search across all messages in a project.
        >>> AgentSearchReq(
        ...     project_id="your-team/your-project",
        ...     query="rate limit",
        ... )
        >>> # Structured retrieval: every message in one trace.
        >>> AgentSearchReq(
        ...     project_id="your-team/your-project",
        ...     trace_id="t1",
        ...     truncate_content=False,
        ... )
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
    """One message hit in an `AgentSearchRes`.

    Args:
        span_id: Span that produced the message.
        trace_id: Trace containing the span.
        role: Message role (`user`, `assistant`, `tool`, etc.).
        content_preview: Trimmed preview, or full body when the
            request set `truncate_content=False`.
        content_digest: Stable digest of the full content. Useful for
            deduplicating identical messages across re-runs.
        started_at: Time the producing span started. UTC.

    Examples:
        >>> AgentSearchMatchedMessage(
        ...     span_id="s1",
        ...     trace_id="t1",
        ...     role="assistant",
        ...     content_preview="Sure, I can help with that.",
        ...     content_digest="abc123",
        ...     started_at=datetime.datetime(
        ...         2026, 6, 1, tzinfo=datetime.timezone.utc
        ...     ),
        ... )
    """

    span_id: str
    trace_id: str
    role: SearchMessageRole
    content_preview: str
    content_digest: str
    started_at: datetime.datetime


class AgentSearchConversationResult(BaseModel):
    """One conversation's matching messages, the row shape of `AgentSearchRes`.

    Args:
        conversation_id: Conversation identifier shared by every
            entry in `matched_messages`.
        conversation_name: Human-readable conversation label.
        agent_name: Agent that owns the conversation.
        matched_messages: Matching messages, in chronological order.
        last_activity: Time of the most recent matching message. UTC.

    Examples:
        >>> AgentSearchConversationResult(
        ...     conversation_id="c1",
        ...     conversation_name="Customer support session",
        ...     agent_name="support-bot",
        ...     matched_messages=[],
        ...     last_activity=datetime.datetime(
        ...         2026, 6, 1, tzinfo=datetime.timezone.utc
        ...     ),
        ... )
    """

    conversation_id: str
    conversation_name: str
    agent_name: str
    matched_messages: list[AgentSearchMatchedMessage]
    last_activity: datetime.datetime


class AgentSearchRes(BaseModel):
    """Response from `agent_search`.

    Args:
        results: One entry per conversation containing a match.
        total_conversations: Conversations matched before
            `limit`/`offset`.

    Examples:
        >>> AgentSearchRes(results=[], total_conversations=0)
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
    """Payload for the `user_message` branch of `AgentChatMessage`.

    Args:
        text: Rendered user prompt text.
        content_refs: Refs to detached content blobs (e.g. uploaded
            images).

    Examples:
        >>> AgentChatUserMessage(text="What's the weather in Paris?")
    """

    text: str
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAssistantMessage(BaseModel):
    """Payload for the `assistant_message` branch of `AgentChatMessage`.

    Carries one assistant response, plus the LLM-call metadata the
    chat-view assembler folded in from the underlying span (model,
    token counts, costs, status).

    Note: the `*_cost_usd` fields use `None` (not `0`) to mean "no
    priced model matched." For aggregated agent turns, cost fields
    are summed across the agent's whole subtree.

    Args:
        text: Rendered assistant response text.
        model: Model that produced the response.
        reasoning_content: Reasoning text from a reasoning-capable
            model.
        reasoning_tokens: Reasoning tokens consumed.
        input_tokens: Prompt tokens for this message's span.
        output_tokens: Completion tokens for this message's span.
        input_cost_usd: Input-token cost in USD.
        output_cost_usd: Output-token cost in USD.
        total_cost_usd: Sum of input and output costs.
        duration_ms: Wall-clock duration of the producing span.
        status: OTel status code from the producing span.
        content_refs: Refs to detached content blobs.

    Examples:
        >>> AgentChatAssistantMessage(
        ...     text="It's sunny and 24°C in Paris.",
        ...     model="gpt-4o",
        ...     input_tokens=120,
        ...     output_tokens=18,
        ... )
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
    """Payload for the `tool_call` branch of `AgentChatMessage`.

    Folds the LLM's tool-call request and the matching `execute_tool`
    span result into one timeline event.

    Args:
        tool_name: Tool name as registered with the agent.
        tool_arguments: JSON-encoded arguments passed to the tool.
        tool_result: Serialized tool result.
        duration_ms: Wall-clock duration of the `execute_tool` span.
        status: OTel status code from the `execute_tool` span.
        content_refs: Refs to detached content blobs attached to the
            call or its result.

    Examples:
        >>> AgentChatToolCall(
        ...     tool_name="search_web",
        ...     tool_arguments='{"query": "weather in Paris"}',
        ...     tool_result='{"temperature_c": 24, "condition": "sunny"}',
        ... )
    """

    tool_name: str | None = None
    tool_arguments: str | None = None
    tool_result: str | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAgentStart(BaseModel):
    """Payload for the `agent_start` branch of `AgentChatMessage`.

    Marks an `invoke_agent` boundary and carries the system
    instructions and tool catalog the model was given for the
    invocation.

    Args:
        model: Model bound to the agent for this invocation.
        system_instructions: System prompt set on the agent.
        tool_definitions: Serialized tool catalog provided to the
            agent.
        status: OTel status code from the `invoke_agent` span.

    Examples:
        >>> AgentChatAgentStart(
        ...     model="gpt-4o",
        ...     system_instructions="You are a helpful weather assistant.",
        ... )
    """

    model: str | None = None
    system_instructions: str | None = None
    tool_definitions: str | None = None
    status: StatusCodeLiteral | None = None


class AgentChatAgentHandoff(BaseModel):
    """Payload for the `agent_handoff` branch of `AgentChatMessage`.

    Reserved for handoff semantics in multi-agent frameworks. No
    fields yet, but present so the timeline model is
    forward-compatible with handoff-aware UIs.

    Examples:
        >>> AgentChatAgentHandoff()
    """


class AgentChatContextCompacted(BaseModel):
    """Payload for the `context_compacted` branch of `AgentChatMessage`.

    Emitted when an agent rewrites its context window to fit within
    the model's token budget.

    Args:
        compaction_summary: Summary of what was compacted.
        compaction_items_before: Message items before compaction.
        compaction_items_after: Message items after compaction.

    Examples:
        >>> AgentChatContextCompacted(
        ...     compaction_summary="Earlier conversation about Paris weather.",
        ...     compaction_items_before=40,
        ...     compaction_items_after=8,
        ... )
    """

    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None


class AgentChatMessage(BaseModel):
    """One event in the agent trajectory / chat timeline.

    The chat view flattens a trace's span tree into a linear list of
    these. Each event is one of six discriminated kinds (see
    `AgentChatMessageType`); the payload field whose name matches
    `type` is populated, and all other payload fields must be `None`.

    Common header fields (`span_id`, `agent_name`, `started_at`, etc.)
    live at the top so callers render headers and filters without
    unwrapping the payload.

    Note: exactly one payload must be set, and it must match `type`.
    The validator rejects mismatched or missing payloads, which
    prevents drift between the discriminator and the data.

    Args:
        type: Event kind. Picks which payload field is populated.
        span_id: Producing span ID, when one exists.
        agent_name: Agent that produced the event.
        agent_version: Agent version that produced the event.
        status_code: OTel status code from the producing span.
        started_at: Event start time. UTC.
        user_message: Payload when `type="user_message"`.
        assistant_message: Payload when `type="assistant_message"`.
        tool_call: Payload when `type="tool_call"`.
        agent_start: Payload when `type="agent_start"`.
        agent_handoff: Payload when `type="agent_handoff"`.
        context_compacted: Payload when `type="context_compacted"`.
        feedback: Feedback rows attached to this event. Populated
            only when the parent request set `include_feedback=True`.

    Raises:
        ValueError: When the payload field matching `type` is
            missing, or when any other payload field is also set.

    Examples:
        >>> AgentChatMessage(
        ...     type="user_message",
        ...     span_id="s1",
        ...     user_message=AgentChatUserMessage(
        ...         text="What's the weather in Paris?"
        ...     ),
        ... )
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
    """Single-turn chat-view request for `agent_traces_chat`.

    Folds the trace's span tree into a linear `AgentChatMessage`
    timeline ready to render top-to-bottom. Pair with
    `AgentTraceChatRes`.

    Args:
        project_id: Target project in `entity/project` form.
        trace_id: OTel trace ID for the turn to render.
        include_feedback: Attach feedback rows on the response and on
            each message that has any. `False` by default to keep
            payloads small.

    Examples:
        >>> AgentTraceChatReq(
        ...     project_id="your-team/your-project",
        ...     trace_id="t1",
        ...     include_feedback=True,
        ... )
    """

    project_id: str
    trace_id: str
    include_feedback: bool = False


class AgentTraceChatRes(BaseModel):
    """Single-turn chat view, the response of `agent_traces_chat`.

    Header fields summarize the trace (agent identity, status,
    duration, cost); `messages` is the ordered chat timeline. The
    same shape is reused inside `AgentConversationChatRes.turns`, so
    one client renderer covers both single-turn and per-turn views.

    Note: `total_duration_ms` is the root span's wall-clock duration,
    not a sum across child spans. `total_cost_usd` is a sum across
    every span in the trace.

    Args:
        trace_id: OTel trace ID echoed from the request.
        root_span_name: Name of the trace's root span.
        agent_name: Agent that owns the trace.
        agent_version: Agent version that produced the trace.
        status_code: OTel status of the root span.
        provider: Provider name reported by the root span.
        total_duration_ms: Wall-clock duration of the root span.
        total_cost_usd: Sum of `total_cost_usd` across every span in
            the trace. `None` signals no priced model matched.
        messages: Chat timeline in chronological order.
        feedback: Trace-level feedback rows. Populated only when the
            request set `include_feedback=True`.

    Examples:
        >>> AgentTraceChatRes(
        ...     trace_id="t1",
        ...     agent_name="research-bot",
        ...     status_code="Ok",
        ...     total_duration_ms=420,
        ... )
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
    """Multi-turn chat-view request for `agent_conversation_chat`.

    Returns an ordered page of turns that share one
    `conversation_id`. The id is `gen_ai.conversation.id` on the
    producing spans.

    Args:
        project_id: Target project in `entity/project` form.
        conversation_id: Conversation identifier.
        limit: Max turns returned per page, 0 to
            `MAX_CONVERSATION_CHAT_TURNS`.
        offset: Most-recent turns to skip. Within the selected page,
            turns are returned in chronological order.
        include_feedback: Attach feedback rows to each turn and
            message that has any.

    Examples:
        >>> AgentConversationChatReq(
        ...     project_id="your-team/your-project",
        ...     conversation_id="c1",
        ...     limit=10,
        ... )
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
    """Multi-turn chat view, the response of `agent_conversation_chat`.

    `turns` is an ordered list of per-turn `AgentTraceChatRes` rows,
    so the client reuses single-turn rendering for each one.
    Conversation-level totals (cost, feedback) sit on the parent
    response.

    Note: one turn corresponds to one trace, not one `invoke_agent`
    span. A turn can contain zero, one, or many agent invocations.

    Args:
        conversation_id: Echoes the request.
        turns: Per-turn chat views in chronological order.
        total_turns: Turns in the conversation before
            `limit`/`offset`.
        has_more: `True` when another page is available.
        limit: Echoes the request limit.
        offset: Echoes the request offset.
        total_cost_usd: Sum of `total_cost_usd` across the returned
            turns. `None` signals no priced model matched.
        feedback: Conversation-level feedback rows. Populated only
            when the request set `include_feedback=True`.

    Examples:
        >>> AgentConversationChatRes(conversation_id="c1", total_turns=3)
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
    """One aggregated row from the agents materialized view.

    Returned in `AgentsQueryRes.agents`. One row per `agent_name`,
    summarizing every span attributed to that agent across all
    versions and conversations. Backs the entry point of the Agents
    view.

    Note: `total_cost_usd` is filled by a supplementary grouped spans
    query because the agents MV has no cost column. It uses `None`
    (not `0`) to mean "costs weren't requested or no priced model
    matched."

    Args:
        project_id: Owning project in `entity/project` form.
        agent_name: Agent identifier.
        invocation_count: `invoke_agent` spans attributed to the
            agent.
        span_count: Total spans attributed to the agent.
        total_input_tokens: Sum of `input_tokens`.
        total_output_tokens: Sum of `output_tokens`.
        total_duration_ms: Sum of span wall-clock durations.
        error_count: Spans with `status_code == "Error"`.
        first_seen: Earliest `started_at` for the agent. UTC.
        last_seen: Latest `started_at` for the agent. UTC.
        total_cost_usd: Opt-in summed cost in USD.

    Examples:
        >>> AgentSchema(
        ...     project_id="your-team/your-project",
        ...     agent_name="research-bot",
        ...     invocation_count=42,
        ...     span_count=210,
        ...     total_input_tokens=12345,
        ...     total_output_tokens=6789,
        ...     total_duration_ms=58000,
        ...     error_count=1,
        ...     first_seen=None,
        ...     last_seen=None,
        ... )
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
    """Optional filters block for `AgentsQueryReq`.

    Args:
        agent_name: Exact-match filter on agent name. `None` matches
            every agent in the project.

    Examples:
        >>> AgentsQueryFilters(agent_name="research-bot")
    """

    agent_name: str | None = None


class AgentsQueryReq(BaseModel):
    """Agent listing request for `agent_agents_query`.

    Entry point for the Agents view. Drill into a specific agent's
    versions with `AgentVersionsQueryReq`; drill into its
    conversations with `AgentSpansQueryReq` in group mode.

    Args:
        project_id: Target project in `entity/project` form.
        filters: Optional narrowing of which agents are returned.
        sort_by: Sort steps. Allowed fields validated server-side.
        limit: Max rows, 0 to `MAX_AGENT_QUERY_LIMIT`.
        offset: Rows to skip.
        include_costs: Opt into supplementary cost computation for
            `AgentSchema.total_cost_usd`.

    Examples:
        >>> AgentsQueryReq(
        ...     project_id="your-team/your-project", include_costs=True
        ... )
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
    """Response from `agent_agents_query`.

    Args:
        agents: One `AgentSchema` per matched agent.
        total_count: Agents matched before `limit`/`offset`.

    Examples:
        >>> AgentsQueryRes(agents=[], total_count=0)
    """

    agents: list[AgentSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# Agent versions (from agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(AgentSchema):
    """`AgentSchema` row keyed by `(agent_name, agent_version)`.

    Returned by `agent_versions_query`. Extends `AgentSchema` with
    `agent_version`; every other field has the same meaning.

    Args:
        agent_version: Version label on the producing spans.

    Examples:
        >>> AgentVersionSchema(
        ...     project_id="your-team/your-project",
        ...     agent_name="research-bot",
        ...     agent_version="2026-06-01",
        ...     invocation_count=10,
        ...     span_count=42,
        ...     total_input_tokens=1000,
        ...     total_output_tokens=500,
        ...     total_duration_ms=12000,
        ...     error_count=0,
        ...     first_seen=None,
        ...     last_seen=None,
        ... )
    """

    agent_version: str


class AgentVersionsQueryReq(BaseModel):
    """Version-listing request for `agent_versions_query`.

    Run after `agent_agents_query` to diff behavior across releases
    of one agent.

    Args:
        project_id: Target project in `entity/project` form.
        agent_name: Agent to enumerate versions for.
        sort_by: Sort steps. Allowed fields validated server-side.
        limit: Max rows, 0 to `MAX_AGENT_QUERY_LIMIT`.
        offset: Rows to skip.
        include_costs: Opt into supplementary cost computation for
            `AgentVersionSchema.total_cost_usd`.

    Examples:
        >>> AgentVersionsQueryReq(
        ...     project_id="your-team/your-project",
        ...     agent_name="research-bot",
        ... )
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
    """Response from `agent_versions_query`.

    Args:
        versions: One `AgentVersionSchema` per matched `(agent_name,
            agent_version)` pair.
        total_count: Versions matched before `limit`/`offset`.

    Examples:
        >>> AgentVersionsQueryRes(versions=[], total_count=0)
    """

    versions: list[AgentVersionSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# OTel ingest types
# ---------------------------------------------------------------------------


class GenAIOTelExportReq(BaseModel):
    """Ingest request for `genai_otel_export`.

    The single write-side entry point in this module. Sits at the
    start of the workflow: spans flow in here from the SDK or a raw
    OTel exporter, land in the agent spans table, and refresh the
    downstream materialized views (agents, agent_versions, messages)
    that the read-side endpoints query.

    Note: carries `ProcessedResourceSpans` (post-deserialization), not
    the raw protobuf payload. The model sets
    `arbitrary_types_allowed=True` because Pydantic doesn't have a
    schema for the OTel proto type.

    Args:
        processed_spans: Deserialized OTel resource spans to ingest.
        project_id: Target project in `entity/project` form.
        wb_user_id: Optional W&B user ID to record on each span.

    Examples:
        >>> # Construct an empty ingest call against your project.
        >>> GenAIOTelExportReq(
        ...     processed_spans=[],
        ...     project_id="your-team/your-project",
        ... )
    """

    model_config = {"arbitrary_types_allowed": True}

    processed_spans: list[ProcessedResourceSpans] = Field(
        ..., description="List of ProcessedResourceSpans from OTel deserialization"
    )
    project_id: str
    wb_user_id: str | None = None


class GenAIOTelExportRes(BaseModel):
    """Response from `genai_otel_export`.

    Note: rejected spans don't block the rest of the batch. Inspect
    `error_message` for a summary of why some were dropped.

    Args:
        accepted_spans: Spans that passed extraction and were
            enqueued for insertion.
        rejected_spans: Spans the server skipped.
        error_message: Short summary of the rejection cause when
            `rejected_spans > 0`. Empty when everything succeeded.

    Examples:
        >>> GenAIOTelExportRes(accepted_spans=100)
    """

    accepted_spans: int = 0
    rejected_spans: int = 0
    error_message: str = ""
