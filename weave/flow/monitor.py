from typing import Literal, TypeAlias, get_args

from pydantic import Field, field_validator, model_validator
from typing_extensions import NotRequired, Self, TypedDict

from weave.flow.casting import Scorer
from weave.object.obj import Object
from weave.trace.api import ObjectRef, publish
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject
from weave.trace_server.interface.query import Query

DebounceAggregationField: TypeAlias = Literal["trace_id", "thread_id"]
DebounceAggregationMethod: TypeAlias = Literal["last_message", "all_messages"]

# Monitors can be configured to score agent spans by including an AgentSpanOpName in their `op_names` list.
AgentSpanOpName: TypeAlias = Literal["weave.genai.turn_ended"]
AGENT_SPAN_OP_NAMES: frozenset[AgentSpanOpName] = frozenset(get_args(AgentSpanOpName))

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
    op_names: list[AgentSpanOpName | str] = Field(default_factory=list)
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

    @field_validator("op_names", mode="before")
    @classmethod
    def _coerce_op_refs_to_str(cls, value: object) -> object:
        """Stored monitors deserialize op refs as `OpRef`/`ObjectRef` instances
        (weave auto-resolves URI strings into ref objects when reading). The
        field type is `list[str]`, so coerce ref objects back to their URI
        strings before type validation.
        """
        if not isinstance(value, list):
            return value
        coerced: list[object] = []
        for item in value:
            uri_fn = getattr(item, "uri", None)
            coerced.append(uri_fn() if callable(uri_fn) else item)
        return coerced

    @model_validator(mode="after")
    def _resolve_op_names(self) -> Self:
        """Rewrite short op names in `op_names` to fully-qualified op refs.

        Users may pass short op names (e.g. `"my_op"`) per the docstring example, but
        the backend and UI key off fully-qualified refs like
        `weave:///entity/project/op/my_op:digest`. The trace server's calls query
        treats `:*` as a "latest version" wildcard (LIKE `...:%`), and the frontend's
        `parseRef` accepts it too, so we construct the ref synchronously from the
        current weave client's entity/project without a network call. Names that
        already look like refs or are predeclared agent-span op names pass through
        unchanged.

        If no weave client is active at construction time, op_names are left as-is.
        This is intentional: a Monitor is only useful in a weave-initialized context
        (publish/activate require a client), and validators on `from_obj` reads
        should not raise when reconstructing already-stored refs.
        """
        if not self.op_names:
            return self
        client = get_weave_client()
        if client is None:
            return self
        entity = client.entity
        project = client.project
        resolved: list[str] = []
        for name in self.op_names:
            if _looks_like_ref(name) or name in AGENT_SPAN_OP_NAMES:
                resolved.append(name)
                continue
            resolved.append(f"weave:///{entity}/{project}/op/{name}:*")
        self.op_names = resolved
        return self

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls.model_validate(obj.unwrap())


def _looks_like_ref(name: str) -> bool:
    """True if `name` is already a weave object/op ref URI."""
    return name.startswith("weave:///")


_OP_CALL_CLASSIFIER_PROMPT_HEADER = "\n".join(
    [
        "You are a multi-classifier evaluation system. Evaluate a traced function call against multiple binary classifiers.",
        "<trace>",
        "  <metadata>",
        "    <operation>{op_name}</operation>",
        "    <status>{status}</status>",
        "  </metadata>",
        "  <input>",
        "  {inputs}",
        "  </input>",
        "  <output>",
        "  {output}",
        "  </output>",
        "  <exception>",
        "  {exception}",
        "  </exception>",
        "  <source_code>",
        "  {op_source}",
        "  </source_code>",
        "</trace>",
        "Evaluate the trace above against each classifier below. Base your judgment strictly on the evidence in the trace.",
    ]
)
_AGENT_SPAN_CLASSIFIER_PROMPT_HEADER = "\n".join(
    [
        "You are a multi-classifier evaluation system. Evaluate a traced function call against multiple binary classifiers.",
        "<agent>",
        "<name>{agent_name}</name>",
        "<version>{agent_version}</version>",
        "<description>{agent_description}</description>",
        "<status>",
        "  <code>{status_code}</code>",
        "  <message>{status_message}</message>",
        "</status>",
        "<messages>",
        "  <conversation-name>{conversation_name}</conversation-name>",
        "  <system-instructions>",
        "  {system_instructions}",
        "  </system-instructions>",
        "  <input-messages>",
        "  {input_messages}",
        "  </input-messages>",
        "  <output-messages>",
        "  {output_messages}",
        "  </output-messages>",
        "</messages>",
        "</agent>",
        "Evaluate the trace above against each classifier below. Base your judgment strictly on the evidence in the trace.",
    ]
)
_CLASSIFIER_PROMPT_FOOTER = "\n".join(
    [
        "Respond with ONLY a JSON object. No markdown fences, no explanation — just the JSON.",
        "Use the exact classifier name from each <classifier> tag.",
        '{{"classifiers": {{',
        '    "ExactName1": {{"is_match": true, "confidence": 0.95, "reason": "one sentence citing specific evidence from the trace"}},',
        '    "ExactName2": {{"is_match": false, "confidence": 0.80, "reason": "one sentence citing specific evidence from the trace"}},',
        "  }}",
        "}}",
        "Rules:",
        '- "classifiers": include an entry for EVERY classifier (match or not) with is_match, confidence, and reason.',
        '- "is_match": true if this classifier applies (the trace exhibits this issue), false otherwise.',
        '- "confidence": your certainty from 0.0 (uncertain) to 1.0 (certain)',
        '- "reason": cite specific evidence from the trace (quote error messages, describe output content, reference status). Be concise (one sentence). Do NOT give generic reasons like "no evidence found".',
        '- If multiple classifiers could apply, choose the MOST SPECIFIC ones. For example, "Request Too Large" is more specific than "Bad Request", and "Ratelimited" is more specific than "Bad Response". Only set is_match to true for the most specific matches.',
    ]
)


@register_object
class ClassifierMonitor(Monitor):
    """A monitor that merges multiple scorers into a single classifier.

    Classifier monitors combine prompts from multiple LLMAsAJudgeScorers
    targeting the same model into a single scoring call.
    """

    # DEPRECATED: header/footer are now hardcoded and these fields are ignored
    prompt_header: str | None = Field(
        default=None,
        deprecated="prompt_header is unused; templates are hardcoded via get_prompt_header.",
    )
    prompt_footer: str | None = Field(
        default=None,
        deprecated="prompt_footer is unused; templates are hardcoded via get_prompt_footer.",
    )

    def get_prompt_header(self, op_name: str) -> str:
        """Text to prepend before the merged classifier prompts."""
        if op_name in AGENT_SPAN_OP_NAMES:
            return _AGENT_SPAN_CLASSIFIER_PROMPT_HEADER
        return _OP_CALL_CLASSIFIER_PROMPT_HEADER

    def get_prompt_footer(self) -> str:
        """Text to append after the merged classifier prompts."""
        return _CLASSIFIER_PROMPT_FOOTER
