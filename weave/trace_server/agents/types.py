"""Request/response types for the Weave Agents observability API.

All types are Pydantic BaseModel subclasses used by both the FastAPI
endpoints (services/weave-trace) and the ClickHouse query handlers
(weave/trace_server/clickhouse_trace_server_batched.py).
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
    """Reference to a span field or typed custom attribute map value."""

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
    """One aggregate measure computed over spans in a group or bucket."""

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
    """Metric to extract from each matching span and aggregate into chart rows."""

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
    """Metadata describing one column in an agent span stats result row."""

    name: str
    role: Literal["time", "bucket", "group", "metric"]
    value_type: AgentSpanStatsColumnValueType
    metric: str | None = None
    aggregation: str | None = None


class AgentSpanGroupFilter(BaseModel):
    """Range filter over one grouped span measure."""

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
    """Bucket stats rows by started_at time intervals."""

    type: Literal["time"] = "time"


class AgentSpanStatsNumericBucketSpec(BaseModel):
    """Bucket stats rows by ranges of one numeric span or grouped value."""

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
    """Request chart-ready aggregations over GenAI agent spans."""

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
        max_range = datetime.timedelta(days=MAX_AGENT_STATS_RANGE_DAYS)
        if end - self.start > max_range:
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
    """Response containing chart-ready agent span stats rows."""

    start: datetime.datetime
    end: datetime.datetime
    granularity: int | None = None
    timezone: str
    bucket_type: Literal["time", "number"] = "time"
    columns: list[AgentSpanStatsColumn] = Field(default_factory=list)
    rows: list[dict[str, AgentSpanStatsCell]] = Field(default_factory=list)


class AgentSpanSchema(BaseModel):
    """A normalized agent span returned by query APIs."""

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
    """Sort specification for agent query endpoints."""

    field: str
    direction: Literal["asc", "desc"] = "desc"


class AgentGroupByRef(BaseModel):
    """Reference to a field or map-key that spans should be grouped by.

    `source="field"` targets a semantic span field (`agent.name`) or direct
    span column (`agent_name`), allowlisted server-side. `source="column"` is
    accepted for existing callers.
    The other sources target keys inside the typed custom attribute Map columns,
    which accept arbitrary user-defined keys.
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
    """Return the SQL-safe output alias for a group-by ref.

    Used for both request validation here and SQL projection in the query
    builder, so both call sites agree on what shows up in `group_keys`.
    """
    if ref.alias is not None:
        return ref.alias
    if ref.source in _FIELD_GROUP_BY_SOURCES:
        return semconv.FILTERABLE_KEY_TO_COLUMN.get(ref.key, ref.key)
    return ref.key


class AgentSpanGroupDistributionSpec(BaseModel):
    """One custom attribute distribution to compute per returned span group."""

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
    """One numeric histogram bin for a custom attribute in a span group."""

    # 0-based bucket position within the histogram; clients render bins in
    # `index` order so this can double as a stable sort key.
    index: int
    min: float
    max: float
    count: int


class AgentSpanGroupDistributionValue(BaseModel):
    """One categorical custom attribute value count in a span group."""

    value: str
    count: int


class AgentSpanGroupDistributionItem(BaseModel):
    """Distribution data for one span-group/custom-attribute pair."""

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
    """A truncated first/last message snippet for a grouped conversation row.

    `role` is the chat-timeline message type (e.g. "user_message",
    "assistant_message") so clients can style it consistently with the full
    chat view; `text` is the trimmed, length-capped preview content.
    """

    role: str = ""
    text: str = ""


class AgentSpanGroupRow(BaseModel):
    """A single row in a grouped spans query response.

    `group_keys` maps each group_by ref's alias to its value for this row.
    The remaining fields are a fixed aggregate bundle computed per group.
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
    """Request to query agent spans for a project.

    When `group_by` is empty (or omitted), returns raw span rows in the
    response's `spans` field. When `group_by` is non-empty, returns
    aggregate group rows in the response's `groups` field.
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
    """Response from a spans query.

    Exactly one of `spans` or `groups` will be populated, based on
    whether the request specified `group_by`.
    """

    spans: list[AgentSpanSchema] = Field(default_factory=list)
    groups: list[AgentSpanGroupRow] = Field(default_factory=list)
    total_count: int = 0


class AgentCustomAttrsSchemaReq(BaseModel):
    """Request to discover typed custom attribute keys for matching spans."""

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
    """One custom attribute key/type observed in the matching spans."""

    source: AgentCustomAttrSource
    key: str
    value_type: AgentCustomAttrValueType
    span_count: int


class AgentCustomAttrsSchemaRes(BaseModel):
    """Typed custom attribute keys available for spans query/group/stats APIs."""

    attributes: list[AgentCustomAttrSchemaItem] = Field(default_factory=list)
    limit: int = DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT
    offset: int = 0
    has_more: bool = False


# ---------------------------------------------------------------------------
# Agent full-text search
# ---------------------------------------------------------------------------


class AgentSearchReq(BaseModel):
    """Full-text search across message content and span metadata.

    Scans the `messages` table (one row per message occurrence, populated
    by an MV from spans) and returns matching span-level hits. The caller
    groups by conversation for the response shape.
    """

    project_id: str
    query: str

    roles: list[SearchMessageRole] | None = None
    conversation_id: str | None = None
    agent_name: str | None = None
    provider_name: str | None = None
    request_model: str | None = None
    started_after: datetime.datetime | None = None
    started_before: datetime.datetime | None = None

    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=0, le=MAX_SEARCH_LIMIT)
    offset: int = Field(default=0, ge=0)


class AgentSearchMatchedMessage(BaseModel):
    """A single message that matched the search query."""

    span_id: str
    trace_id: str
    role: SearchMessageRole
    content_preview: str
    content_digest: str
    started_at: datetime.datetime


class AgentSearchConversationResult(BaseModel):
    """A conversation containing messages that matched the search query."""

    conversation_id: str
    conversation_name: str
    agent_name: str
    matched_messages: list[AgentSearchMatchedMessage]
    last_activity: datetime.datetime


class AgentSearchRes(BaseModel):
    """Response from a full-text search across agent messages."""

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
    """Payload for a user prompt in the chat timeline."""

    text: str
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAssistantMessage(BaseModel):
    """Payload for assistant text emitted by an agent or LLM span."""

    text: str
    model: str | None = None
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatToolCall(BaseModel):
    """Payload for a tool call timeline event."""

    tool_name: str | None = None
    tool_arguments: str | None = None
    tool_result: str | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAgentStart(BaseModel):
    """Payload for an agent lifecycle boundary."""

    model: str | None = None
    system_instructions: str | None = None
    tool_definitions: str | None = None
    status: StatusCodeLiteral | None = None


class AgentChatAgentHandoff(BaseModel):
    """Payload for a future agent-to-agent handoff event."""


class AgentChatContextCompacted(BaseModel):
    """Payload for a context-window compaction event."""

    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None


class AgentChatMessage(BaseModel):
    """A single element in the structured agent trajectory / chat view.

    Common event fields live at the top level. Type-specific fields are
    grouped under the payload matching `type`, and exactly one payload must be
    set. This keeps subtype nullability explicit while preserving a single
    ordered timeline model for callers.
    """

    type: AgentChatMessageType
    span_id: str | None = None
    agent_name: str | None = None
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
    """Request to get the structured chat / trajectory view for a trace."""

    project_id: str
    trace_id: str
    include_feedback: bool = False


class AgentTraceChatRes(BaseModel):
    """Structured chat view: a linear sequence of messages representing
    the agent trajectory for a single trace.
    """

    trace_id: str
    root_span_name: str | None = None
    provider: str | None = None
    total_duration_ms: int | None = Field(
        default=None,
        description=(
            "Wall-clock duration of the trace root span in milliseconds. "
            "This is not a sum of child span durations."
        ),
    )
    messages: list[AgentChatMessage] = Field(default_factory=list)
    feedback: list[dict[str, Any]] | None = None


class AgentConversationChatReq(BaseModel):
    """Request to get the multi-turn chat view for a conversation."""

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
    """Multi-turn chat view: an ordered list of per-turn chat responses.

    Each entry in `turns` corresponds to one trace_id, which Weave treats as
    one conversation turn. This is not necessarily one `invoke_agent` span:
    a turn can contain zero, one, or many agent invocations. The frontend can
    render turn-number dividers between entries and still reuse
    `AgentTraceChatRes` rendering for each individual turn.
    """

    conversation_id: str
    turns: list[AgentTraceChatRes] = Field(default_factory=list)
    total_turns: int = 0
    has_more: bool = False
    limit: int = MAX_CONVERSATION_CHAT_TURNS
    offset: int = 0
    feedback: list[dict[str, Any]] | None = None


class AgentSchema(BaseModel):
    """Aggregated per-agent stats from the agents table."""

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


class AgentsQueryFilters(BaseModel):
    """Optional filters for querying agents."""

    agent_name: str | None = None


class AgentsQueryReq(BaseModel):
    """Request to list agents with aggregated stats for a project."""

    project_id: str
    filters: AgentsQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)


class AgentsQueryRes(BaseModel):
    """Response containing aggregated agent stats."""

    agents: list[AgentSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# Agent versions (from agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(AgentSchema):
    """Aggregated per-version stats from the agent_versions AMT."""

    agent_version: str


class AgentVersionsQueryReq(BaseModel):
    """Request to list versions for an agent."""

    project_id: str
    agent_name: str
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)


class AgentVersionsQueryRes(BaseModel):
    """Response containing agent version stats."""

    versions: list[AgentVersionSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# OTel ingest types
# ---------------------------------------------------------------------------


class GenAIOTelExportReq(BaseModel):
    """Request for the GenAI OTel ingest endpoint.

    Carries the same ProcessedResourceSpans as the standard OTel endpoint
    but routes through GenAI extraction and into spans.
    """

    model_config = {"arbitrary_types_allowed": True}

    processed_spans: list[ProcessedResourceSpans] = Field(
        ..., description="List of ProcessedResourceSpans from OTel deserialization"
    )
    project_id: str
    wb_user_id: str | None = None


class GenAIOTelExportRes(BaseModel):
    """Response for the GenAI OTel ingest endpoint."""

    accepted_spans: int = 0
    rejected_spans: int = 0
    error_message: str = ""
