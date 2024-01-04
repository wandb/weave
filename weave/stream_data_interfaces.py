# This file contains the low-level dictionary definitions for the
# data types which can be logged to StreamTables and consumed
# by various Prompts products in the Weave UI. It is rare that an
# end user would directly interact with these types. Instead, they
# are more likely to be used by someone building an integration or
# an MLOps engineer setting up a pipeline for their team.

import typing
from uuid import uuid4

from wandb.sdk.data_types.trace_tree import Span as WBSpan


# TraceSpanDict is the lowest common denominator for a span
# in the Weave system. It conforms to the OpenTelemetry spec
class TraceSpanDict(typing.TypedDict):
    # **OpenTelemetry spec**

    # The ID of the span - typically a UUID
    span_id: str

    # The name of the span - typically the name of the operation
    name: str

    # The ID of the trace this span belongs to - typically a UUID
    trace_id: str

    # The status code conforming to the OpenTelemetry spec
    # I would like to use a literal `typing.Literal["SUCCESS", "ERROR", "UNSET"]`
    # here, but then you have to type it this way everywhere and probably causes
    # more problems than it solves.
    status_code: str

    # Start and end times in seconds since the epoch
    start_time_s: float
    end_time_s: float

    # The parent span ID - typically a UUID (optional)
    # if not set, this is a root span
    parent_id: typing.Optional[str]

    # **Weave specific keys**

    # Attributes are any key value pairs associated with the span,
    # typically known before the execution operation
    attributes: typing.Optional[typing.Dict[str, typing.Any]]

    # Inputs are the parameters to the operation
    inputs: typing.Optional[typing.Dict[str, typing.Any]]

    # Output is the result of the operation
    output: typing.Optional[typing.Any]

    # Summary is a dictionary of key value pairs that summarize
    # the execution of the operation. This data is typically only
    # available after the operation has completed, as a function
    # of the output.
    summary: typing.Optional[typing.Dict[str, typing.Any]]

    # Exception is any free form string describing an exception
    # that occurred during the execution of the operation
    exception: typing.Optional[str]


# LLM Completion is a specific type of span that is used to
# represent the execution of a language model. We use a structure
# modelled after OpenAI's API to represent the inputs and outputs.


class _LLMCompletionMessage(typing.TypedDict):
    role: typing.Optional[str]
    content: typing.Optional[str]


class _LLMCompletionInputs(typing.TypedDict):
    messages: typing.Optional[typing.List[_LLMCompletionMessage]]


class _LLMCompletionChoice(typing.TypedDict):
    message: typing.Optional[_LLMCompletionMessage]
    finish_reason: typing.Optional[str]
    index: typing.Optional[int]


class _LLMCompletionOutput(typing.TypedDict):
    id: typing.Optional[str]
    object: typing.Optional[str]
    model: typing.Optional[str]
    choices: typing.Optional[typing.List[_LLMCompletionChoice]]


class _LLMCompletionSummary(typing.TypedDict):
    prompt_tokens: typing.Optional[int]
    completion_tokens: typing.Optional[int]
    total_tokens: typing.Optional[int]


# Ideally we would inherit from TraceSpanDict here, but
# mypy doesn't support that level of sophistication yet.
# The only difference between this and TraceSpanDict is
# the further specification of the inputs, output, and summary.
class LLMCompletionDict(typing.TypedDict):
    # **OpenTelemetry spec**

    # The ID of the span - typically a UUID
    span_id: str

    # The name of the span - typically the name of the operation
    name: str

    # The ID of the trace this span belongs to - typically a UUID
    trace_id: str

    # The status code conforming to the OpenTelemetry spec
    # I would like to use a literal `typing.Literal["SUCCESS", "ERROR", "UNSET"]`
    # here, but then you have to type it this way everywhere and probably causes
    # more problems than it solves.
    status_code: str

    # Start and end times in seconds since the epoch
    start_time_s: float
    end_time_s: float

    # The parent span ID - typically a UUID (optional)
    # if not set, this is a root span
    parent_id: typing.Optional[str]

    # **Weave specific keys**

    # Attributes are any key value pairs associated with the span,
    # typically known before the execution operation
    attributes: typing.Optional[typing.Dict[str, typing.Any]]

    # Inputs are the parameters to the operation
    inputs: typing.Optional[_LLMCompletionInputs]

    # Output is the result of the operation
    output: typing.Optional[_LLMCompletionOutput]

    # Summary is a dictionary of key value pairs that summarize
    # the execution of the operation. This data is typically only
    # available after the operation has completed, as a function
    # of the output.
    summary: typing.Optional[_LLMCompletionSummary]

    # Exception is any free form string describing an exception
    # that occurred during the execution of the operation
    exception: typing.Optional[str]


# We rely on all the hard work already in our W&B integration and just
# simply map the properties of the WB Span to the Weave Span
def wb_span_to_weave_spans(
    wb_span: WBSpan,
    trace_id: typing.Optional[str] = None,
    parent_id: typing.Optional[str] = None,
) -> typing.List[TraceSpanDict]:
    attributes = {**wb_span.attributes} if wb_span.attributes is not None else {}
    if hasattr(wb_span, "span_kind") and wb_span.span_kind is not None:
        attributes["span_kind"] = str(wb_span.span_kind)
    inputs = (
        wb_span.results[0].inputs
        if wb_span.results is not None and len(wb_span.results) > 0
        else None
    )
    outputs = (
        wb_span.results[0].outputs
        if wb_span.results is not None and len(wb_span.results) > 0
        else None
    )

    # Super Hack - fix merge!
    dummy_dict = {"_": ""} if parent_id == None else {}

    span_id = wb_span.span_id
    if span_id is None:
        span_id = str(uuid4())

    if (
        wb_span.start_time_ms is None
        or wb_span.end_time_ms is None
        or span_id is None
        or wb_span.name is None
    ):
        return []

    span = TraceSpanDict(
        start_time_s=wb_span.start_time_ms / 1000.0,
        end_time_s=wb_span.end_time_ms / 1000.0,
        span_id=span_id,
        name=wb_span.name,
        status_code=str(wb_span.status_code),
        trace_id=trace_id or span_id,
        parent_id=parent_id,
        # Followup: allow None in attributes & summary (there is an issue with vectorized opMerge)
        # This should be fixed before integrating inside LC
        attributes=attributes or dummy_dict,
        summary=dummy_dict,
        inputs=inputs,
        output=outputs,
        exception=wb_span.status_message
        if wb_span.status_message is not None
        else None,
    )
    spans = [span]
    for child in wb_span.child_spans or []:
        spans += wb_span_to_weave_spans(child, span["trace_id"], span["span_id"])

    return spans
