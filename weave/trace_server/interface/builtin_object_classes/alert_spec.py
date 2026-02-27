from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class WeaveMetricThresholdSpec(BaseModel):
    """Alert specification for weave metric threshold alerts.

    Fields align with gorilla's WeaveMetricThresholdFilter and the
    alert_worker's WeaveMetricFilter.  Extra keys are permitted so that
    the schema can evolve without breaking existing stored objects.
    """

    model_config = ConfigDict(extra="allow")

    alert_condition: str = Field(
        default="THRESHOLD",
        description="Trigger condition type (e.g. 'THRESHOLD')",
    )
    comparison_operator: Literal["GREATER_THAN", "LESS_THAN", "EQUAL"] = Field(
        default="GREATER_THAN",
        description="Direction of the threshold comparison",
    )
    metric_path: str = Field(
        default="",
        description="Dot-notation path to the metric value in the call (e.g. 'output.score')",
    )
    op_str: str = Field(
        default="",
        description="Op or scorer ref to scope this alert to; empty means all ops",
    )
    threshold: float = Field(
        default=0.0,
        description="Threshold value that triggers the alert",
    )
    window_size: int | None = Field(
        default=None,
        description="Max number of recent calls to include in the window",
    )
    window_duration: int | None = Field(
        default=None,
        description="Time window in seconds for historical calls",
    )
    monitor_ref: str | None = Field(
        default=None,
        description="Monitor ref; presence indicates alert was created from a monitor",
    )
    scorer_ref: str | None = Field(
        default=None,
        description="Scorer object ref identifying which scorer instance within a monitor to alert on. "
        "Disambiguates scorers that share the same op class (e.g. multiple LLMAsAJudgeScorer instances). "
        "Filterable via inputs.self on scorer calls or input_refs on CallsFilter.",
    )
    source_type: Literal["op", "monitor", "feedback"] | None = Field(
        default=None,
        description="Data source type for the alert. None or 'op' means call-based, "
        "'monitor' means monitor-based, 'feedback' means feedback-based.",
    )
    feedback_type_filter: str | None = Field(
        default=None,
        description="Feedback type to filter on (e.g. 'wandb.runnable.my_scorer'). "
        "Required when source_type='feedback'.",
    )
    aggregation_mode: Literal["per_trace", "all"] | None = Field(
        default=None,
        description="How to aggregate feedback metrics. 'per_trace' groups by trace_id, "
        "'all' considers all matching feedback. Required when source_type='feedback'.",
    )


class AlertSpec(base_object_def.BaseObject):
    op_scope: list[str] | None = Field(
        default=None,
        description="If provided, this alert only applies to calls from the given op refs",
        examples=[
            ["weave:///entity/project/op/name:digest"],
            ["weave:///entity/project/op/name:*"],
        ],
    )

    spec: WeaveMetricThresholdSpec = Field(
        default_factory=WeaveMetricThresholdSpec,
        description="Alert specification (threshold config, window config, etc.)",
    )
