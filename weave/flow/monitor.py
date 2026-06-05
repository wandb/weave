from typing import Any, Literal, TypeAlias, get_args

from pydantic import Field, field_validator
from typing_extensions import NotRequired, Self, TypedDict

from weave.flow.casting import Scorer
from weave.object.obj import Object
from weave.trace.api import ObjectRef, publish
from weave.trace.context.weave_client_context import (
    get_weave_client,
    require_weave_client,
)
from weave.trace.objectify import register_object
from weave.trace.refs import OpRef, Ref
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

    Note that the op name will be converted to a weave ref using the entity and project
    from the Weave client. If you're operating on multiple entities and projects
    with the same client, you'll need to specify a fully-qualified weave ref.
    See _normalized_op_names for more details.

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

    @field_validator("op_names", mode="before")
    @classmethod
    def _coerce_op_name_refs_to_str(cls, value: Any) -> Any:
        """Access op-name refs as their URI string.

        ``op_names`` is stored as full ``weave:///`` op refs (WB-33908). When a
        stored Monitor is loaded, Weave's value layer turns those ref-shaped
        strings back into ``Ref`` objects, which the ``list[AgentSpanOpName |
        str]`` field would reject. Pydantic runs this ``mode="before"`` validator
        automatically on every load/construct; it maps any ``Ref`` back to its
        URI string so the Monitor objectifies cleanly.
        """
        if isinstance(value, list):
            return [item.uri() if isinstance(item, Ref) else item for item in value]
        return value

    def model_post_init(self, context: Any, /) -> None:
        """Normalize ``op_names`` at construction when a client is available.

        Publishing has no per-object hook, so to also cover a bare
        ``weave.publish(monitor)`` (no ``activate()``), expand short names here:
        anyone who will publish has typically called ``weave.init``, so the client
        is set when the monitor is constructed.

        Several use cases perform construction without a client, such as unit tests,
        inspection, deserializing a stored monitor in a worker. The guard on
        ``get_weave_client()`` allows construction without a client. Normalization
        won't occur in this case, but that should be ok because stored monitors already
        hold full refs.

        There is an edge case where a monitor can be created using the SDK without
        normalizing: if the user constructs the monitor, then calls weave.init,
        and then publishes it. Calling ``activate()`` or ``deactivate()`` could be
        a workaround for this use-case.
        """
        super().model_post_init(context)
        if get_weave_client() is not None:
            self.op_names = self._normalized_op_names()

    def activate(self) -> ObjectRef:
        """Activates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = True
        self.ref = None
        self.op_names = self._normalized_op_names()
        return publish(self)

    def deactivate(self) -> ObjectRef:
        """Deactivates the monitor.

        Returns:
            The ref to the monitor.
        """
        self.active = False
        self.ref = None
        self.op_names = self._normalized_op_names()
        return publish(self)

    def _normalized_op_names(self) -> list[str]:
        """Expand bare op names to fully-qualified ``weave:///`` op refs before saving.

        Both the UI and the scoring worker require full refs. However, the public
        ``Monitor`` example tells users to pass a short name (``op_names=["my_op"]``).
        To satisfy both use-cases, we perform a conversion here using the
        active client's entity/project.

        Entries that are already ``weave:///`` refs, or agent-span literals
        like ``"weave.genai.turn_ended"``, are returned unchanged.
        """

        def needs_expansion(name: str) -> bool:
            return name not in AGENT_SPAN_OP_NAMES and not name.strip().startswith(
                "weave:///"
            )

        if not any(needs_expansion(name) for name in self.op_names):
            return list(self.op_names)

        client = require_weave_client()
        entity, project = client.entity, client.project
        normalized: list[str] = []
        for name in self.op_names:
            if not needs_expansion(name):
                normalized.append(name)
                continue
            short = name.strip().strip("/")
            if not short:
                raise ValueError(f"op_names entries must be non-empty; got {name!r}")
            if "/" in short:
                raise ValueError(
                    "op_names entries must be a weave URI starting with 'weave:///', "
                    f"or a single op short name (no '/'); got {name!r}"
                )
            normalized.append(
                OpRef(entity=entity, project=project, name=short, _digest="*").uri()
            )
        return normalized

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls.model_validate(obj.unwrap())


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
