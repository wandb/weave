from typing import Literal, get_args

from pydantic import Field
from typing_extensions import NotRequired, Self, TypedDict

from weave.flow.casting import Scorer
from weave.object.obj import Object
from weave.trace.api import ObjectRef, publish
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject
from weave.trace_server.interface.query import Query

SinkEntityType = Literal["span", "conversation"]

DebounceAggregationField = Literal["trace_id", "thread_id"]
DebounceAggregationMethod = Literal["last_message", "all_messages"]

# Runtime-valid sets derived from Literals above
VALID_DEBOUNCE_AGGREGATION_FIELDS: frozenset[DebounceAggregationField] = frozenset(
    get_args(DebounceAggregationField)
)
VALID_DEBOUNCE_AGGREGATION_METHODS: frozenset[DebounceAggregationMethod] = frozenset(
    get_args(DebounceAggregationMethod)
)


class ScorerDebounceConfig(TypedDict):
    """Configuration for debounced scoring on a monitor."""

    # Specifies which field is used to find candidates for debouncing
    aggregation_field: DebounceAggregationField

    # How to aggregate messages for scoring: last message only or all messages in the window.
    # Defaults to last_message when not present.
    aggregation_method: NotRequired[DebounceAggregationMethod]

    # Timeframe for the debouncing. Messages received within this timeframe will be debounced.
    timeout_seconds: float


@register_object
class Monitor(Object):
    """Sets up a monitor to score incoming calls automatically.

    Examples:
    ```python
    import weave
    from weave.scorers import ValidJSONScorer

    json_scorer = ValidJSONScorer()

    my_monitor = weave.Monitor(
        name="my-monitor",
        description="This is a test monitor",
        sampling_rate=0.5,
        op_names=["my_op"],
        query={
            "$expr": {
                "$gt": [
                    {
                            "$getField": "started_at"
                        },
                        {
                            "$literal": 1742540400
                        }
                    ]
                }
            }
        },
        scorers=[json_scorer],
    )

    my_monitor.activate()
    ```
    """

    sampling_rate: float = Field(ge=0, le=1, default=1)
    scorers: list[Scorer]
    op_names: list[str] = Field(default_factory=list)
    query: Query | None = None
    is_traced: bool = Field(
        default=True,
        description="Trace this monitor's scorers and any downstream LLM calls.",
    )
    active: bool = False

    # Debounced scoring is enabled when this is present, and disabled when it is not.
    scorer_debounce_config: ScorerDebounceConfig | None = None

    def activate(self) -> ObjectRef:
        """Activates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = True
        self.ref = None
        return publish(self)

    def deactivate(self) -> ObjectRef:
        """Deactivates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = False
        self.ref = None
        return publish(self)

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls.model_validate(obj.unwrap())


@register_object
class ClassifierMonitor(Monitor):
    """A monitor that merges multiple scorers into a single classifier.

    Classifier monitors combine prompts from multiple LLMAsAJudgeScorers
    targeting the same model into a single scoring call.
    """

    prompt_header: str | None = Field(
        default=None,
        description="Text prepended before the merged classifier prompts.",
    )
    prompt_footer: str | None = Field(
        default=None,
        description="Text appended after the merged classifier prompts.",
    )


@register_object
class SinkMonitor(Object):
    """Scores GenAI sink entities (spans, conversations) automatically.

    Unlike Monitor which targets calls by op name, SinkMonitor targets
    GenAI spans and conversations using typed filters that map directly
    to genai_spans columns.

    Examples:
    ```python
    import weave
    from weave.scorers import LLMAsAJudgeScorer

    scorer = LLMAsAJudgeScorer(
        model=my_model,
        scoring_prompt="Evaluate whether the response is helpful.",
    )

    signal = weave.SinkMonitor(
        name="helpfulness",
        entity_type="conversation",
        scorers=[scorer],
        agent_names=["my-agent"],
    )

    signal.activate()
    ```
    """

    entity_type: SinkEntityType
    sampling_rate: float = Field(ge=0, le=1, default=1)
    scorers: list[Scorer]
    active: bool = False
    is_traced: bool = Field(
        default=True,
        description="Trace this monitor's scorers and any downstream LLM calls.",
    )

    operation_names: list[str] = Field(
        default_factory=list,
        description="Filter to spans with these operation names (chat, invoke_agent, execute_tool).",
    )
    agent_names: list[str] = Field(
        default_factory=list,
        description="Filter to spans from these agents.",
    )
    provider_names: list[str] = Field(
        default_factory=list,
        description="Filter to spans from these providers.",
    )
    model_names: list[str] = Field(
        default_factory=list,
        description="Filter to spans using these models.",
    )

    debounce_seconds: float = Field(
        default=30.0,
        description="For conversation scoring: wait this long after the last span before scoring.",
    )

    def activate(self) -> ObjectRef:
        """Activates the sink monitor."""
        self.active = True
        self.ref = None
        return publish(self)

    def deactivate(self) -> ObjectRef:
        """Deactivates the sink monitor."""
        self.active = False
        self.ref = None
        return publish(self)

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        """Construct from a WeaveObject."""
        return cls.model_validate(obj.unwrap())


@register_object
class SinkClassifierMonitor(SinkMonitor):
    """A sink monitor with an inline scoring prompt.

    Unlike calls ClassifierMonitor which references separate scorer objects,
    SinkClassifierMonitor stores the scoring prompt directly. The sink
    scoring worker builds the LLM call from these fields.
    """

    scoring_prompt: str = Field(
        default="",
        description="The LLM judge prompt used to evaluate entities.",
    )
    prompt_header: str | None = Field(
        default=None,
        description="Text prepended before the scoring prompt.",
    )
    prompt_footer: str | None = Field(
        default=None,
        description="Text appended after the scoring prompt.",
    )
